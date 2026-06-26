"""
Evaluation Runner
==================
CLI orchestrator for RAG evaluation.

Usage:
    cd backend/RAG/GraphRAG
    python -m evaluation.eval_runner --dataset evaluation/eval_dataset.json --mode retriever
    python -m evaluation.eval_runner --dataset evaluation/eval_dataset.json --mode generation
    python -m evaluation.eval_runner --dataset evaluation/eval_dataset.json --mode full

Modes:
    retriever  — Benchmark Vector / Graph / Hybrid retrievers
    generation — Evaluate LLM answer quality (RAGAS + fallback)
    full       — Run both retriever + generation evaluation
"""

from __future__ import annotations
import argparse
import io
import sys
from pathlib import Path

# Fix relative imports when run directly from IDE or wrong directory
if __package__ is None or __package__ == "evaluation":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    __package__ = "GraphRAG.evaluation"

sys.stdout.reconfigure(encoding='utf-8')
# UTF-8 FIX FOR WINDOWS
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from .generation_metrics import GenerationEvalResult, evaluate_generation
from .ground_truth import load_ground_truth
from .retriever_metrics import RetrieverEvalResult, evaluate_retriever

# ──────────────────────────────────────────────────────────────────────────────
# Retriever Adapters
# ──────────────────────────────────────────────────────────────────────────────


def _make_vector_retriever_fn(embed_model=None):
    """Create a retriever function for vector-only search."""
    from ..retrieval.vector_retriever import VectorRetriever

    retriever = VectorRetriever(embed_model=embed_model)

    def fn(query: str) -> list[str]:
        results = retriever.search_all(query, top_k=10)
        return [r.stix_id for r in results]

    return fn, None  # No cleanup needed for vector retriever


def _make_graph_retriever_fn():
    """Create a retriever function for graph-only search (requires STIX IDs as seed).

    Note: GraphRetriever expands from known STIX IDs, so for standalone eval
    we use it differently — we do a Cypher name search first.
    """
    from ..retrieval.graph_retriever import GraphRetriever
    import re

    retriever = GraphRetriever()

    def fn(query: str) -> list[str]:
        # Extract ATT&CK IDs (e.g., T1566, S0002, G0016)
        attack_ids = re.findall(r'[T|S|G]\d{4}', query, re.IGNORECASE)
        
        # Extract basic keywords (ignoring common words)
        ignore_words = {"what", "is", "the", "how", "can", "i", "do", "does", "are", "explain", "relationship", "between", "and", "in", "for", "to", "of", "a", "an", "all", "technique", "techniques", "exist", "does", "use", "detect", "data", "sources", "classified", "as", "work", "campaigns", "have", "targeted", "sector"}
        clean_query = re.sub(r'[^\w\s]', ' ', query).lower()
        keywords = [w for w in clean_query.split() if w not in ignore_words and len(w) > 2]
        
        match_clauses = []
        params = {}
        
        if attack_ids:
            for i, aid in enumerate(attack_ids):
                match_clauses.append(f"toUpper(n.attack_id) = $attack_id_{i}")
                params[f"attack_id_{i}"] = aid.upper()
                
        if keywords:
            for i, kw in enumerate(keywords):
                match_clauses.append(f"toLower(n.name) CONTAINS $kw_{i}")
                params[f"kw_{i}"] = kw
        
        # Fallback to whole string match if no keywords found
        if not match_clauses:
            match_clauses.append("toLower(n.name) CONTAINS toLower($query) OR toLower(n.description) CONTAINS toLower($query)")
            params["query"] = query
            
        where_clause = " OR ".join(match_clauses)
        
        # Find matching nodes, then expand 1 hop to simulate graph expansion
        cypher = f"""
        MATCH (n)
        WHERE {where_clause}
        WITH n LIMIT 5
        OPTIONAL MATCH (n)-[]-(m)
        WITH n, collect(m.stix_id) AS neighbor_ids
        RETURN n.stix_id AS stix_id, neighbor_ids
        """
        
        try:
            results = retriever.query_cypher(cypher, params=params)
            ids = set()
            for r in results:
                if r.get("stix_id"):
                    ids.add(r["stix_id"])
                for nid in r.get("neighbor_ids", []):
                    if nid:
                        ids.add(nid)
            return list(ids)
        except Exception as e:
            print(f"[GRAPH] Cypher error: {e}")
            return []

    return fn, retriever.close


