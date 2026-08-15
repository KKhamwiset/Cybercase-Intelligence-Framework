"""
Cross-Encoder Reranker
=======================
Post-retrieval reranker that rescores vector search results using a
cross-encoder model for joint query-document relevance.  Replaces the
raw RRF fusion score with a more precise relevance signal before the
top-K cut that feeds graph expansion and the LLM context.
"""
from __future__ import annotations

from .vector_retriever import VectorResult
from ..config import DEVICE, FINAL_TOP_K, RERANKER_MODEL


class Reranker:
    """Reranks a list of VectorResults using a cross-encoder model."""

    def __init__(self, model_name: str = RERANKER_MODEL) -> None:
        from sentence_transformers import CrossEncoder
        print(f"[RERANKER] Loading {model_name} on {DEVICE}...")
        self.model = CrossEncoder(model_name, max_length=512, device=DEVICE)
        print(f"[RERANKER] Ready")

    def rerank(
        self,
        query: str,
        results: list[VectorResult],
        top_k: int = FINAL_TOP_K,
    ) -> list[VectorResult]:
        """Score each (query, document) pair and return top_k results sorted
        by cross-encoder score.

        ``CrossEncoder.predict()`` already applies the model's default
        activation, which is ``nn.Sigmoid()`` for a ``num_labels=1`` model such
        as bge-reranker-v2-m3. Scores are therefore already in [0, 1] — do NOT
        apply sigmoid again here (doing so squashes the whole range into
        [0.5, 0.731] and destroys any absolute score threshold downstream).
        """
        if not results:
            return results

        pairs = [(query, r.document[:512]) for r in results]
        scores = self.model.predict(pairs)

        for result, score in zip(results, scores):
            result.score = float(score)

        reranked = sorted(results, key=lambda r: r.score, reverse=True)

        print(
            f"[RERANKER] Top-{min(top_k, len(reranked))} after reranking: "
            + ", ".join(
                f"{r.metadata.get('name', r.metadata.get('source_name', '?'))} ({r.score:.3f})"
                for r in reranked[:top_k]
            )
        )
        return reranked
