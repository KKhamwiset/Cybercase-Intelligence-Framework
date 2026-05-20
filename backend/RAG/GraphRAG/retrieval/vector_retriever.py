"""
ChromaDB Vector Retriever
==========================
Performs semantic search over entity and relationship embeddings.
Uses E5 query prefix for optimal retrieval with multilingual-e5-large.
"""

from dataclasses import dataclass
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer

from ..config import (
    CHROMA_API_KEY,
    CHROMA_COLLECTION_ENTITIES,
    CHROMA_COLLECTION_RELATIONSHIPS,
    CHROMA_DIR,
    CHROMA_HOST,
    CHROMA_PORT,
    CHROMA_SSL,
    E5_QUERY_PREFIX,
    EMBED_MODEL,
    VECTOR_TOP_K,
)
from ..models import AttackEntity, AttackRelationship


@dataclass
class VectorResult:
    """A single result from vector search."""

    document: str
    metadata: dict
    score: float
    stix_id: str


class VectorRetriever:
    """Retrieves semantically similar ATT&CK documents from ChromaDB."""

    def __init__(self, embed_model: Optional[SentenceTransformer] = None):
        # Choose between Remote (HttpClient) and Local (PersistentClient)
        if CHROMA_HOST:
            print(
                f"[VECTOR] Using Remote ChromaDB at {CHROMA_HOST}:{CHROMA_PORT} (SSL: {CHROMA_SSL})"
            )
            self.client = chromadb.HttpClient(
                host=CHROMA_HOST,
                port=CHROMA_PORT,
                ssl=CHROMA_SSL,
                headers={"Authorization": f"Bearer {CHROMA_API_KEY}"}
                if CHROMA_API_KEY
                else None,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        else:
            print(f"[VECTOR] Using Local ChromaDB at {CHROMA_DIR}")
            self.client = chromadb.PersistentClient(
                path=str(CHROMA_DIR),
                settings=ChromaSettings(anonymized_telemetry=False),
            )

        if embed_model is None:
            print(f"[VECTOR] Loading {EMBED_MODEL}...")
            self.embed_model = SentenceTransformer(EMBED_MODEL)
        else:
            self.embed_model = embed_model

        self.entity_collection = self.client.get_collection(CHROMA_COLLECTION_ENTITIES)
        self.rel_collection = self.client.get_collection(
            CHROMA_COLLECTION_RELATIONSHIPS
        )

        print(f"[VECTOR] Entity collection: {self.entity_collection.count()} docs")
        print(f"[VECTOR] Relationship collection: {self.rel_collection.count()} docs")

    def _embed_query(self, query: str) -> list[float]:
        """Embed a query with E5 query prefix."""
        prefixed = f"{E5_QUERY_PREFIX}{query}"
        embedding = self.embed_model.encode(prefixed, normalize_embeddings=True)
        return embedding.tolist()

    def search_entities(
        self,
        query: str,
        top_k: int = VECTOR_TOP_K,
        node_label_filter: Optional[str] = None,
    ) -> list[VectorResult]:
        """Search entity descriptions semantically.

        Args:
            query: The search query (in English for best results).
            top_k: Number of results to return.
            node_label_filter: Optional filter by node type (e.g., "Technique").
        """
        query_embedding = self._embed_query(query)

        where_filter = None
        if node_label_filter:
            where_filter = {"node_label": node_label_filter}

        results = self.entity_collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        return self._parse_results(results)

    def search_relationships(
        self,
        query: str,
        top_k: int = VECTOR_TOP_K,
        edge_label_filter: Optional[str] = None,
    ) -> list[VectorResult]:
        """Search relationship descriptions semantically.

        Args:
            query: The search query (in English for best results).
            top_k: Number of results to return.
            edge_label_filter: Optional filter by edge type (e.g., "USES").
        """
        query_embedding = self._embed_query(query)

        where_filter = None
        if edge_label_filter:
            where_filter = {"edge_label": edge_label_filter}

        results = self.rel_collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        return self._parse_results(results)

    def search_all(
        self,
        query: str,
        top_k: int = VECTOR_TOP_K,
    ) -> list[VectorResult]:
        """Search both entities and relationships, returning merged results sorted by score."""
        entity_results = self.search_entities(query, top_k=top_k)
        rel_results = self.search_relationships(query, top_k=top_k)

        combined = entity_results + rel_results
        # Sort by score (higher is better — we convert distance to similarity)
        combined.sort(key=lambda r: r.score, reverse=True)

        return combined[:top_k]

    def _parse_results(self, raw_results: dict) -> list[VectorResult]:
        """Parse ChromaDB query results into VectorResult objects."""
        results = []

        if not raw_results or not raw_results.get("ids"):
            return results

        ids = raw_results["ids"][0]
        documents = raw_results["documents"][0]
        metadatas = raw_results["metadatas"][0]
        distances = raw_results["distances"][0]

        for doc_id, doc, meta, dist in zip(ids, documents, metadatas, distances):
            # ChromaDB returns L2 distance for cosine space → similarity = 1 - distance
            # For cosine space, distance is already (1 - cosine_similarity) * 2
            similarity = max(0.0, 1.0 - dist)

            results.append(
                VectorResult(
                    document=doc,
                    metadata=meta,
                    score=similarity,
                    stix_id=doc_id,
                )
            )

        return results
