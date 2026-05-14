"""
LangChain LCEL Chain for MITRE ATT&CK GraphRAG
================================================
Orchestrates the full cross-lingual GraphRAG pipeline:

    Thai Query → Translate → English Query → Vector Search → Graph Expand
    → Context Assembly → LLM Generation (Thai Response)

Uses LangChain Expression Language (LCEL) for composability.
"""

from typing import Optional
from sentence_transformers import SentenceTransformer

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage

from RAG.GraphRAG.config import (
    ANTHROPIC_API_KEY,
    LLM_MODEL,
    LLM_MAX_TOKENS,
    LLM_TEMPERATURE,
    EMBED_MODEL,
    VECTOR_TOP_K,
    sep,
)
from RAG.GraphRAG.pipeline.cross_lingual import CrossLingualLayer
from RAG.GraphRAG.pipeline.context_builder import build_context, build_generation_prompt
from RAG.GraphRAG.retrieval.hybrid_retriever import HybridRetriever


class GraphRAGChain:
    """Full GraphRAG pipeline with cross-lingual support."""

    def __init__(self, embed_model: Optional[SentenceTransformer] = None):
        sep("Initializing GraphRAG Chain")

        # Load embedding model (shared across components)
        if embed_model is None:
            print(f"[CHAIN] Loading embedding model: {EMBED_MODEL}")
            self.embed_model = SentenceTransformer(EMBED_MODEL)
        else:
            self.embed_model = embed_model

        # Initialize components
        self.translator = CrossLingualLayer()
        self.retriever = HybridRetriever(embed_model=self.embed_model)

        # LLM for generation
        if ANTHROPIC_API_KEY:
            self.llm = ChatAnthropic(
                model=LLM_MODEL,
                api_key=ANTHROPIC_API_KEY,
                temperature=LLM_TEMPERATURE,
                max_tokens=LLM_MAX_TOKENS,
            )
            print(f"[CHAIN] LLM: {LLM_MODEL}")
        else:
            self.llm = None
            print("[CHAIN] No LLM configured (ANTHROPIC_API_KEY not set)")

        print("[CHAIN] GraphRAG chain ready")

    def close(self):
        """Clean up resources."""
        self.retriever.close()

    def query(self, user_query: str, verbose: bool = True) -> str:
        """Execute the full GraphRAG pipeline.

        Args:
            user_query: The user's query (Thai or English).
            verbose: Print intermediate steps.

        Returns:
            The generated response (in Thai if query was Thai).
        """
        if verbose:
            sep("QUERY")
            print(f"  Input: {user_query}")

        # ── Step 1: Detect language & translate ───────────────────────────
        respond_in_thai = CrossLingualLayer.should_respond_in_thai(user_query)
        english_query = self.translator.translate_query(user_query)

        if verbose and english_query != user_query:
            print(f"  Translated: {english_query}")

        # ── Step 2: Hybrid retrieval (Vector + Graph) ─────────────────────
        graphrag_result = self.retriever.retrieve(english_query, top_k=VECTOR_TOP_K)

        # ── Step 3: Build context ─────────────────────────────────────────
        context = build_context(graphrag_result)

        if verbose:
            sep("CONTEXT PREVIEW")
            # Show first 500 chars of context
            print(context[:500] + "..." if len(context) > 500 else context)

        # ── Step 4: Generate response ─────────────────────────────────────
        if not self.llm:
            # No LLM → return raw context
            if verbose:
                sep("RAW CONTEXT (No LLM)")
            return context

        user_prompt = build_generation_prompt(
            context=context,
            original_query=user_query,
            english_query=english_query,
            respond_in_thai=respond_in_thai,
        )

        system_prompt = (
            CrossLingualLayer.get_system_prompt()
            if respond_in_thai
            else "You are a cybersecurity expert specializing in MITRE ATT&CK. Answer questions accurately using only the provided context."
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        if verbose:
            sep("GENERATING RESPONSE")

        response = self.llm.invoke(messages)
        answer = response.content

        if verbose:
            sep("ANSWER")
            print(answer)

            # Show sources
            sep("SOURCES")
            for i, vr in enumerate(graphrag_result.vector_results[:5], 1):
                name = vr.metadata.get("name", vr.metadata.get("source_name", "?"))
                entity_type = vr.metadata.get("node_label", vr.metadata.get("edge_label", "?"))
                attack_id = vr.metadata.get("attack_id", "")
                print(f"  [{i}] {entity_type}: {name} {f'({attack_id})' if attack_id else ''} — score: {vr.score:.3f}")

            sep()

        return answer

    def retrieve_only(self, user_query: str) -> str:
        """Run retrieval without LLM generation (for testing/debugging).

        Returns the assembled context text.
        """
        english_query = self.translator.translate_query(user_query)
        result = self.retriever.retrieve(english_query, top_k=VECTOR_TOP_K)
        return build_context(result)
