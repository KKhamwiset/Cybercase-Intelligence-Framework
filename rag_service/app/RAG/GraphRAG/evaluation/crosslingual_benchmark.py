"""
Cross-Lingual Retrieval Benchmark
==================================
Compares three retrieval configurations for Thai queries against the
English-only MITRE ATT&CK knowledge base:

  1. tRAG         — translate query to English, retrieve with translation only
                    (the original pipeline behaviour)
  2. Thai-direct  — retrieve with the raw Thai query, no translation
                    (relies on BGE-M3 cross-lingual dense space)
  3. Dual-query   — retrieve with BOTH queries in parallel, merge by max score
                    (the new DUAL_QUERY_RETRIEVAL behaviour)

Usage (from rag_service/app/RAG/GraphRAG):
    python -m evaluation.crosslingual_benchmark
    python -m evaluation.crosslingual_benchmark --max-samples 50
    python -m evaluation.crosslingual_benchmark --with-graph --output results_xling.md
    python -m evaluation.crosslingual_benchmark --local   # Ollama translation

Notes:
  - Requires Qdrant access (env / Doppler) and an LLM for query translation.
  - Translations are cached in evaluation/translation_cache.json so re-runs
    are free and all configs see the exact same translation.
  - Reported latency excludes the translation LLM call (it is pre-computed);
    in production tRAG and Dual-query pay one extra LLM round-trip that
    Thai-direct does not.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

# Fix relative imports when run directly from IDE or wrong directory
if __package__ is None or __package__ == "evaluation":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    __package__ = "GraphRAG.evaluation"

# UTF-8 FIX FOR WINDOWS
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from .ground_truth import EvalSample, load_ground_truth
from .retriever_metrics import RetrieverEvalResult, evaluate_retriever

_DEFAULT_DATASET = Path(__file__).parent / "Thai_dataset.json"
_DEFAULT_CACHE = Path(__file__).parent / "translation_cache.json"


# ──────────────────────────────────────────────────────────────────────────────
# Translation (pre-computed + cached)
# ──────────────────────────────────────────────────────────────────────────────


def load_cache(path: Path) -> dict[str, str]:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache: dict[str, str], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def translate_all(
    samples: list[EvalSample], cache_path: Path, use_local: bool
) -> dict[str, str]:
    """Translate every query once, reusing/extending the on-disk cache."""
    cache = load_cache(cache_path)
    missing = [s.query for s in samples if s.query not in cache]

    if missing:
        from ..config import ANTHROPIC_API_KEY
        from ..pipeline.cross_lingual import CrossLingualLayer

        if not use_local and not ANTHROPIC_API_KEY:
            print(
                f"[BENCH] ERROR: {len(missing)} queries need translation but no "
                "ANTHROPIC_API_KEY is set (and --local not passed). "
                "tRAG / Dual-query results would be meaningless."
            )
            sys.exit(1)

        print(f"[BENCH] Translating {len(missing)} uncached queries...")
        translator = CrossLingualLayer(use_local=use_local)
        for i, query in enumerate(missing, 1):
            cache[query] = str(translator.translate_query(query)).strip()
            if i % 10 == 0 or i == len(missing):
                print(f"[BENCH]   translated {i}/{len(missing)}")
                save_cache(cache, cache_path)  # checkpoint
        save_cache(cache, cache_path)
        print(f"[BENCH] Translation cache saved → {cache_path.name}")
    else:
        print(f"[BENCH] All {len(samples)} translations found in cache")

    return cache


# ──────────────────────────────────────────────────────────────────────────────
# Retrieval backends
# ──────────────────────────────────────────────────────────────────────────────


class RetrievalBackend:
    """Shared retrieval stack: one embed model, one reranker, one Qdrant client.

    ``retrieve_ids(queries)`` mirrors ``HybridRetriever.retrieve_multi``:
    per-query (vector search → rerank), then merge keeping the highest
    reranker score per stix_id. With ``with_graph=True`` the full hybrid
    pipeline (graph expansion included) is used instead.
    """

    def __init__(self, with_graph: bool, top_k: int):
        from FlagEmbedding import BGEM3FlagModel

        from ..config import EMBED_MODEL, USE_FP16

        self.with_graph = with_graph
        self.top_k = top_k

        print(f"[BENCH] Loading embedding model {EMBED_MODEL}...")
        embed_model = BGEM3FlagModel(EMBED_MODEL, use_fp16=USE_FP16)

        if with_graph:
            from ..retrieval.hybrid_retriever import HybridRetriever

            self._hybrid = HybridRetriever(embed_model=embed_model)
            self._close = self._hybrid.close
        else:
            from ..retrieval.reranker import Reranker
            from ..retrieval.vector_retriever import VectorRetriever

            self._vector = VectorRetriever(embed_model=embed_model)
            self._reranker = Reranker()
            self._close = None

    def close(self) -> None:
        if self._close:
            self._close()

    def retrieve_ids(self, queries: list[str]) -> list[str]:
        if self.with_graph:
            return self._retrieve_hybrid(queries)
        return self._retrieve_vector_rerank(queries)

    def _retrieve_vector_rerank(self, queries: list[str]) -> list[str]:
        merged: dict[str, float] = {}
        for query in queries:
            results = self._vector.search_all(query, top_k=self.top_k)
            results = self._reranker.rerank(query, results, top_k=self.top_k)
            for r in results:
                if r.stix_id not in merged or r.score > merged[r.stix_id]:
                    merged[r.stix_id] = r.score
        return [sid for sid, _ in sorted(merged.items(), key=lambda kv: -kv[1])]

    def _retrieve_hybrid(self, queries: list[str]) -> list[str]:
        # Same ID collection as eval_runner._make_hybrid_retriever_fn
        result = self._hybrid.retrieve_multi(queries, top_k=self.top_k)
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


# ──────────────────────────────────────────────────────────────────────────────
# Comparison table
# ──────────────────────────────────────────────────────────────────────────────


def print_comparison(results: list[RetrieverEvalResult]) -> None:
    print("\n" + "═" * 76)
    print("  CROSS-LINGUAL RETRIEVAL COMPARISON")
    print("═" * 76)

    header = f"  {'Metric':<20}"
    for r in results:
        header += f"{r.retriever_name:>16}"
    print(header)
    print("  " + "─" * (20 + 16 * len(results)))

    for k in (5, 10):
        for metric_name in ("Hit", "Recall", "NDCG"):
            row = f"  {metric_name + '@' + str(k):<20}"
            for r in results:
                row += f"{getattr(r, f'{metric_name.lower()}_at_k').get(k, 0.0):>16.3f}"
            print(row)

    for metric_name, attr in (("MRR", "mrr"), ("MAP", "map_score")):
        row = f"  {metric_name:<20}"
        for r in results:
            row += f"{getattr(r, attr):>16.3f}"
        print(row)

    row = f"  {'Latency (ms)*':<20}"
    for r in results:
        row += f"{r.avg_latency_ms:>16.1f}"
    print(row)
    print("\n  * excludes the translation LLM call (pre-computed & cached)")
    print()


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cross-lingual retrieval benchmark: tRAG vs Thai-direct vs Dual-query"
    )
    parser.add_argument(
        "--dataset", type=str, default=str(_DEFAULT_DATASET),
        help="Ground-truth JSON (default: evaluation/Thai_dataset.json)",
    )
    parser.add_argument(
        "--language", type=str, default="th",
        help="Only evaluate samples with this language tag (default: th; use 'all' to disable)",
    )
    parser.add_argument(
        "--max-samples", type=int, default=0,
        help="Limit to first N samples (0 = all)",
    )
    parser.add_argument(
        "--top-k", type=int, default=10,
        help="Vector top-K per query (default: 10)",
    )
    parser.add_argument(
        "--with-graph", action="store_true",
        help="Benchmark the full hybrid pipeline incl. Neo4j graph expansion "
             "(slower; default benchmarks vector search + rerank only)",
    )
    parser.add_argument(
        "--cache", type=str, default=str(_DEFAULT_CACHE),
        help="Translation cache JSON path",
    )
    parser.add_argument(
        "--local", action="store_true",
        help="Use local Ollama model for query translation",
    )
    parser.add_argument("--output", type=str, help="Tee output to a file")
    args = parser.parse_args()

    if args.output:
        tee = open(args.output, "w", encoding="utf-8")
        stdout_orig = sys.stdout

        class Tee:
            def write(self, data):
                stdout_orig.write(data)
                tee.write(data)

            def flush(self):
                stdout_orig.flush()
                tee.flush()

        sys.stdout = Tee()

    # ── Load samples ──────────────────────────────────────────────────────
    samples = load_ground_truth(args.dataset)
    samples = [s for s in samples if s.relevant_stix_ids and len(s.relevant_stix_ids) <= 50]
    if args.language != "all":
        samples = [s for s in samples if s.language == args.language]
    if args.max_samples and args.max_samples < len(samples):
        samples = samples[: args.max_samples]
    print(f"[BENCH] Evaluating {len(samples)} samples (language={args.language})")
    if not samples:
        print("[BENCH] No samples to evaluate — check --dataset / --language")
        sys.exit(1)

    # ── Pre-compute translations ──────────────────────────────────────────
    translations = translate_all(samples, Path(args.cache), use_local=args.local)

    # ── Shared retrieval stack ────────────────────────────────────────────
    backend = RetrievalBackend(with_graph=args.with_graph, top_k=args.top_k)

    def trag_fn(query: str) -> list[str]:
        return backend.retrieve_ids([translations[query]])

    def thai_direct_fn(query: str) -> list[str]:
        return backend.retrieve_ids([query])

    def dual_fn(query: str) -> list[str]:
        english = translations[query]
        queries = [english] if english.strip() == query.strip() else [english, query]
        return backend.retrieve_ids(queries)

    configs = [
        ("tRAG", trag_fn),
        ("Thai-direct", thai_direct_fn),
        ("Dual-query", dual_fn),
    ]

    results = []
    try:
        for name, fn in configs:
            print("\n" + "═" * 60)
            print(f"  Evaluating config: {name}")
            print("═" * 60)
            result = evaluate_retriever(fn, samples, retriever_name=name)
            results.append(result)
            print(result.to_table())
    finally:
        backend.close()

    print_comparison(results)

    print("═" * 60)
    print("  BENCHMARK COMPLETE")
    print("═" * 60)


if __name__ == "__main__":
    main()
