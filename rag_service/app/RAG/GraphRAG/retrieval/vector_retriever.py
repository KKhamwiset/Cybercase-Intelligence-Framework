"""
Qdrant Vector Retriever
==========================
Performs hybrid search (Dense + Sparse) over entity and relationship embeddings
using BGE-M3 and Qdrant's native RRF fusion.
"""

from dataclasses import dataclass
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Filter,
    FieldCondition,
    MatchValue,
    Prefetch,
    SparseVector,
    FusionQuery,
    Fusion,
)
from FlagEmbedding import BGEM3FlagModel

from ..config import (
    QDRANT_API_KEY,
    QDRANT_COLLECTION_ENTITIES,
    QDRANT_COLLECTION_RELATIONSHIPS,
    QDRANT_HOST,
    QDRANT_PORT,
    QDRANT_URL,
    EMBED_MODEL,
    USE_FP16,
    VECTOR_TOP_K,
    RRF_K,
    DENSE_WEIGHT,
    SPARSE_WEIGHT,
)


@dataclass
class VectorResult:
    """A single result from vector search."""

    document: str
    metadata: dict
    score: float
    stix_id: str


class VectorRetriever:
    """Retrieves semantically similar ATT&CK documents from Qdrant using Hybrid Search."""

    def __init__(self, embed_model: Optional[BGEM3FlagModel] = None):
        if QDRANT_URL:
            print(f"[VECTOR] Using Qdrant Cloud at {QDRANT_URL}")
            self.client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        elif QDRANT_HOST:
            print(f"[VECTOR] Using local Qdrant at {QDRANT_HOST}:{QDRANT_PORT}")
            self.client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, api_key=QDRANT_API_KEY)
        else:
            print(f"[VECTOR] Using in-memory Qdrant (dev only)")
            self.client = QdrantClient(":memory:")

        if embed_model is None:
            print(f"[VECTOR] Loading {EMBED_MODEL}...")
            self.embed_model = BGEM3FlagModel(EMBED_MODEL, use_fp16=USE_FP16)
        else:
            self.embed_model = embed_model
            
        try:
            ent_count = self.client.count(QDRANT_COLLECTION_ENTITIES).count
            rel_count = self.client.count(QDRANT_COLLECTION_RELATIONSHIPS).count
            print(f"[VECTOR] Entity collection: {ent_count} docs")
            print(f"[VECTOR] Relationship collection: {rel_count} docs")
        except Exception as e:
            print(f"[VECTOR] Warning: Could not get collection counts ({e})")

    def _search_hybrid(self, collection_name: str, query: str, 
                       top_k: int, qdrant_filter: Optional[Filter] = None) -> list[VectorResult]:
        """Hybrid search: dense + sparse with RRF fusion natively in Qdrant."""
        
        # 1. Embed query (dense + sparse)
        query_output = self.embed_model.encode(
            [query], return_dense=True, return_sparse=True, return_colbert_vecs=False
        )
        dense_vec = query_output["dense_vecs"][0].tolist()
        sparse_dict = query_output["lexical_weights"][0]
        
        sparse_indices = [int(k) for k in sparse_dict.keys()]
        sparse_values = list(sparse_dict.values())
        
        # We handle empty sparse vectors gracefully just in case
        if not sparse_indices:
            sparse_indices = [0]
            sparse_values = [0.0]

        # 2. Execute Qdrant native hybrid search
        results = self.client.query_points(
            collection_name=collection_name,
            prefetch=[
                Prefetch(
                    query=dense_vec,
                    using="dense",
                    limit=max(top_k * 5, 50),
                    filter=qdrant_filter,
                ),
                Prefetch(
                    query=SparseVector(
                        indices=sparse_indices,
                        values=sparse_values,
                    ),
                    using="sparse",
                    limit=max(top_k * 5, 50),
                    filter=qdrant_filter,
                ),
            ],
            query=FusionQuery(
                fusion=Fusion.RRF,
            ),
            limit=top_k,
            with_payload=True,
        )

        # 3. Parse results
        parsed = []
        for point in results.points:
            payload = point.payload or {}
            
            # Weighted score approximation (since Qdrant abstracts RRF)
            # Actually, Qdrant returns a fused score, we'll just pass it through.
            
            parsed.append(
                VectorResult(
                    document=payload.get("document", ""),
                    metadata=payload,
                    score=point.score,
                    stix_id=payload.get("stix_id", str(point.id)),
                )
            )
            
        return parsed

    def search_entities(
        self,
        query: str,
        top_k: int = VECTOR_TOP_K,
        node_label_filter: Optional[str] = None,
    ) -> list[VectorResult]:
        """Search entity descriptions semantically."""
        
        q_filter = None
        if node_label_filter:
            q_filter = Filter(
                must=[
                    FieldCondition(
                        key="node_label",
                        match=MatchValue(value=node_label_filter)
                    )
                ]
            )

        return self._search_hybrid(
            collection_name=QDRANT_COLLECTION_ENTITIES,
            query=query,
            top_k=top_k,
            qdrant_filter=q_filter,
        )

    def search_relationships(
        self,
        query: str,
        top_k: int = VECTOR_TOP_K,
        edge_label_filter: Optional[str] = None,
    ) -> list[VectorResult]:
        """Search relationship descriptions semantically."""
        
        q_filter = None
        if edge_label_filter:
            q_filter = Filter(
                must=[
                    FieldCondition(
                        key="edge_label",
                        match=MatchValue(value=edge_label_filter)
                    )
                ]
            )

        return self._search_hybrid(
            collection_name=QDRANT_COLLECTION_RELATIONSHIPS,
            query=query,
            top_k=top_k,
            qdrant_filter=q_filter,
        )

    @staticmethod
    def _normalize_scores(results: list["VectorResult"]) -> None:
        """Min-max normalize scores in-place so results from different
        collections are comparable on the same [0, 1] scale."""
        if len(results) < 2:
            return
        scores = [r.score for r in results]
        min_s, max_s = min(scores), max(scores)
        if max_s == min_s:
            return
        span = max_s - min_s
        for r in results:
            r.score = (r.score - min_s) / span

    def search_all(
        self,
        query: str,
        top_k: int = VECTOR_TOP_K,
    ) -> list[VectorResult]:
        """Search both entity and relationship collections.

        Entities receive the full top_k quota; relationships get half,
        biasing retrieval toward Technique/Tactic nodes for incident queries.
        Scores are min-max normalized within each collection before merging
        so RRF scores from different Qdrant collections are comparable.
        """
        entity_results = self.search_entities(query, top_k=top_k)
        rel_results = self.search_relationships(query, top_k=max(top_k // 2, 3))

        self._normalize_scores(entity_results)
        self._normalize_scores(rel_results)

        combined = entity_results + rel_results
        combined.sort(key=lambda r: r.score, reverse=True)
        return combined[:top_k]
