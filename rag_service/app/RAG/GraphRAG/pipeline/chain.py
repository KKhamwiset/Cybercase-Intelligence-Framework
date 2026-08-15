"""
LangChain LCEL Chain for MITRE ATT&CK GraphRAG  —  EVALUATION ONLY
==================================================================
NOT a production path. ``POST /query`` always routes to ``GraphRAGAgent``
(agent_graph.py); nothing in ``app/`` imports this module, and it is
deliberately absent from ``pipeline/__init__.py`` so importing the package
does not drag it in.

It survives because ``evaluation/eval_runner.py --mode generation`` and
``evaluation/crosslingual_benchmark.py`` still build a ``GraphRAGChain``
directly, and they are the baseline the agent path is measured against.
Retiring it means porting those two onto ``GraphRAGAgent`` first — which
would move the eval numbers, so it is a deliberate decision, not cleanup.

This is also the only remaining caller of the translate-then-retrieve flow
(``CrossLingualLayer.translate_query`` → ``build_retrieval_queries`` →
``DUAL_QUERY_RETRIEVAL``). The agent dropped input translation entirely:
BGE-M3 is multilingual, so it retrieves on the Thai text as-is.

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

from dataclasses import dataclass
from typing import Optional

from FlagEmbedding import BGEM3FlagModel
from langchain_core.messages import HumanMessage, SystemMessage

from ..config import (
    EMBED_MODEL,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_TEMPERATURE,
    LOCAL_LLM_MODEL,
    OLLAMA_BASE_URL,
    USE_FP16,
    VECTOR_TOP_K,
    sep,
)
from ..llm_content import require_message_text
from ..llm_provider import (
    CoreLlmConfigurationError,
    create_core_chat_model,
    resolve_core_llm_target,
)
from ..retrieval.hybrid_retriever import GraphRAGResult, HybridRetriever
from .context_builder import build_context, build_generation_prompt
from .cross_lingual import CrossLingualLayer, build_retrieval_queries
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


@dataclass
class ChainResponse:
    """Answer plus the retrieval artifacts behind it (for the MITRE table)."""

    answer: str
    context: str = ""
    graphrag_result: Optional[GraphRAGResult] = None


class GraphRAGChain:
    """Full GraphRAG pipeline with cross-lingual support."""

    def __init__(self, embed_model: Optional[BGEM3FlagModel] = None,
                 use_local: bool = False):
        sep("Initializing GraphRAG Chain")
        self.use_local = use_local

        # Load embedding model (shared across components)
        if embed_model is None:
            print(f"[CHAIN] Loading embedding model: {EMBED_MODEL}")
            self.embed_model = BGEM3FlagModel(EMBED_MODEL, use_fp16=USE_FP16)
        else:
            self.embed_model = embed_model

        # Initialize components — propagate use_local so the whole chain is local.
        self.translator = CrossLingualLayer(use_local=use_local)
        self.retriever = HybridRetriever(embed_model=self.embed_model)
        self.router = QueryRouter(use_local=use_local)

        # Stage 2: Reasoning LLM — simplifies jargon into plain English
        # Stage 3: Translation LLM — renders simplified English into Thai
        # Both use the same underlying model; prompts enforce the stage boundary.
        if use_local:
            from langchain_ollama import ChatOllama

            # reasoning=False disables Qwen3.5 thinking, so no <think> blocks leak
            # into the answer or the downstream Thai translation stage.
            self.reasoning_llm = ChatOllama(
                model=LOCAL_LLM_MODEL,
                base_url=OLLAMA_BASE_URL,
                temperature=LLM_TEMPERATURE,
                num_predict=LLM_MAX_TOKENS,
                reasoning=False,
            )
            self.translation_llm = ChatOllama(
                model=LOCAL_LLM_MODEL,
                base_url=OLLAMA_BASE_URL,
                temperature=LLM_TEMPERATURE,
                num_predict=LLM_MAX_TOKENS,
                reasoning=False,
            )
            print(f"[CHAIN] Reasoning LLM : {LOCAL_LLM_MODEL} (local)")
            print(f"[CHAIN] Translation LLM: {LOCAL_LLM_MODEL} (local)")
        else:
            try:
                target = resolve_core_llm_target(LLM_MODEL)
                self.reasoning_llm = create_core_chat_model(
                    anthropic_model=LLM_MODEL,
                    temperature=LLM_TEMPERATURE,
                    max_tokens=LLM_MAX_TOKENS,
                )
                self.translation_llm = create_core_chat_model(
                    anthropic_model=LLM_MODEL,
                    temperature=LLM_TEMPERATURE,
                    max_tokens=LLM_MAX_TOKENS,
                )
                print(
                    f"[CHAIN] Reasoning LLM : {target.model} ({target.provider})"
                )
                print(
                    f"[CHAIN] Translation LLM: {target.model} ({target.provider})"
                )
            except CoreLlmConfigurationError as exc:
                self.reasoning_llm = None
                self.translation_llm = None
                print(f"[CHAIN] No cloud LLM configured: {exc}")

        print("[CHAIN] GraphRAG chain ready")

    def close(self):
        """Clean up resources."""
        self.retriever.close()

    def query(self, user_query: str, verbose: bool = True) -> str:
        """Execute the full GraphRAG pipeline and return the answer text.

        Thin wrapper over ``query_with_details`` for callers (CLI, eval) that
        only need the answer string.
        """
        return self.query_with_details(user_query, verbose=verbose).answer

    def query_with_details(
        self,
        user_query: str,
        verbose: bool = True,
    ) -> ChainResponse:
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
            ``ChainResponse`` with the answer (simplified English for English
            queries, Thai otherwise) plus the retrieval context/result behind
            it (empty for the general-explanation route, which skips retrieval).
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
                return ChainResponse(
                    answer="Cannot answer general explanation without an LLM."
                )

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

            answer = require_message_text(response, operation="general explanation")
            if verbose:
                print(answer)
                sep()

            return ChainResponse(answer=answer)

        # ── Step 1: Detect language & translate query ──────────────────────
        respond_in_thai = CrossLingualLayer.should_respond_in_thai(user_query)
        english_query = self.translator.translate_query(user_query)

        if verbose and english_query != user_query:
            print(f"  Translated: {english_query}")

        # ── Step 2: Hybrid retrieval (Vector + Graph) ──────────────────────
        # Dual-query: English translation + original Thai query in parallel
        queries = build_retrieval_queries(user_query, english_query)
        graphrag_result = self.retriever.retrieve_multi(queries, top_k=VECTOR_TOP_K)

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
            return ChainResponse(
                answer=context, context=context, graphrag_result=graphrag_result
            )

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
        simplified_english = require_message_text(
            reasoning_response,
            operation="English answer generation",
        )

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
            return ChainResponse(
                answer=simplified_english,
                context=context,
                graphrag_result=graphrag_result,
            )

        if not self.translation_llm:
            return ChainResponse(
                answer=simplified_english,
                context=context,
                graphrag_result=graphrag_result,
            )

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
        thai_answer = require_message_text(
            translation_response,
            operation="Thai answer translation",
        )

        if verbose:
            sep("ANSWER (Thai)")
            print(thai_answer)
            _print_sources(graphrag_result)
            sep()

        return ChainResponse(
            answer=thai_answer, context=context, graphrag_result=graphrag_result
        )

    def retrieve_only(self, user_query: str) -> str:
        """Run retrieval without LLM generation (for testing/debugging).

        Returns the assembled context text.
        """
        english_query = self.translator.translate_query(user_query)
        queries = build_retrieval_queries(user_query, english_query)
        result = self.retriever.retrieve_multi(queries, top_k=VECTOR_TOP_K)
        return build_context(result)
