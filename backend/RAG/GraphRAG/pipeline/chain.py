"""
LangChain LCEL Chain for MITRE ATT&CK GraphRAG
================================================
Orchestrates the full cross-lingual GraphRAG pipeline:

    Thai Query
      → [Stage 1] Query Translate LLM  → English Query
      → Hybrid Retrieval (Vector + Graph)
      → Context Assembly
      → [Stage 2] Reasoning LLM        → Simplified English Narrative
      → [Stage 3] Translation LLM      → Thai Output  (skipped for English queries)

Each stage is a distinct LLM call with its own system prompt, ensuring clear
separation of concerns between jargon simplification and language translation.
"""

from typing import Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from sentence_transformers import SentenceTransformer

from ..config import (
    ANTHROPIC_API_KEY,
    EMBED_MODEL,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_TEMPERATURE,
    VECTOR_TOP_K,
    sep,
)
from ..retrieval.hybrid_retriever import GraphRAGResult, HybridRetriever
from .context_builder import build_context, build_generation_prompt
from .cross_lingual import CrossLingualLayer
from .router import QueryRouter


def _print_sources(graphrag_result: GraphRAGResult, top_n: int = 5) -> None:
    """Print the top retrieval sources for verbose/debug output."""
    sep("SOURCES")
    for i, vr in enumerate(graphrag_result.vector_results[:top_n], 1):
        name = vr.metadata.get("name", vr.metadata.get("source_name", "?"))
        entity_type = vr.metadata.get("node_label", vr.metadata.get("edge_label", "?"))
        attack_id = vr.metadata.get("attack_id", "")
        print(
            f"  [{i}] {entity_type}: {name} {f'({attack_id})' if attack_id else ''} — score: {vr.score:.3f}"
        )


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
        self.router = QueryRouter()

        # Stage 2: Reasoning LLM — simplifies jargon into plain English
        # Stage 3: Translation LLM — renders simplified English into Thai
        # Both use the same underlying model; prompts enforce the stage boundary.
        if ANTHROPIC_API_KEY:
            self.reasoning_llm = ChatAnthropic(  # type: ignore
                model=LLM_MODEL,
                api_key=ANTHROPIC_API_KEY,
                temperature=LLM_TEMPERATURE,
                max_tokens=LLM_MAX_TOKENS,
            )
            self.translation_llm = ChatAnthropic(  # type: ignore
                model=LLM_MODEL,
                api_key=ANTHROPIC_API_KEY,
                temperature=LLM_TEMPERATURE,
                max_tokens=LLM_MAX_TOKENS,
            )
            print(f"[CHAIN] Reasoning LLM : {LLM_MODEL}")
            print(f"[CHAIN] Translation LLM: {LLM_MODEL}")
        else:
            self.reasoning_llm = None
            self.translation_llm = None
            print("[CHAIN] No LLM configured (ANTHROPIC_API_KEY not set)")

        print("[CHAIN] GraphRAG chain ready")

    def close(self):
        """Clean up resources."""
        self.retriever.close()

    def query(self, user_query: str, verbose: bool = True) -> str:
        """Execute the full GraphRAG pipeline.

        Pipeline:
            1. Translate Thai query → English (query translate LLM)
            2. Hybrid retrieval  (Vector + Graph)
            3. Reasoning LLM    → simplified English narrative
            4. Translation LLM  → Thai output  (skipped for English queries)

        Args:
            user_query: The user's query (Thai or English).
            verbose: Print intermediate steps.

        Returns:
            Simplified English answer (English queries) or Thai answer (Thai queries).
        """
        if verbose:
            sep("QUERY")
            print(f"  Input: {user_query}")

        # ── Step 0: Route Query ───────────────────────────────────────────
        route = self.router.route_query(user_query)
        if verbose:
            print(f"  Route: {route}")

        if route == "GENERAL_EXPLANATION":
            if not self.reasoning_llm:
                return "Cannot answer general explanation without an LLM."

            system_prompt = "You are a cybersecurity expert. Provide a clear, concise, and accurate explanation for the user's query."
            if CrossLingualLayer.should_respond_in_thai(user_query):
                system_prompt += " Answer in Thai."

            if verbose:
                sep("GENERAL EXPLANATION")
                print("Skipping retrieval and using direct LLM knowledge...")

            response = self.reasoning_llm.invoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_query),
                ]
            )

            answer = str(response.content)
            if verbose:
                print(answer)
                sep()

            return answer

        # ── Step 1: Detect language & translate query ──────────────────────
        respond_in_thai = CrossLingualLayer.should_respond_in_thai(user_query)
        english_query = self.translator.translate_query(user_query)

        if verbose and english_query != user_query:
            print(f"  Translated: {english_query}")

        # ── Step 2: Hybrid retrieval (Vector + Graph) ──────────────────────
        graphrag_result = self.retriever.retrieve(english_query, top_k=VECTOR_TOP_K)

        # ── Step 3: Build context ──────────────────────────────────────────
        context = build_context(graphrag_result)

        if verbose:
            sep("CONTEXT PREVIEW")
            print(context[:500] + "..." if len(context) > 500 else context)

        # ── Step 4: Reasoning LLM — simplified English ────────────────────
        if not self.reasoning_llm:
            # No LLM configured → return raw context
            if verbose:
                sep("RAW CONTEXT (No LLM)")
            return context

        reasoning_user_prompt = build_generation_prompt(
            context=context,
            original_query=user_query,
            english_query=english_query,
            respond_in_thai=False,  # Reasoning LLM always outputs English
        )

        if verbose:
            sep("STAGE 2 — REASONING LLM (English simplification)")

        reasoning_response = self.reasoning_llm.invoke(
            [
                SystemMessage(content=CrossLingualLayer.get_reasoning_system_prompt()),
                HumanMessage(content=reasoning_user_prompt),
            ]
        )
        simplified_english = str(reasoning_response.content)

        if verbose:
            sep("SIMPLIFIED ENGLISH NARRATIVE")
            print(simplified_english)

        # ── Step 5: Translation LLM — Thai output (Thai queries only) ─────
        if not respond_in_thai:
            # English query → return simplified English directly
            if verbose:
                sep("ANSWER (English)")
                print(simplified_english)
                _print_sources(graphrag_result)
                sep()
            return simplified_english

        if not self.translation_llm:
            return simplified_english

        if verbose:
            sep("STAGE 3 — TRANSLATION LLM (English → Thai)")

        translation_response = self.translation_llm.invoke(
            [
                SystemMessage(
                    content=CrossLingualLayer.get_translation_system_prompt()
                ),
                HumanMessage(content=simplified_english),
            ]
        )
        thai_answer = str(translation_response.content)

        if verbose:
            sep("ANSWER (Thai)")
            print(thai_answer)
            _print_sources(graphrag_result)
            sep()

        return thai_answer

    def retrieve_only(self, user_query: str) -> str:
        """Run retrieval without LLM generation (for testing/debugging).

        Returns the assembled context text.
        """
        english_query = self.translator.translate_query(user_query)
        result = self.retriever.retrieve(english_query, top_k=VECTOR_TOP_K)
        return build_context(result)
