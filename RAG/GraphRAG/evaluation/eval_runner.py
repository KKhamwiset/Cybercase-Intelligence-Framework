"""
Evaluation Runner
==================
CLI orchestrator for RAG evaluation.

Usage:
    cd d:\\Doc\\TSR_Mitre\\RAG\\GraphRAG
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
import json
import sys
import os
from pathlib import Path

# Add parent directory to path for imports
_SCRIPT_DIR = Path(__file__).resolve().parent
_GRAPHRAG_DIR = _SCRIPT_DIR.parent
if str(_GRAPHRAG_DIR) not in sys.path:
    sys.path.insert(0, str(_GRAPHRAG_DIR))

from evaluation.ground_truth import load_ground_truth, EvalSample
from evaluation.retriever_metrics import evaluate_retriever, RetrieverEvalResult
from evaluation.generation_metrics import evaluate_generation, GenerationEvalResult


# ──────────────────────────────────────────────────────────────────────────────
# Retriever Adapters
# ──────────────────────────────────────────────────────────────────────────────

def _make_vector_retriever_fn(embed_model=None):
    """Create a retriever function for vector-only search."""
    from retrieval.vector_retriever import VectorRetriever
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
    from retrieval.graph_retriever import GraphRetriever
    retriever = GraphRetriever()

    def fn(query: str) -> list[str]:
        # Graph retriever finds nodes by name match, then expands
        results = retriever.query_cypher(
            """
            MATCH (n)
            WHERE toLower(n.name) CONTAINS toLower($query)
               OR toLower(n.description) CONTAINS toLower($query)
            RETURN n.stix_id AS stix_id
            LIMIT 10
            """,
            params={"query": query},
        )
        return [r["stix_id"] for r in results if r.get("stix_id")]

    return fn, retriever.close


def _make_hybrid_retriever_fn(embed_model=None):
    """Create a retriever function for hybrid (Vector + Graph) search."""
    from retrieval.hybrid_retriever import HybridRetriever
    retriever = HybridRetriever(embed_model=embed_model)

    def fn(query: str) -> list[str]:
        result = retriever.retrieve(query, top_k=10)

        # Collect STIX IDs from both vector and graph results
        ids = []
        seen = set()
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

    return fn, retriever.close


# ──────────────────────────────────────────────────────────────────────────────
# Generation Adapter
# ──────────────────────────────────────────────────────────────────────────────

def _make_generation_fn(embed_model=None):
    """Create a generation function wrapping GraphRAGChain."""
    from pipeline.chain import GraphRAGChain
    chain = GraphRAGChain(embed_model=embed_model)

    def fn(query: str) -> tuple[str, list[str]]:
        """Returns (answer, list_of_context_chunks)."""
        # Get retrieval context
        english_query = chain.translator.translate_query(query)
        graphrag_result = chain.retriever.retrieve(english_query)

        from pipeline.context_builder import build_context
        context = build_context(graphrag_result)

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

    def __init__(self, dataset_path: str, mode: str = "full"):
        self.dataset_path = Path(dataset_path)
        self.mode = mode
        self.samples = load_ground_truth(self.dataset_path)
        self._embed_model = None
        self._cleanups = []

    def _get_embed_model(self):
        """Lazy-load and share the embedding model."""
        if self._embed_model is None:
            from sentence_transformers import SentenceTransformer
            from config import EMBED_MODEL
            print(f"\n[EVAL] Loading shared embedding model: {EMBED_MODEL}")
            self._embed_model = SentenceTransformer(EMBED_MODEL)
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
        print(f"\n[EVAL] Running retriever evaluation ({len(eval_samples)} samples with ground truth)")

        results = []
        embed_model = self._get_embed_model()

        # 1. Vector Retriever
        print("\n" + "═" * 60)
        print("  Evaluating: Vector Retriever (ChromaDB)")
        print("═" * 60)
        fn, cleanup = _make_vector_retriever_fn(embed_model)
        if cleanup:
            self._cleanups.append(cleanup)
        vr_result = evaluate_retriever(fn, eval_samples, retriever_name="Vector (ChromaDB)")
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
            gr_result = evaluate_retriever(fn, eval_samples, retriever_name="Graph (Neo4j)")
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
            hr_result = evaluate_retriever(fn, eval_samples, retriever_name="Hybrid (Vector+Graph)")
            results.append(hr_result)
            print(hr_result.to_table())
        except Exception as e:
            print(f"  [SKIP] Hybrid retriever unavailable: {e}")

        # Comparison table
        self._print_comparison(results)
        return results

    def _run_generation_eval(self) -> GenerationEvalResult:
        """Run generation evaluation."""
        print("\n" + "═" * 60)
        print("  Evaluating: Answer Generation (GraphRAGChain)")
        print("═" * 60)

        embed_model = self._get_embed_model()
        fn, cleanup = _make_generation_fn(embed_model)
        if cleanup:
            self._cleanups.append(cleanup)

        gen_result = evaluate_generation(fn, self.samples)
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

    args = parser.parse_args()

    runner = EvalRunner(dataset_path=args.dataset, mode=args.mode)
    results = runner.run()

    print("\n" + "═" * 60)
    print("  EVALUATION COMPLETE")
    print("═" * 60)


if __name__ == "__main__":
    main()
