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

from FlagEmbedding import BGEM3FlagModel

from ..config import FINAL_TOP_K, RERANKER_MODEL, VECTOR_TOP_K
from .graph_retriever import GraphRetriever, SubgraphResult
from .reranker import Reranker
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


# Per-type score multipliers applied AFTER reranking. For incident analysis we
# want Technique/Subtechnique/Tactic nodes to anchor the mapping; Groups/Software/
# Campaigns are attribution context and were outranking the actual techniques
# (e.g. APT41 scoring above Phishing). They stay in the results (useful for the
# graph section) but are nudged below the techniques.
_TYPE_WEIGHTS = {
    "Technique": 1.2,
    "Subtechnique": 1.2,
    "Tactic": 1.1,
    "Group": 0.75,
    "Software": 0.8,
    "Campaign": 0.75,
}


class HybridRetriever:
    """Orchestrates Vector + Graph retrieval for GraphRAG."""

    def __init__(
        self,
        embed_model: Optional[BGEM3FlagModel] = None,
        reranker: Optional[Reranker] = None,
    ):
        self.vector_retriever = VectorRetriever(embed_model=embed_model)
        self.graph_retriever = GraphRetriever()
        self.reranker = reranker or Reranker(RERANKER_MODEL)
        print("[HYBRID] GraphRAG retriever initialized")

    def close(self):
        self.graph_retriever.close()
        # Also release the Qdrant HTTP connection (else a noisy RuntimeWarning
        # "Unable to close http connection" is emitted at shutdown).
        try:
            self.vector_retriever.client.close()
        except Exception:
            pass

    @staticmethod
    def _reweight_by_type(vector_results: list) -> list:
        """Down/up-weight reranked vector hits by node type, then re-sort so the
        graph-seed order (taken from this list) is technique-first."""
        for vr in vector_results:
            md = getattr(vr, "metadata", None) or {}
            w = _TYPE_WEIGHTS.get(md.get("node_label", ""))
            if w is not None:
                vr.score *= w
        vector_results.sort(key=lambda r: r.score, reverse=True)
        return vector_results

    def retrieve(
        self,
        query: str,
        top_k: int = VECTOR_TOP_K,
        node_label_filter: Optional[str] = None,
        expand_graph: bool = True,
    ) -> GraphRAGResult:
        """Execute the full GraphRAG retrieval pipeline.

        Args:
            query: The search query (should be in English for best results).
            top_k: Number of vector results to retrieve.
            node_label_filter: Optional filter for entity types.
            expand_graph: When False, skip Neo4j graph expansion and return
                vector + rerank results only (used by --ultrafast to drop the
                graph round-trips entirely).

        Returns:
            GraphRAGResult with combined vector + graph context.
        """
        print(f"[RETRIEVE] Query: {query[:80]}...")

        # ── Step 1: Vector search ─────────────────────────────────────────
        vector_results = self.vector_retriever.search_all(query, top_k=top_k)

        print(f"[RETRIEVE] Vector search: {len(vector_results)} results (pre-rerank)")

        # ── Step 1b: Rerank ───────────────────────────────────────────────
        vector_results = self.reranker.rerank(query, vector_results, top_k=top_k)

        # ── Step 1c: Re-weight by node type (techniques first) ─────────────
        vector_results = self._reweight_by_type(vector_results)

        # ── Ultrafast: vector + rerank only, no Neo4j graph expansion ──────
        if not expand_graph:
            return GraphRAGResult(vector_results=vector_results, graph_results=[])

        # ── Step 2: Extract STIX IDs for graph expansion (relevance order) ──
        # Use an ordered dedup list so graph seeds reflect reranker ranking,
        # not arbitrary set iteration order.
        seen_stix: set[str] = set()
        stix_ids_list: list[str] = []

        for vr in vector_results:
            if vr.metadata.get("entity_type") == "Node":
                if vr.stix_id not in seen_stix:
                    seen_stix.add(vr.stix_id)
                    stix_ids_list.append(vr.stix_id)
            elif vr.metadata.get("entity_type") == "Relationship":
                for sid in filter(
                    None,
                    [
                        vr.metadata.get("source_id"),
                        vr.metadata.get("target_id"),
                    ],
                ):
                    if sid not in seen_stix:
                        seen_stix.add(sid)
                        stix_ids_list.append(sid)
            if len(stix_ids_list) >= FINAL_TOP_K:
                break

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

    def retrieve_multi(
        self,
        queries: list[str],
        top_k: int = VECTOR_TOP_K,
        node_label_filter: Optional[str] = None,
    ) -> GraphRAGResult:
        """Execute hybrid retrieval for multiple queries and merge results.

        Runs ``retrieve()`` independently for each query then merges and
        deduplicates the results so the downstream context builder sees a
        single, unified view.

        Deduplication strategy:
        - **Vector results**: keyed by ``stix_id``; the entry with the
          highest score is kept.
        - **Graph results**: keyed by the center-node's ``stix_id``; the
          first encountered subgraph for each node is kept (they are
          structurally identical for the same seed node).

        Args:
            queries: List of English retrieval queries (original + rewrites).
            top_k:   Number of vector results to retrieve per query.
            node_label_filter: Optional entity-type filter passed to each
                               individual ``retrieve()`` call.

        Returns:
            A single merged ``GraphRAGResult`` ready for ``build_context()``.
        """
        if not queries:
            return GraphRAGResult(vector_results=[], graph_results=[])

        # Deduplicated accumulators
        # stix_id → VectorResult (highest score wins)
        seen_vector: dict[str, "VectorResult"] = {}
        # center stix_id → SubgraphResult (first encountered wins)
        seen_graph: dict[str, "SubgraphResult"] = {}

        for i, query in enumerate(queries, 1):
            print(f"[RETRIEVE-MULTI] Query {i}/{len(queries)}: {query[:80]}...")
            result = self.retrieve(
                query, top_k=top_k, node_label_filter=node_label_filter
            )

            # Merge vector results — keep highest score per stix_id
            for vr in result.vector_results:
                key = vr.stix_id
                if key not in seen_vector or vr.score > seen_vector[key].score:
                    seen_vector[key] = vr

            # Merge graph results — keep first subgraph per center node
            for sg in result.graph_results:
                center_id = sg.center_node.stix_id if sg.center_node else id(sg)
                if center_id not in seen_graph:
                    seen_graph[center_id] = sg

        # Re-sort merged vector results by score descending
        merged_vector = sorted(
            seen_vector.values(), key=lambda r: r.score, reverse=True
        )
        merged_graph = list(seen_graph.values())

        print(
            f"[RETRIEVE-MULTI] Merged: {len(merged_vector)} unique vector results, "
            f"{len(merged_graph)} unique subgraphs"
        )

        return GraphRAGResult(
            vector_results=merged_vector,
            graph_results=merged_graph,
        )

    def retrieve_multi_quota(
        self,
        queries: list[str],
        per_query_k: int = 3,
        top_k: int = VECTOR_TOP_K,
        max_vector: int = 15,
        max_graph: int = 8,
        node_label_filter: Optional[str] = None,
    ) -> "GraphRAGResult":
        """Multi-query retrieval with a PER-QUERY QUOTA.

        Unlike ``retrieve_multi`` (which merges everything by score and lets the
        final top-K trim silently drop a whole technique), this keeps each
        sub-query's top ``per_query_k`` results and ROUND-ROBIN interleaves them,
        so the first entries cover every sub-query. Use with a decomposed query
        list so each attacker technique is guaranteed representation in context.

        Args:
            queries:      Atomic sub-queries (e.g. one per technique).
            per_query_k:  How many top results to KEEP from each sub-query.
            top_k:        How many to retrieve per sub-query before keeping top-k.
            max_vector:   Hard cap on merged vector results (fits the LLM ctx).
            max_graph:    Hard cap on merged subgraphs.
        """
        if not queries:
            return GraphRAGResult(vector_results=[], graph_results=[])

        per_query_vectors: list[list] = []
        seen_graph: dict[str, "SubgraphResult"] = {}

        for i, query in enumerate(queries, 1):
            print(f"[RETRIEVE-QUOTA] Query {i}/{len(queries)}: {query[:80]}...")
            result = self.retrieve(
                query, top_k=top_k, node_label_filter=node_label_filter
            )
            per_query_vectors.append(result.vector_results[:per_query_k])
            for sg in result.graph_results:
                cid = sg.center_node.stix_id if sg.center_node else str(id(sg))
                if cid not in seen_graph:
                    seen_graph[cid] = sg

        # Round-robin interleave: query1[0], query2[0], …, query1[1], query2[1], …
        # so the top of the list spans all sub-queries (no technique gets dropped).
        merged_vector: list = []
        seen_vec: set[str] = set()
        depth = max((len(v) for v in per_query_vectors), default=0)
        for rank in range(depth):
            for vecs in per_query_vectors:
                if rank < len(vecs):
                    vr = vecs[rank]
                    if vr.stix_id not in seen_vec:
                        seen_vec.add(vr.stix_id)
                        merged_vector.append(vr)
            if len(merged_vector) >= max_vector:
                break
        merged_vector = merged_vector[:max_vector]
        merged_graph = list(seen_graph.values())[:max_graph]

        print(
            f"[RETRIEVE-QUOTA] {len(merged_vector)} vectors "
            f"(quota {per_query_k}/query), {len(merged_graph)} subgraphs "
            f"from {len(queries)} queries"
        )

        return GraphRAGResult(
            vector_results=merged_vector,
            graph_results=merged_graph,
        )
