"""
LangGraph Agentic RAG Pipeline
================================
Replaces the linear LCEL chain with a stateful graph that supports:

   1. **Decomposed Multi-Query Retrieval** — the incident is broken into atomic
      per-technique sub-queries (in the incident's own language; no English
      translation — BGE-M3 is multilingual) plus any rewrites, then retrieved
      via retrieve_multi_quota() so every technique is guaranteed representation.
   2. **Self-Reflection Loop** — the evaluator judges context sufficiency. On
      INSUFFICIENT the agent rewrites the query itself (BROADEN_SEARCH) and
      re-retrieves, without ever pausing to ask the user anything.

 The graph flow:

     input → route → prepare → retrieve_quota → evaluate_context
                   (lang detect)                      │
                                        ┌─ sufficient │  insufficient
                                        ↓             ↓
                                   reasoning     broaden_search
                                        ↓             ↓
                               translate_output  retrieve_quota (loop)
                                        ↓      (max 2 broaden iterations,
                                     output     then answer with what we have)

 The pipeline never pauses for user input — ``query()`` always returns a
 completed answer. Interactive clarification is owned by the caller
 (backend case-analysis workflow), not by this agent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, TypedDict

from FlagEmbedding import BGEM3FlagModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from ..config import (
    EMBED_MODEL,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_TEMPERATURE,
    SINGLE_CALL_GENERATION,
    ULTRAFAST_MAX_TOKENS,
    ULTRAFAST_TOP_K,
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
from .cross_lingual import CrossLingualLayer
from .query_decomposer import QueryDecomposer
from .evaluator import (
    VERDICT_INSUFFICIENT,
    VERDICT_SUFFICIENT,
    ContextEvaluator,
    EvaluationResult,
)
from .query_sanitizer import sanitize_retrieval_query
from .router import QueryRouter


# ──────────────────────────────────────────────────────────────────────────────
# State definition
# ──────────────────────────────────────────────────────────────────────────────
class AgentState(TypedDict, total=False):
    """Shared state flowing through every node in the graph."""

    # ── Inputs ────────────────────────────────────────────────────────────
    original_query: str  # The user's raw input
    verbose: bool

    # ── Routing ───────────────────────────────────────────────────────────
    route: str  # GENERAL_EXPLANATION | INCIDENT_ANALYSIS

    # ── Translation ───────────────────────────────────────────────────────
    english_query: str  # Translated (or original if already English)
    respond_in_thai: bool
    answer_is_final: bool  # single-call generation already produced Thai

    # ── Retrieval ─────────────────────────────────────────────────────────
    graphrag_result: Any  # GraphRAGResult
    context: str  # Assembled context text
    rewritten_queries: list  # MITRE-aligned rewrites produced by BROADEN_SEARCH

    # ── Evaluation ────────────────────────────────────────────────────────
    evaluation: Any  # EvaluationResult
    broaden_count: int  # Iterations of BROADEN_SEARCH so far

    # ── Fallback Strategies ───────────────────────────────────────────────
    strategy: str  # BROADEN_SEARCH | PARTIAL_ANSWER | ACKNOWLEDGE_LIMIT
    gap_warning: str
    acknowledgement_message: str

    # ── Output ────────────────────────────────────────────────────────────
    answer: str  # Final answer


# ──────────────────────────────────────────────────────────────────────────────
# Structured response — works for both API and CLI
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class AgentResponse:
    """Structured response returned by ``GraphRAGAgent.query()``.

    ``status`` is always ``"completed"`` — the agent never pauses. The field is
    retained so API consumers keep a stable response shape.
    """

    status: str = "completed"
    answer: str = ""
    context: str = ""
    graphrag_result: Any = None

    def to_dict(self) -> dict:
        """Serialize for JSON API responses."""
        return {"status": self.status, "answer": self.answer}


# ──────────────────────────────────────────────────────────────────────────────
# Budget for the self-reflection (BROADEN_SEARCH) loop
# ──────────────────────────────────────────────────────────────────────────────
MAX_BROADEN_RETRIES = 2  # Broaden iterations before answering with what we have


# ──────────────────────────────────────────────────────────────────────────────
# The Agent
# ──────────────────────────────────────────────────────────────────────────────
class GraphRAGAgent:
    """Agentic RAG pipeline built on LangGraph.

    Drop-in companion for ``GraphRAGChain`` — offers the same ``.query()``
    interface but with query decomposition and a self-reflection loop.
    """

    def __init__(
        self,
        embed_model: Optional[BGEM3FlagModel] = None,
        reranker: Optional[Any] = None,
    ) -> None:
        sep("Initializing GraphRAG Agent (LangGraph)")

        self._ultrafast_llm = None  # lazily built on first query_ultrafast call

        # Shared embedding model
        if embed_model is None:
            print(f"[AGENT] Loading embedding model: {EMBED_MODEL}")
            self.embed_model = BGEM3FlagModel(EMBED_MODEL, use_fp16=USE_FP16)
        else:
            self.embed_model = embed_model

        # No input-translation component: retrieval is native-language (BGE-M3).
        # CrossLingualLayer is still used, but only via its @staticmethods
        # (language detect + system prompts), so no instance is needed.
        self.retriever = HybridRetriever(
            embed_model=self.embed_model, reranker=reranker
        )
        self.router = QueryRouter()
        self.evaluator = ContextEvaluator()
        self.decomposer = QueryDecomposer()

        # Both LLMs are the same model; the system prompt draws the stage
        # boundary. reasoning_llm and translation_llm are set (and cleared)
        # together, so downstream None-checks only ever see both or neither.
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
            print(f"[AGENT] Reasoning LLM : {target.model} ({target.provider})")
            print(f"[AGENT] Translation LLM: {target.model} ({target.provider})")
        except CoreLlmConfigurationError as exc:
            self.reasoning_llm = None
            self.translation_llm = None
            print(f"[AGENT] No cloud LLM configured: {exc}")

        print(
            "[AGENT] Generation    : "
            + (
                "single-call (Thai direct, variant C)"
                if SINGLE_CALL_GENERATION
                else "two-stage (reason EN -> translate TH)"
            )
        )

        # Build the LangGraph
        self.graph = self._build_graph()
        print("[AGENT] LangGraph compiled ✓")
        print("[AGENT] GraphRAG Agent ready")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def close(self) -> None:
        """Clean up resources."""
        self.retriever.close()

    def retrieve_only(self, user_query: str) -> str:
        """Execute only the retrieval portion of the pipeline.

        Mirrors ``_node_retrieve``: decompose into atomic native-language
        sub-queries (no translation) then quota-retrieve.
        """
        sub_queries = self.decomposer.decompose(incident=user_query, verbose=False)
        all_queries = [user_query] + [q for q in sub_queries if q and q != user_query]
        rag_result = self.retriever.retrieve_multi_quota(
            all_queries, per_query_k=3, top_k=VECTOR_TOP_K, max_vector=15, max_graph=8
        )
        return build_context(rag_result, max_vector=15, max_graph=8)

    def query_fast(self, user_query: str, verbose: bool = True) -> AgentResponse:
        """Minimal-latency path — single retrieve → one combined reason+answer call.

        Deliberately strips everything the full agent does for robustness, trading
        coverage for ~2-3x lower latency:
          • NO routing            (always treats input as an incident)
          • NO query decomposition / per-query quota → ONE hybrid retrieve on the
            raw query (BGE-M3 is multilingual, so no input translation either)
          • NO context evaluator / self-reflection loop / broaden
          • NO separate translation stage — the reasoning LLM answers DIRECTLY in
            the response language (reasoning + translation folded into one call)

        Use when speed matters more than maximal technique coverage.
        """
        if not self.reasoning_llm:
            return AgentResponse(
                status="completed",
                answer="Cannot generate answer because the selected CORE_LLM_PROVIDER key is not configured.",
            )

        respond_in_thai = CrossLingualLayer.should_respond_in_thai(user_query)

        if verbose:
            sep("AGENT — FAST MODE (single retrieve → direct answer)")
            print(f"  Respond in Thai: {respond_in_thai}")

        # 1. Single hybrid retrieve on the raw query (vector + rerank + graph).
        graphrag_result = self.retriever.retrieve(user_query, top_k=VECTOR_TOP_K)
        context = build_context(graphrag_result)

        if verbose:
            sep("CONTEXT PREVIEW")
            print(context[:500] + "..." if len(context) > 500 else context)

        # 2. One combined reasoning+answer call, output directly in the target language.
        prompt = build_generation_prompt(
            context=context,
            original_query=user_query,
            english_query=user_query,
            respond_in_thai=respond_in_thai,
        )
        response = self.reasoning_llm.invoke(
            [
                SystemMessage(
                    content=CrossLingualLayer.get_fast_system_prompt(respond_in_thai)
                ),
                HumanMessage(content=prompt),
            ]
        )
        answer = require_message_text(response, operation="fast answer generation")

        if verbose:
            sep("ANSWER (FAST)")
            print(answer)
            sep()

        return AgentResponse(
            status="completed",
            answer=answer,
            context=context,
            graphrag_result=graphrag_result,
        )

    def _get_ultrafast_llm(self):
        """Lazily build (and cache) a low-output-token LLM for ultrafast mode."""
        if self._ultrafast_llm is not None:
            return self._ultrafast_llm

        try:
            self._ultrafast_llm = create_core_chat_model(
                anthropic_model=LLM_MODEL,
                temperature=LLM_TEMPERATURE,
                max_tokens=ULTRAFAST_MAX_TOKENS,
            )
        except CoreLlmConfigurationError as exc:
            print(f"[AGENT] Ultrafast cloud LLM unavailable: {exc}")
        return self._ultrafast_llm

    def query_ultrafast(self, user_query: str, verbose: bool = True) -> AgentResponse:
        """Absolute-minimum-latency path. On top of everything ``query_fast`` strips:
          • NO graph expansion — vector search + rerank ONLY (skips Neo4j entirely)
          • smaller top-K + compact context
          • terse output — capped ``max_tokens`` + a brief incident→MITRE mapping
            prompt (no 4-section narrative), since output tokens dominate latency

        Returns a short technique mapping in the query's language.
        """
        llm = self._get_ultrafast_llm()
        if not llm:
            return AgentResponse(
                status="completed",
                answer="Cannot generate answer because the selected CORE_LLM_PROVIDER key is not configured.",
            )

        respond_in_thai = CrossLingualLayer.should_respond_in_thai(user_query)

        if verbose:
            sep("AGENT — ULTRAFAST (vector-only retrieve → terse answer)")
            print(f"  Respond in Thai: {respond_in_thai}")

        # 1. Vector + rerank only (no graph), small top-K.
        rag_result = self.retriever.retrieve(
            user_query, top_k=ULTRAFAST_TOP_K, expand_graph=False
        )
        context = build_context(rag_result, max_vector=ULTRAFAST_TOP_K, max_graph=0)

        # 2. One terse LLM call (compact prompt — skip the heavy generation template).
        user_prompt = f"{context}\n\n{'=' * 60}\nQUESTION\n{'=' * 60}\n{user_query}"
        response = llm.invoke(
            [
                SystemMessage(
                    content=CrossLingualLayer.get_ultrafast_system_prompt(respond_in_thai)
                ),
                HumanMessage(content=user_prompt),
            ]
        )
        answer = require_message_text(response, operation="ultrafast answer generation")

        if verbose:
            sep("ANSWER (ULTRAFAST)")
            print(answer)
            sep()

        return AgentResponse(
            status="completed",
            answer=answer,
            context=context,
            graphrag_result=rag_result,
        )

    def query(self, user_query: str, verbose: bool = True) -> AgentResponse:
        """Execute the agentic RAG pipeline.

        The graph always runs to completion — when the context is judged
        insufficient the agent rewrites the query and re-retrieves itself
        (bounded by ``MAX_BROADEN_RETRIES``) rather than pausing to ask the
        user. Callers that want interactive clarification own that loop and
        should re-invoke ``query()`` with the enriched incident text.

        Args:
            user_query: The user's query (Thai or English).
            verbose: Print intermediate steps.

        Returns:
            ``AgentResponse`` with ``status="completed"``.
        """
        initial_state: AgentState = {
            "original_query": user_query,
            "verbose": verbose,
            "broaden_count": 0,
            "rewritten_queries": [],
            "strategy": "",
            "gap_warning": "",
            "acknowledgement_message": "",
        }

        result = self.graph.invoke(initial_state)

        return AgentResponse(
            status="completed",
            answer=result.get("answer", ""),
            context=result.get("context", ""),
            graphrag_result=result.get("graphrag_result"),
        )

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------
    def _build_graph(self) -> Any:
        """Construct and compile the LangGraph state machine."""

        graph = StateGraph(AgentState)

        # ── Register nodes ────────────────────────────────────────────
        graph.add_node("route_query", self._node_route_query)
        graph.add_node("general_explanation", self._node_general_explanation)
        graph.add_node("prepare", self._node_prepare)
        graph.add_node("retrieve", self._node_retrieve)
        graph.add_node("evaluate_context", self._node_evaluate_context)
        graph.add_node("broaden_search", self._node_broaden_search)
        graph.add_node("reasoning", self._node_reasoning)
        graph.add_node("translate_output", self._node_translate_output)

        # ── Entry point ───────────────────────────────────────────────
        graph.set_entry_point("route_query")

        # ── Edges ─────────────────────────────────────────────────────
        graph.add_conditional_edges(
            "route_query",
            self._edge_after_route,
            {
                "general": "general_explanation",
                "incident": "prepare",
            },
        )

        graph.add_edge("general_explanation", END)

        # Prepare (language detect) → Multi-Query Retrieval → Evaluation
        graph.add_edge("prepare", "retrieve")
        graph.add_edge("retrieve", "evaluate_context")

        # Evaluation decides: sufficient → reason, insufficient → self-rewrite and loop
        graph.add_conditional_edges(
            "evaluate_context",
            self._edge_after_evaluation,
            {
                "sufficient": "reasoning",
                "broaden": "broaden_search",
            },
        )

        graph.add_edge("broaden_search", "retrieve")

        # Reasoning → optional translation → END
        graph.add_conditional_edges(
            "reasoning",
            self._edge_after_reasoning,
            {
                "translate": "translate_output",
                "done": END,
            },
        )

        graph.add_edge("translate_output", END)

        return graph.compile()

    # ------------------------------------------------------------------
    # Node implementations
    # ------------------------------------------------------------------
    def _node_route_query(self, state: AgentState) -> dict:
        """Classify the query as GENERAL_EXPLANATION or INCIDENT_ANALYSIS."""
        query = state.get("original_query", "")
        verbose = state.get("verbose", True)

        if verbose:
            sep("AGENT — ROUTING")
            print(f"  Input: {query}")

        route = self.router.route_query(query)

        if verbose:
            print(f"  Route: {route}")

        return {"route": route}

    def _node_general_explanation(self, state: AgentState) -> dict:
        """Handle general knowledge questions without retrieval."""
        query = state.get("original_query", "")
        verbose = state.get("verbose", True)

        if not self.reasoning_llm:
            return {"answer": "Cannot answer general explanation without an LLM."}

        system_prompt = (
            "You are a cybersecurity expert. Provide a clear, concise, "
            "and accurate explanation for the user's query."
        )
        if CrossLingualLayer.should_respond_in_thai(query):
            system_prompt += " Answer in Thai."

        if verbose:
            sep("AGENT — GENERAL EXPLANATION")
            print("  Skipping retrieval — using direct LLM knowledge...")

        response = self.reasoning_llm.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=query),
            ]
        )

        answer = require_message_text(response, operation="general explanation")

        if verbose:
            print(answer)
            sep()

        return {"answer": answer}

    def _node_prepare(self, state: AgentState) -> dict:
        """Detect the response language. NO input translation.

        BGE-M3 is multilingual, so retrieval runs on the native-language query —
        the decomposer (in ``_node_retrieve``) breaks the Thai incident into
        atomic Thai sub-queries that match the English MITRE corpus directly. This
        replaces the old Thai→English dual-query.

        ``english_query`` is kept as a state key for backward-compat but now simply
        mirrors the original (native) query, so downstream nodes (evaluator,
        reasoning, query-merger) that key off it keep a stable handle.
        """
        query = state.get("original_query", "")
        verbose = state.get("verbose", True)

        respond_in_thai = CrossLingualLayer.should_respond_in_thai(query)

        if verbose:
            print(f"  Respond in Thai: {respond_in_thai} (no input translation)")

        return {
            "english_query": query,
            "respond_in_thai": respond_in_thai,
        }

    def _node_retrieve(self, state: AgentState) -> dict:
        """Execute decomposed multi-query hybrid retrieval (Vector + Graph).

        The incident is decomposed into atomic per-technique sub-queries (in the
        incident's own language — no English translation; BGE-M3 matches Thai
        against the English MITRE corpus directly). Any MITRE-aligned follow-up
        rewrites are appended. All sub-queries are retrieved together via
        ``retrieve_multi_quota()``, which round-robin interleaves a per-query
        quota so every technique is guaranteed representation in the context —
        a plain score-merge would silently drop a low-scoring technique.
        """
        original_query = state.get("original_query", "")
        rewritten_queries: list = list(state.get("rewritten_queries") or [])
        verbose = state.get("verbose", True)

        # Full original query goes FIRST as a holistic channel — it preserves the
        # incident's full context (the report path proved this gives better
        # technique coverage), then the atomic sub-queries pin each technique.
        sub_queries = self.decomposer.decompose(incident=original_query, verbose=verbose)
        all_queries: list[str] = []
        for q in [original_query, *sub_queries, *rewritten_queries]:
            if q and q.strip() and q not in all_queries:
                all_queries.append(q)

        if verbose:
            sep("AGENT — MULTI-QUERY RETRIEVAL (decomposed + per-query quota)")
            for i, q in enumerate(all_queries, 1):
                print(f"  [{i}] {q[:100]}")

        graphrag_result = self.retriever.retrieve_multi_quota(
            all_queries, per_query_k=3, top_k=VECTOR_TOP_K, max_vector=15, max_graph=8
        )
        context = build_context(graphrag_result, max_vector=15, max_graph=8)

        if verbose:
            sep("CONTEXT PREVIEW")
            print(context[:500] + "..." if len(context) > 500 else context)

        return {
            "graphrag_result": graphrag_result,
            "context": context,
        }

    def _node_evaluate_context(self, state: AgentState) -> dict:
        """Evaluate whether the retrieved context is sufficient."""
        verbose = state.get("verbose", True)
        broaden_count = state.get("broaden_count", 0)

        evaluation = self.evaluator.evaluate(
            original_query=state.get("original_query", ""),
            english_query=state.get("english_query", ""),
            context=state.get("context", ""),
            # drives looser criteria on later iterations and strategy choice
            retry_count=broaden_count,
            verbose=verbose,
        )

        return {
            "evaluation": evaluation,
            "strategy": getattr(evaluation, "strategy", ""),
            "gap_warning": getattr(evaluation, "gap_warning", ""),
            "acknowledgement_message": getattr(evaluation, "message", ""),
        }

    def _node_broaden_search(self, state: AgentState) -> dict:
        """Execute the BROADEN_SEARCH strategy by rewriting the query and looping."""
        evaluation = state.get("evaluation")
        rewritten_queries: list = list(state.get("rewritten_queries") or [])
        # Evaluator-written rewrites go straight into embedding + rerank, so
        # strip markdown/ID pollution before they hit retrieval.
        new_query = sanitize_retrieval_query(getattr(evaluation, "new_query", "") or "")
        if new_query:
            rewritten_queries.append(new_query)

        broaden_count = state.get("broaden_count", 0) + 1

        if state.get("verbose", True):
            from ..config import sep

            sep("AGENT — BROADEN SEARCH STRATEGY")
            print(f"  New Query: {new_query}")

        return {
            "rewritten_queries": rewritten_queries,
            "broaden_count": broaden_count,
        }

    def _node_reasoning(self, state: AgentState) -> dict:
        """Stage 2: Reasoning LLM — synthesize context into an English answer."""
        verbose = state.get("verbose", True)
        strategy = state.get("strategy", "")
        ack_message = state.get("acknowledgement_message", "")

        if not self.reasoning_llm:
            return {
                "answer": "Cannot generate answer because the selected CORE_LLM_PROVIDER key is not configured."
            }

        # ── Fast path for ACKNOWLEDGE_LIMIT ───────────────────────────────
        # Honour it only alongside an INSUFFICIENT verdict — guard against
        # local LLMs that output strategy=ACKNOWLEDGE_LIMIT while simultaneously
        # returning verdict=SUFFICIENT. Reaching reasoning WITH an INSUFFICIENT
        # verdict already means broaden is spent or unavailable
        # (see _edge_after_evaluation), so no separate budget check is needed —
        # and the answerability gate can legitimately fire on the first pass.
        evaluation = state.get("evaluation")
        verdict = getattr(evaluation, "verdict", "") if evaluation else ""
        if strategy == "ACKNOWLEDGE_LIMIT" and ack_message and verdict == VERDICT_INSUFFICIENT:
            if verbose:
                sep("AGENT — REASONING LLM (ACKNOWLEDGE_LIMIT)")
                print(ack_message)
            return {"answer": ack_message}

        # ── Standard reasoning ────────────────────────────────────────────
        # Single-call generation (benchmark variant C): write the final Thai
        # answer in this call — the translate_output node is skipped via
        # answer_is_final. Statistically equal quality to the two-stage path
        # at ~2.3x lower latency (see evaluation/results/).
        single_call = SINGLE_CALL_GENERATION and state.get("respond_in_thai", False)

        reasoning_prompt = build_generation_prompt(
            context=state.get("context", ""),
            original_query=state.get("original_query", ""),
            english_query=state.get("english_query", ""),
            respond_in_thai=single_call,
        )
        system_prompt = (
            CrossLingualLayer.get_fast_system_prompt(respond_in_thai=True)
            if single_call
            else CrossLingualLayer.get_reasoning_system_prompt()
        )

        if verbose:
            sep(
                "AGENT — REASONING LLM (single-call, Thai direct)"
                if single_call
                else "AGENT — REASONING LLM (context-grounded QA)"
            )

        response = self.reasoning_llm.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=reasoning_prompt),
            ]
        )
        answer = require_message_text(response, operation="grounded answer generation")

        if verbose:
            sep("ANSWER (Thai, single-call)" if single_call else "ENGLISH ANSWER")
            print(answer)

        return {"answer": answer, "answer_is_final": single_call}

    def _node_translate_output(self, state: AgentState) -> dict:
        """Stage 3: Translation LLM — render English answer into Thai."""
        verbose = state.get("verbose", True)
        simplified = state.get("answer", "")

        if not self.translation_llm:
            return {"answer": simplified}

        if verbose:
            sep("AGENT — TRANSLATION LLM (English → Thai)")

        response = self.translation_llm.invoke(
            [
                SystemMessage(
                    content=CrossLingualLayer.get_translation_system_prompt()
                ),
                HumanMessage(content=simplified),
            ]
        )
        thai_answer = require_message_text(response, operation="Thai answer translation")

        if verbose:
            sep("ANSWER (Thai)")
            print(thai_answer)
            sep()

        return {"answer": thai_answer}

    # ------------------------------------------------------------------
    # Edge routing functions
    # ------------------------------------------------------------------
    @staticmethod
    def _edge_after_route(state: AgentState) -> str:
        """Route based on query classification."""
        # TEMPORARILY DISABLED ROUTER: always go to incident analysis
        # if state.get("route") == "GENERAL_EXPLANATION":
        #     return "general"
        return "incident"

    @staticmethod
    def _edge_after_evaluation(state: AgentState) -> str:
        """Decide next step based on context evaluation.

        - SUFFICIENT                     → "sufficient" (proceed to reasoning)
        - INSUFFICIENT + budget + rewrite → "broaden"   (self-rewrite, re-retrieve)
        - anything else                  → "sufficient" (answer with what we have)

        With the follow-up module gone, INSUFFICIENT can no longer pause for the
        user — the only remaining recovery is the agent's own BROADEN_SEARCH
        rewrite. Once the budget is spent, or the evaluator gives no usable
        rewrite (looping on the same queries would change nothing), we answer
        with the best available context; ACKNOWLEDGE_LIMIT is then honoured
        downstream in ``_node_reasoning``.

        PARTIAL_ANSWER is NOT honoured: the evaluator can return it, and its
        ``gap_warning`` is carried into state, but nothing reads it, so the
        answer goes out without the caveat the evaluator asked for. Wiring it
        up is a feature, not cleanup — left as-is deliberately.
        """
        evaluation: EvaluationResult = state.get("evaluation")  # type: ignore[assignment]
        broaden_count = state.get("broaden_count", 0)

        # No evaluation object → proceed
        if evaluation is None:
            return "sufficient"

        if evaluation.verdict == VERDICT_SUFFICIENT:
            return "sufficient"

        if broaden_count < MAX_BROADEN_RETRIES and sanitize_retrieval_query(
            getattr(evaluation, "new_query", "") or ""
        ):
            return "broaden"

        return "sufficient"

    @staticmethod
    def _edge_after_reasoning(state: AgentState) -> str:
        """Decide whether to translate the answer to Thai.

        Skipped when single-call generation already wrote the Thai answer
        (answer_is_final). The ACKNOWLEDGE_LIMIT fast path never sets that
        flag, so its (possibly English) message still gets translated.
        """
        if state.get("respond_in_thai", False) and not state.get(
            "answer_is_final", False
        ):
            return "translate"
        return "done"