def _collect_hybrid_ids(result) -> list[str]:
    """Flatten a GraphRAGResult into an ordered, deduped STIX-id list
    (vector hits first, then each subgraph's center node + neighbors)."""
    ids: list[str] = []
    seen: set[str] = set()
    for vr in result.vector_results:
        if vr.stix_id not in seen:
            ids.append(vr.stix_id)
            seen.add(vr.stix_id)
    for gr in result.graph_results:
        if gr.center_node and gr.center_node.stix_id not in seen:
            ids.append(gr.center_node.stix_id)
            seen.add(gr.center_node.stix_id)
        for nb in gr.neighbors:
            if nb.stix_id not in seen:
                ids.append(nb.stix_id)
                seen.add(nb.stix_id)
    return ids


def _make_hybrid_retriever_fn(embed_model=None):
    """Create a retriever function for hybrid (Vector + Graph) search —
    single-query baseline (no decomposition)."""
    from ..retrieval.hybrid_retriever import HybridRetriever

    retriever = HybridRetriever(embed_model=embed_model)

    def fn(query: str) -> list[str]:
        result = retriever.retrieve(query, top_k=10)
        return _collect_hybrid_ids(result)

    return fn, retriever.close


def _make_hybrid_quota_retriever_fn(embed_model=None, use_local: bool = False):
    """Hybrid retriever with query decomposition + per-query quota — mirrors the
    production agent path (``_node_retrieve``). The incident is decomposed into
    atomic per-technique sub-queries, each retrieved under a quota and round-robin
    interleaved, so every technique survives the final trim. Compare against
    ``_make_hybrid_retriever_fn`` (single-query) to measure whether decompose +
    quota improves multi-technique recall.

    NOTE: decomposition needs an LLM (ANTHROPIC_API_KEY, or --local Ollama). With
    no LLM the decomposer falls back to the whole query → this degenerates to a
    single-query hybrid run (the eval would then just mirror the baseline).
    """
    from ..config import VECTOR_TOP_K
    from ..pipeline.query_decomposer import QueryDecomposer
    from ..retrieval.hybrid_retriever import HybridRetriever

    retriever = HybridRetriever(embed_model=embed_model)
    decomposer = QueryDecomposer(use_local=use_local)

    def fn(query: str) -> list[str]:
        sub_queries = decomposer.decompose(incident=query, verbose=False)
        result = retriever.retrieve_multi_quota(
            sub_queries, per_query_k=3, top_k=VECTOR_TOP_K, max_vector=15, max_graph=8
        )
        return _collect_hybrid_ids(result)

    return fn, retriever.close


# ──────────────────────────────────────────────────────────────────────────────
# Generation Adapter
# ──────────────────────────────────────────────────────────────────────────────


def _make_generation_fn(embed_model=None, use_local: bool = False):
    """Create a generation function wrapping GraphRAGChain."""
    from ..pipeline.chain import GraphRAGChain

    chain = GraphRAGChain(embed_model=embed_model, use_local=use_local)

    def fn(query: str) -> tuple[str, list[str]]:
        """Returns (answer, list_of_context_chunks)."""
        # Get retrieval context (same dual-query flow as GraphRAGChain.query)
        from ..pipeline.cross_lingual import build_retrieval_queries

        english_query = chain.translator.translate_query(query)
        queries = build_retrieval_queries(query, english_query)
        graphrag_result = chain.retriever.retrieve_multi(queries)

        from ..pipeline.context_builder import build_context

        build_context(graphrag_result)

        # Get answer
        answer = chain.query(query, verbose=False)

        # Split context into chunks for RAGAS (one per semantic result)
        context_chunks = []
        for vr in graphrag_result.vector_results[:5]:
            context_chunks.append(vr.document)
        for gr in graphrag_result.graph_results:
            text = gr.to_text()
            if text:
                context_chunks.append(text)

        return answer, context_chunks

    return fn, chain.close


# ──────────────────────────────────────────────────────────────────────────────
# Main Runner
# ──────────────────────────────────────────────────────────────────────────────


