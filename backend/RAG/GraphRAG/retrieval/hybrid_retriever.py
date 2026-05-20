"""
Hybrid GraphRAG Retriever
==========================
Combines Vector Search + Graph Expansion into a single retrieval step.
Implements the GraphRAG architecture from schema_design.md:

1. Semantic Search (Vector DB) → top-K similar docs
2. Graph Expansion (Graph DB)  → subgraph for each result's stix_id
3. Merge & Deduplicate          → combined context
"""

from dataclasses import dataclass
from typing import Optional

from ..config import FINAL_TOP_K, VECTOR_TOP_K
from sentence_transformers import SentenceTransformer

from .graph_retriever import GraphRetriever, SubgraphResult
from .vector_retriever import VectorResult, VectorRetriever


@dataclass
class GraphRAGResult:
    """Combined result from vector search + graph expansion."""

    # Vector search results
    vector_results: list[VectorResult]
    # Graph expansion results (one subgraph per unique stix_id)
    graph_results: list[SubgraphResult]

    def get_context_text(self, max_length: int = 8000) -> str:
        """Format combined results as text for LLM context."""
        parts = []

        # Section 1: Semantic matches
        parts.append("=== Semantic Search Results ===")
        for i, vr in enumerate(self.vector_results[:FINAL_TOP_K], 1):
            entity_type = vr.metadata.get("entity_type", "Unknown")
            name = vr.metadata.get("name", vr.metadata.get("source_name", ""))
            parts.append(f"\n[{i}] ({entity_type}) {name} — score: {vr.score:.3f}")
            # Truncate document text
            doc_text = vr.document[:500].replace("\n", " ")
            parts.append(f"    {doc_text}")

        # Section 2: Graph context
        parts.append("\n\n=== Graph Context (Structured Relationships) ===")
        for sg in self.graph_results:
            text = sg.to_text()
            if text:
                parts.append(f"\n{text}")

        context = "\n".join(parts)

        # Truncate if too long
        if len(context) > max_length:
            context = context[:max_length] + "\n... [truncated]"

        return context


class HybridRetriever:
    """Orchestrates Vector + Graph retrieval for GraphRAG."""

    def __init__(self, embed_model: Optional[SentenceTransformer] = None):
        self.vector_retriever = VectorRetriever(embed_model=embed_model)
        self.graph_retriever = GraphRetriever()
        print("[HYBRID] GraphRAG retriever initialized")

    def close(self):
        self.graph_retriever.close()

    def retrieve(
        self,
        query: str,
        top_k: int = VECTOR_TOP_K,
        node_label_filter: Optional[str] = None,
    ) -> GraphRAGResult:
        """Execute the full GraphRAG retrieval pipeline.

        Args:
            query: The search query (should be in English for best results).
            top_k: Number of vector results to retrieve.
            node_label_filter: Optional filter for entity types.

        Returns:
            GraphRAGResult with combined vector + graph context.
        """
        print(f"[RETRIEVE] Query: {query[:80]}...")

        # ── Step 1: Vector search ─────────────────────────────────────────
        vector_results = self.vector_retriever.search_all(query, top_k=top_k)

        print(f"[RETRIEVE] Vector search: {len(vector_results)} results")
        for vr in vector_results[:3]:
            name = vr.metadata.get("name", vr.metadata.get("source_name", "?"))
            print(f"           → {name} (score: {vr.score:.3f})")

        # ── Step 2: Extract STIX IDs for graph expansion ──────────────────
        stix_ids_to_expand = set()

        for vr in vector_results:
            # For entity results, expand the entity itself
            if vr.metadata.get("entity_type") == "Node":
                stix_ids_to_expand.add(vr.stix_id)
            # For relationship results, expand both source and target
            elif vr.metadata.get("entity_type") == "Relationship":
                source_id = vr.metadata.get("source_id")
                target_id = vr.metadata.get("target_id")
                if source_id:
                    stix_ids_to_expand.add(source_id)
                if target_id:
                    stix_ids_to_expand.add(target_id)

        # Limit graph expansion to top results to control context size
        stix_ids_list = list(stix_ids_to_expand)[:FINAL_TOP_K]

        # ── Step 3: Graph expansion ───────────────────────────────────────
        graph_results = self.graph_retriever.expand(stix_ids_list)

        print(f"[RETRIEVE] Graph expansion: {len(graph_results)} subgraphs")
        for sg in graph_results:
            if sg.center_node:
                print(
                    f"           → {sg.center_node.name} "
                    f"({len(sg.neighbors)} neighbors, {len(sg.edges)} edges)"
                )

        return GraphRAGResult(
            vector_results=vector_results,
            graph_results=graph_results,
        )
