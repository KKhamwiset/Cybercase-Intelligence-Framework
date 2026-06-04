"""
Cross-Encoder Reranker
=======================
Post-retrieval reranker that rescores vector search results using a
cross-encoder model for joint query-document relevance.  Replaces the
raw RRF fusion score with a more precise relevance signal before the
top-K cut that feeds graph expansion and the LLM context.
"""
from __future__ import annotations

import math

from .vector_retriever import VectorResult
from ..config import FINAL_TOP_K, RERANKER_MODEL


class Reranker:
    """Reranks a list of VectorResults using a cross-encoder model."""

    def __init__(self, model_name: str = RERANKER_MODEL) -> None:
        from sentence_transformers import CrossEncoder
        print(f"[RERANKER] Loading {model_name}...")
        self.model = CrossEncoder(model_name, max_length=512)
        print(f"[RERANKER] Ready")

    def rerank(
        self,
        query: str,
        results: list[VectorResult],
        top_k: int = FINAL_TOP_K,
    ) -> list[VectorResult]:
        """Score each (query, document) pair and return top_k results sorted
        by cross-encoder score.

        Raw logit scores are passed through sigmoid so the final score stays
        in [0, 1] and remains interpretable in context display.
        """
        if not results:
            return results

        pairs = [(query, r.document[:512]) for r in results]
        raw_scores = self.model.predict(pairs)

        for result, raw in zip(results, raw_scores):
            result.score = 1.0 / (1.0 + math.exp(-float(raw)))

        reranked = sorted(results, key=lambda r: r.score, reverse=True)

        print(
            f"[RERANKER] Top-{min(top_k, len(reranked))} after reranking: "
            + ", ".join(
                f"{r.metadata.get('name', r.metadata.get('source_name', '?'))} ({r.score:.3f})"
                for r in reranked[:top_k]
            )
        )
        return reranked