class EvalRunner:
    """Orchestrates the full evaluation pipeline."""

    def __init__(self, dataset_path: str, mode: str = "full", use_local: bool = False, max_samples: int = 0):
        self.dataset_path = Path(dataset_path)
        self.mode = mode
        self.use_local = use_local

        all_samples = load_ground_truth(self.dataset_path)
        # Filter out samples with > 50 relevant STIX IDs
        self.samples = [
            s for s in all_samples
            if not s.relevant_stix_ids or len(s.relevant_stix_ids) <= 50
        ]

        filtered_count = len(all_samples) - len(self.samples)
        if filtered_count > 0:
            print(f"[EVAL] Filtered out {filtered_count} samples with > 50 relevant STIX IDs")

        if max_samples and max_samples < len(self.samples):
            self.samples = self.samples[:max_samples]
            print(f"[EVAL] Capped to {max_samples} samples (--max-samples)")

        print(f"[EVAL] Samples for evaluation: {len(self.samples)}")
        
        self._embed_model = None
        self._cleanups = []

    def _get_embed_model(self):
        """Lazy-load and share the embedding model."""
        if self._embed_model is None:
            from FlagEmbedding import BGEM3FlagModel
            from ..config import EMBED_MODEL, USE_FP16

            print(f"[EVAL] Loading embedding model {EMBED_MODEL}...")
            self._embed_model = BGEM3FlagModel(EMBED_MODEL, use_fp16=USE_FP16)
        return self._embed_model

    def run(self) -> dict:
        """Execute evaluation and return results dict."""
        results = {}

        try:
            if self.mode in ("retriever", "full"):
                results["retriever"] = self._run_retriever_eval()

            if self.mode in ("generation", "full"):
                results["generation"] = self._run_generation_eval()
        finally:
            # Cleanup all opened resources
            for cleanup in self._cleanups:
                try:
                    cleanup()
                except Exception:
                    pass

        return results

    def _run_retriever_eval(self) -> list[RetrieverEvalResult]:
        """Run retriever benchmarks on all 3 retriever modes."""
        # Only use samples that have relevant STIX IDs
        eval_samples = [s for s in self.samples if s.relevant_stix_ids]
        print(
            f"\n[EVAL] Running retriever evaluation ({len(eval_samples)} samples with ground truth)"
        )

        results = []
        embed_model = self._get_embed_model()

        # 1. Vector Retriever
        print("\n" + "═" * 60)
        print("  Evaluating: Vector Retriever (ChromaDB)")
        print("═" * 60)
        fn, cleanup = _make_vector_retriever_fn(embed_model)
        if cleanup:
            self._cleanups.append(cleanup)
        vr_result = evaluate_retriever(
            fn, eval_samples, retriever_name="Vector (ChromaDB)"
        )
        results.append(vr_result)
        print(vr_result.to_table())

        # 2. Graph Retriever
        print("\n" + "═" * 60)
        print("  Evaluating: Graph Retriever (Neo4j)")
        print("═" * 60)
        try:
            fn, cleanup = _make_graph_retriever_fn()
            if cleanup:
                self._cleanups.append(cleanup)
            gr_result = evaluate_retriever(
                fn, eval_samples, retriever_name="Graph (Neo4j)"
            )
            results.append(gr_result)
            print(gr_result.to_table())
        except Exception as e:
            print(f"  [SKIP] Graph retriever unavailable: {e}")

        # 3. Hybrid Retriever
        print("\n" + "═" * 60)
        print("  Evaluating: Hybrid Retriever (Vector + Graph)")
        print("═" * 60)
        try:
            fn, cleanup = _make_hybrid_retriever_fn(embed_model)
            if cleanup:
                self._cleanups.append(cleanup)
            hr_result = evaluate_retriever(
                fn, eval_samples, retriever_name="Hybrid (Vector+Graph)"
            )
            results.append(hr_result)
            print(hr_result.to_table())
        except Exception as e:
            print(f"  [SKIP] Hybrid retriever unavailable: {e}")

        # 4. Hybrid + Quota (decompose → retrieve_multi_quota) — production agent path
        print("\n" + "═" * 60)
        print("  Evaluating: Hybrid + Quota (decompose + per-query quota)")
        print("═" * 60)
        try:
            fn, cleanup = _make_hybrid_quota_retriever_fn(
                embed_model, use_local=self.use_local
            )
            if cleanup:
                self._cleanups.append(cleanup)
            hq_result = evaluate_retriever(
                fn, eval_samples, retriever_name="Hybrid+Quota (decompose)"
            )
            results.append(hq_result)
            print(hq_result.to_table())
        except Exception as e:
            print(f"  [SKIP] Hybrid+Quota retriever unavailable: {e}")

        # Comparison table
        self._print_comparison(results)
        return results

    def _run_generation_eval(self) -> GenerationEvalResult:
        """Run generation evaluation."""
        print("\n" + "═" * 60)
        print("  Evaluating: Answer Generation (GraphRAGChain)")
        print("═" * 60)

        embed_model = self._get_embed_model()
        fn, cleanup = _make_generation_fn(embed_model, use_local=self.use_local)
        if cleanup:
            self._cleanups.append(cleanup)

        gen_result = evaluate_generation(fn, self.samples, use_local=self.use_local)
        print(gen_result.to_table())
        return gen_result

    def _print_comparison(self, results: list[RetrieverEvalResult]) -> None:
        """Print a side-by-side comparison table."""
        if len(results) < 2:
            return

        print("\n" + "═" * 70)
        print("  RETRIEVER COMPARISON")
        print("═" * 70)

        # Header
        header = f"  {'Metric':<20}"
        for r in results:
            short = r.retriever_name.split("(")[0].strip()
            header += f"{short:>16}"
        print(header)
        print("  " + "─" * (20 + 16 * len(results)))

        # K=5 metrics (most common benchmark)
        k = 5
        for metric_name in ["Hit", "Recall", "Precision", "NDCG"]:
            row = f"  {metric_name + '@' + str(k):<20}"
            for r in results:
                metric_dict = getattr(r, f"{metric_name.lower()}_at_k")
                val = metric_dict.get(k, 0.0)
                row += f"{val:>16.3f}"
            print(row)

        # Scalar metrics
        for metric_name, attr in [("MRR", "mrr"), ("MAP", "map_score")]:
            row = f"  {metric_name:<20}"
            for r in results:
                val = getattr(r, attr)
                row += f"{val:>16.3f}"
            print(row)

        # Latency
        row = f"  {'Latency (ms)':<20}"
        for r in results:
            row += f"{r.avg_latency_ms:>16.1f}"
        print(row)
        print()


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="RAG Evaluation Runner for MITRE ATT&CK GraphRAG"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="evaluation/eval_dataset.json",
        help="Path to ground truth JSON file",
    )
    parser.add_argument(
        "--mode",
        choices=["retriever", "generation", "full"],
        default="full",
        help="Evaluation mode: retriever, generation, or full (both)",
    )
    parser.add_argument(
        "--output", type=str, help="Export output to file (.txt or .md)"
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=0,
        help="Limit evaluation to first N samples (0 = no limit)",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help=(
            "Use local Ollama models instead of Claude/OpenRouter. "
            "Generation: qwen2.5:7b  |  RAGAS judge: gemma3:4b  "
            "(requires: ollama pull qwen2.5:7b && ollama pull gemma3:4b)"
        ),
    )

    args = parser.parse_args()

    if args.local:
        from ..config import LOCAL_LLM_MODEL, LOCAL_EVAL_MODEL, OLLAMA_BASE_URL
        print(f"\n[LOCAL MODE]  Generation model : {LOCAL_LLM_MODEL}")
        print(f"[LOCAL MODE]  RAGAS judge      : {LOCAL_EVAL_MODEL}")
        print(f"[LOCAL MODE]  Ollama URL        : {OLLAMA_BASE_URL}\n")

    if args.output:
        tee = open(args.output, "w", encoding="utf-8")

        class Tee:
            def write(self, data):
                sys.stdout_orig.write(data)  # type: ignore
                tee.write(data)

            def flush(self):
                sys.stdout_orig.flush()  # type: ignore
                tee.flush()

        sys.stdout_orig = sys.stdout  # type: ignore
        sys.stdout = Tee()  # type: ignore

    runner = EvalRunner(dataset_path=args.dataset, mode=args.mode, use_local=args.local, max_samples=args.max_samples)
    runner.run()

    print("\n" + "═" * 60)
    print("  EVALUATION COMPLETE")
    print("═" * 60)


if __name__ == "__main__":
    main()
