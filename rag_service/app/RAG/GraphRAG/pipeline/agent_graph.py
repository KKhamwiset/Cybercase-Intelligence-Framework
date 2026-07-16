"""
LangGraph Agentic RAG Pipeline
================================
Replaces the linear LCEL chain with a stateful graph that supports:

   1. **Follow-Up Module** — on insufficient context the agent immediately
      asks a targeted follow-up question, stores the answer as a structured
      incident fact, rewrites the query (MITRE-aligned), then re-retrieves
      using ALL accumulated queries in parallel.
   2. **Decomposed Multi-Query Retrieval** — the incident is broken into atomic
      per-technique sub-queries (in the incident's own language; no English
      translation — BGE-M3 is multilingual) plus any rewrites, then retrieved
      via retrieve_multi_quota() so every technique is guaranteed representation.

 The graph flow:

     input → route → prepare → retrieve_quota → evaluate_context
                   (lang detect)                      │
                                        ┌─ sufficient │  insufficient
                                        ↓             ↓
                                   reasoning     prepare_followup
                                        ↓             ↓
                               translate_output  (user input)
                                        ↓             ↓
                                     output    append fact + rewrite
                                                       ↓
                                                retrieve_quota (loop)
                                            (max 2 follow-up iterations)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, TypedDict

from FlagEmbedding import BGEM3FlagModel
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from ..config import (
    ANTHROPIC_API_KEY,
    EMBED_MODEL,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_TEMPERATURE,
    LOCAL_LLM_MODEL,
    OLLAMA_BASE_URL,
    SINGLE_CALL_GENERATION,
    ULTRAFAST_MAX_TOKENS,
    ULTRAFAST_TOP_K,
    USE_FP16,
    VECTOR_TOP_K,
    sep,
)
from ..retrieval.hybrid_retriever import GraphRAGResult, HybridRetriever
from .context_builder import build_context, build_generation_prompt
from .cross_lingual import CrossLingualLayer
from .query_decomposer import QueryDecomposer
from .evaluator import (
    VERDICT_INSUFFICIENT,
    VERDICT_NEED_CLARIFICATION,
    VERDICT_SUFFICIENT,
    ContextEvaluator,
    EvaluationResult,
)
from .query_merger import QueryMerger, sanitize_retrieval_query
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
    rewritten_queries: list  # All MITRE-aligned rewrites derived from follow-ups

    # ── Evaluation ────────────────────────────────────────────────────────
    evaluation: Any  # EvaluationResult
    retry_count: int  # Number of re-retrieval attempts so far

    # ── Follow-up ─────────────────────────────────────────────────────────
    followup_question: str  # Question to ask the user
    followup_answer: str  # User's response (latest)
    awaiting_followup: bool  # True while waiting for user input
    followup_count: int  # Iterations so far (max: MAX_FOLLOWUP_RETRIES)
    broaden_count: int  # Iterations of BROADEN_SEARCH so far
    incident_facts: dict  # Structured facts: {"initial_access": "SQL Injection", …}
    asked_slots: list  # Slot names already asked, e.g. ["initial_access"]

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

    Consumers (FastAPI, CLI, tests) should inspect ``status``:

    - ``"completed"``  → ``answer`` contains the final answer.
    - ``"followup"``   → ``followup_question`` contains the agent's
      clarifying question. Use ``session_id`` to resume via
      ``agent.resume(session_id, user_answer)``.
    """

    status: str  # "completed" | "followup"
    answer: str = ""
    followup_question: str = ""
    session_id: str = ""  # Non-empty only when status == "followup"
    context: str = ""
    graphrag_result: Any = None

    # Convenience helpers
    @property
    def needs_followup(self) -> bool:
        return self.status == "followup"

    def to_dict(self) -> dict:
        """Serialize for JSON API responses."""
        d: dict[str, Any] = {"status": self.status, "answer": self.answer}
        if self.needs_followup:
            d["followup_question"] = self.followup_question
            d["session_id"] = self.session_id
        return d


# ──────────────────────────────────────────────────────────────────────────────
# Max retries for the self-reflection loop
# ──────────────────────────────────────────────────────────────────────────────
MAX_RETRIEVAL_RETRIES = 2
MAX_FOLLOWUP_RETRIES = 2  # Maximum follow-up iterations before forcing generation


# ──────────────────────────────────────────────────────────────────────────────
# The Agent
# ──────────────────────────────────────────────────────────────────────────────
class GraphRAGAgent:
    """Agentic RAG pipeline built on LangGraph.

    Drop-in companion for ``GraphRAGChain`` — offers the same ``.query()``
    interface but with self-reflection and follow-up capabilities.
    """

    def __init__(
        self,
        embed_model: Optional[BGEM3FlagModel] = None,
        reranker: Optional[Any] = None,
        use_local: bool = False,
    ) -> None:
        sep("Initializing GraphRAG Agent (LangGraph)")

        self.use_local = use_local
        self._ultrafast_llm = None  # lazily built on first query_ultrafast call

        # Shared embedding model
        if embed_model is None:
            print(f"[AGENT] Loading embedding model: {EMBED_MODEL}")
            self.embed_model = BGEM3FlagModel(EMBED_MODEL, use_fp16=USE_FP16)
        else:
            self.embed_model = embed_model

        # Components — propagate use_local to all LLM-bearing components.
        # No input-translation component: retrieval is native-language (BGE-M3).
        # CrossLingualLayer is still used, but only via its @staticmethods
        # (language detect + system prompts), so no instance is needed.
        self.retriever = HybridRetriever(
            embed_model=self.embed_model, reranker=reranker
        )
        self.router = QueryRouter(use_local=use_local)
        self.evaluator = ContextEvaluator(use_local=use_local)
        self.query_merger = QueryMerger(use_local=use_local)
        self.decomposer = QueryDecomposer(use_local=use_local)

        # In-memory session store for paused follow-up states.
        self._sessions: dict[str, dict] = {}

        # LLMs
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
            print(f"[AGENT] Reasoning LLM  : {LOCAL_LLM_MODEL} (local)")
            print(f"[AGENT] Translation LLM: {LOCAL_LLM_MODEL} (local)")
        elif ANTHROPIC_API_KEY:
            self.reasoning_llm = ChatAnthropic(  # type: ignore[call-arg]
                model_name=LLM_MODEL,
                api_key=ANTHROPIC_API_KEY,
                temperature=LLM_TEMPERATURE,
                max_tokens_to_sample=LLM_MAX_TOKENS,
            )
            self.translation_llm = ChatAnthropic(  # type: ignore[call-arg]
                model_name=LLM_MODEL,
                api_key=ANTHROPIC_API_KEY,
                temperature=LLM_TEMPERATURE,
                max_tokens_to_sample=LLM_MAX_TOKENS,
            )
            print(f"[AGENT] Reasoning LLM : {LLM_MODEL}")
            print(f"[AGENT] Translation LLM: {LLM_MODEL}")
        else:
            self.reasoning_llm = None
            self.translation_llm = None
            print("[AGENT] No LLM configured (ANTHROPIC_API_KEY not set)")

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
          • NO context evaluator / self-reflection loop / follow-up / broaden
          • NO separate translation stage — the reasoning LLM answers DIRECTLY in
            the response language (reasoning + translation folded into one call)

        Use when speed matters more than maximal technique coverage or clarifying
        follow-ups. Always returns ``status="completed"`` (never pauses).
        """
        if not self.reasoning_llm:
            return AgentResponse(
                status="completed",
                answer="Cannot generate answer without an LLM (ANTHROPIC_API_KEY not set).",
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
        answer = str(response.content)

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

        if self.use_local:
            from langchain_ollama import ChatOllama

            self._ultrafast_llm = ChatOllama(
                model=LOCAL_LLM_MODEL,
                base_url=OLLAMA_BASE_URL,
                temperature=LLM_TEMPERATURE,
                num_predict=ULTRAFAST_MAX_TOKENS,
                reasoning=False,
            )
        elif ANTHROPIC_API_KEY:
            self._ultrafast_llm = ChatAnthropic(  # type: ignore[call-arg]
                model_name=LLM_MODEL,
                api_key=ANTHROPIC_API_KEY,
                temperature=LLM_TEMPERATURE,
                max_tokens_to_sample=ULTRAFAST_MAX_TOKENS,
            )
        return self._ultrafast_llm

    def query_ultrafast(self, user_query: str, verbose: bool = True) -> AgentResponse:
        """Absolute-minimum-latency path. On top of everything ``query_fast`` strips:
          • NO graph expansion — vector search + rerank ONLY (skips Neo4j entirely)
          • smaller top-K + compact context
          • terse output — capped ``max_tokens`` + a brief incident→MITRE mapping
            prompt (no 4-section narrative), since output tokens dominate latency

        Returns a short technique mapping in the query's language. Never pauses.
        """
        llm = self._get_ultrafast_llm()
        if not llm:
            return AgentResponse(
                status="completed",
                answer="Cannot generate answer without an LLM (ANTHROPIC_API_KEY not set).",
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
        answer = str(response.content)

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

    def query(
        self,
        user_query: str,
        verbose: bool = True,
        followup_callback: Any = None,
    ) -> AgentResponse:
        """Execute the agentic RAG pipeline.

        Works for **both** CLI and API:

        - **CLI / synchronous**: Pass a ``followup_callback(question) -> str``.
          If the agent needs clarification it will call the callback, get the
          user's answer, and continue. It handles multiple follow-up iterations
          in a loop until the graph completes.
        - **API / asynchronous**: Pass ``followup_callback=None`` (default).
          If clarification is needed the method returns an ``AgentResponse``
          with ``status="followup"`` and a ``session_id``.  The API caller
          should send the user's answer to ``agent.resume(session_id, answer)``.

        Args:
            user_query: The user's query (Thai or English).
            verbose: Print intermediate steps.
            followup_callback: Optional callable ``(question: str) -> str``
                for synchronous follow-up (CLI mode).

        Returns:
            ``AgentResponse`` — check ``.status`` to determine next action.
        """
        initial_state: AgentState = {
            "original_query": user_query,
            "verbose": verbose,
            "retry_count": 0,
            "followup_count": 0,
            "broaden_count": 0,
            "awaiting_followup": False,
            "followup_answer": "",
            "rewritten_queries": [],
            "incident_facts": {},
            "asked_slots": [],
            "strategy": "",
            "gap_warning": "",
            "acknowledgement_message": "",
        }

        # Run the graph until we hit END (or follow-up pause)
        result = self.graph.invoke(initial_state)

        # ── Handle follow-up ──────────────────────────────────────────
        # Use a loop so CLI mode can handle multiple follow-up iterations.
        # Key the loop on awaiting_followup ALONE: a follow-up must never be
        # silently dropped just because its question came back blank (that
        # would fall through to a completed response with an empty answer).
        while result.get("awaiting_followup"):
            question = (
                result.get("followup_question") or self._DEFAULT_FOLLOWUP_QUESTION
            )

            if verbose:
                from ..config import sep

                sep("AGENT — FOLLOW-UP REQUIRED")
                print(f"  Question: {question}")

            # ── CLI mode: use callback synchronously ──────────────────
            if followup_callback is not None:
                user_answer = followup_callback(question)

                if user_answer:
                    # _resume_with_answer re-invokes the graph. The loop continues.
                    result = self._resume_with_answer(result, user_answer)
                    continue
                else:
                    # User declined to answer → proceed with what we have
                    result = self._force_continue(result)
                    break

            # ── API mode: park the session and return follow-up ───────
            else:
                import uuid

                session_id = str(uuid.uuid4())
                self._sessions[session_id] = dict(result)

                if verbose:
                    print(f"  Session parked: {session_id}")

                return AgentResponse(
                    status="followup",
                    followup_question=question,
                    session_id=session_id,
                )

        # ── Normal completion ─────────────────────────────────────────
        return AgentResponse(
            status="completed",
            answer=result.get("answer", ""),
            context=result.get("context", ""),
            graphrag_result=result.get("graphrag_result"),
        )

    def resume(
        self,
        session_id: str,
        user_answer: str,
        verbose: bool = True,
    ) -> AgentResponse:
        """Resume a paused follow-up session with the user's answer.

        This is the second step of the API flow:

        1. ``agent.query(q)`` → ``AgentResponse(status="followup", session_id=..., ...)``
        2. ``agent.resume(session_id, user_answer)`` → usually
           ``AgentResponse(status="completed", answer=...)``, but may return
           another ``status="followup"`` (with a fresh ``session_id``) when the
           context is still insufficient after the answer. The caller should
           loop the same way as after ``query()`` until ``status`` is
           ``"completed"`` (bounded by ``MAX_FOLLOWUP_RETRIES``).

        Args:
            session_id: The session ID returned by ``query()`` or a prior
                ``resume()``.
            user_answer: The user's response to the follow-up question.
            verbose: Print intermediate steps.

        Returns:
            ``AgentResponse`` — ``status`` is ``"completed"`` or ``"followup"``.

        Raises:
            KeyError: If the session_id is not found (expired or invalid).
        """
        if session_id not in self._sessions:
            raise KeyError(
                f"Session '{session_id}' not found. "
                "It may have expired or already been resumed."
            )

        # Pop the stored state (one-time use)
        stored_state = self._sessions.pop(session_id)
        stored_state["verbose"] = verbose

        if verbose:
            sep("AGENT — RESUMING SESSION")
            print(f"  Session : {session_id}")
            print(f"  Answer  : {user_answer}")

        if user_answer:
            result = self._resume_with_answer(stored_state, user_answer)
        else:
            result = self._force_continue(stored_state)

        # The re-run graph can ask ANOTHER follow-up when the context is still
        # insufficient after the user's answer (e.g. initial-access answered,
        # but credential-theft still missing). Park a new session and return
        # status="followup" instead of a completed response with an empty
        # answer. Bounded by MAX_FOLLOWUP_RETRIES in _edge_after_evaluation.
        return self._park_or_complete(result, verbose)

    def _park_or_complete(self, result: dict, verbose: bool = True) -> AgentResponse:
        """Turn a graph result into an AgentResponse.

        If the graph is awaiting another follow-up, park a fresh session and
        return status="followup"; otherwise return the completed answer. Shared
        by query() and resume() so a follow-up on a later turn behaves exactly
        like the first one (never a silent completed+empty).
        """
        if result.get("awaiting_followup"):
            import uuid

            question = (
                result.get("followup_question") or self._DEFAULT_FOLLOWUP_QUESTION
            )
            session_id = str(uuid.uuid4())
            self._sessions[session_id] = dict(result)
            if verbose:
                sep("AGENT — FOLLOW-UP REQUIRED")
                print(f"  Question: {question}")
                print(f"  Session parked: {session_id}")
            return AgentResponse(
                status="followup",
                followup_question=question,
                session_id=session_id,
            )
        return AgentResponse(
            status="completed",
            answer=result.get("answer", ""),
            context=result.get("context", ""),
            graphrag_result=result.get("graphrag_result"),
        )

    # ------------------------------------------------------------------
    # Internal helpers for follow-up resumption
    # ------------------------------------------------------------------
    def _resume_with_answer(self, state: dict, user_answer: str) -> dict:
        """Incorporate the user's follow-up answer as a structured incident fact
        and produce a MITRE-aligned rewritten query before re-running the graph.

        Steps:
        1. Retrieve the slot_name from the evaluation result so the answer can
           be stored under the correct key in ``incident_facts``.
        2. Call ``QueryMerger`` to produce a clean MITRE-aligned rewritten query.
        3. Append the rewritten query to ``rewritten_queries`` (the original
           ``english_query`` is never mutated).
        4. Record the slot in ``asked_slots`` to prevent re-asking.
        5. Re-run the graph; ``_node_retrieve`` will call ``retrieve_multi``
           with all accumulated queries.
        """
        verbose = state.get("verbose", True)
        followup_question = state.get("followup_question", "")
        original_query = state.get("original_query", "")
        english_query = state.get("english_query", original_query)

        # ── 1. Store structured incident fact ─────────────────────────────
        evaluation = state.get("evaluation")
        slot_name = (
            evaluation.missing_slot
            if evaluation and getattr(evaluation, "missing_slot", "")
            else "followup"
        )
        incident_facts: dict = dict(state.get("incident_facts") or {})
        incident_facts[slot_name] = user_answer

        asked_slots: list = list(state.get("asked_slots") or [])
        if slot_name not in asked_slots:
            asked_slots.append(slot_name)

        # ── 2. Produce MITRE-aligned rewritten query via QueryMerger ──────
        rewritten_query = self.query_merger.merge(
            original_query=english_query,
            followup_question=followup_question,
            user_answer=user_answer,
            verbose=verbose,
        )

        # ── 3. Accumulate rewritten queries ───────────────────────────────
        rewritten_queries: list = list(state.get("rewritten_queries") or [])
        rewritten_queries.append(rewritten_query)

        # ── 4. Update state ───────────────────────────────────────────────
        state["followup_answer"] = user_answer
        state["awaiting_followup"] = False
        state["followup_count"] = state.get("followup_count", 0) + 1
        state["incident_facts"] = incident_facts
        state["asked_slots"] = asked_slots
        state["rewritten_queries"] = rewritten_queries

        if verbose:
            from ..config import sep

            sep("AGENT — FOLLOW-UP ANSWER RECEIVED")
            print(f"  Slot       : {slot_name}")
            print(f"  Value      : {user_answer}")
            print(f"  Rewrite    : {rewritten_query}")
            print(f"  All queries: {len(rewritten_queries) + 1} total")

        # Increment retry_count so the evaluator treats this as a follow-up
        # iteration — prevents infinite NEED_CLARIFICATION loops and ensures
        # the graph reaches reasoning even if context is still imperfect.
        state["retry_count"] = state.get("retry_count", 0) + 1

        # Re-run the full graph from the beginning (route → … → answer)

        return self.graph.invoke(state)

    def _force_continue(self, state: dict) -> dict:
        """Skip the follow-up and proceed with existing context."""
        state["awaiting_followup"] = False
        state["evaluation"] = None  # Clear evaluation to force SUFFICIENT path
        # Re-enter at route so the graph runs reasoning → translate → answer
        return self.graph.invoke(state)

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
        graph.add_node("prepare_followup", self._node_prepare_followup)
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

        # Evaluation decides: sufficient → reason, insufficient → ask follow-up, broaden → broaden_search
        graph.add_conditional_edges(
            "evaluate_context",
            self._edge_after_evaluation,
            {
                "sufficient": "reasoning",
                "followup": "prepare_followup",
                "broaden": "broaden_search",
            },
        )

        graph.add_edge("broaden_search", "retrieve")

        # Follow-up → END (pipeline pauses; resumed via _resume_with_answer)
        graph.add_edge("prepare_followup", END)

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

        answer = str(response.content)

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
        """Evaluate whether the retrieved context is sufficient.

        Passes structured incident facts and already-asked slots to the
        evaluator so it never asks for information the user already gave.
        """
        verbose = state.get("verbose", True)
        followup_count = state.get("followup_count", 0)
        broaden_count = state.get("broaden_count", 0)

        # the retry_count passed to the evaluator includes both user follow-ups and broaden loops
        total_retries = followup_count + broaden_count

        evaluation = self.evaluator.evaluate(
            original_query=state.get("original_query", ""),
            english_query=state.get("english_query", ""),
            context=state.get("context", ""),
            retry_count=total_retries,  # drives looser criteria on later iterations and strategy choice
            verbose=verbose,
            incident_facts=state.get("incident_facts") or {},
            asked_slots=state.get("asked_slots") or [],
        )

        return {
            "evaluation": evaluation,
            "strategy": getattr(evaluation, "strategy", ""),
            "gap_warning": getattr(evaluation, "gap_warning", ""),
            "acknowledgement_message": getattr(evaluation, "message", ""),
        }

    # Used when the evaluator flags INSUFFICIENT but returns a blank
    # follow-up question — without this the graph would set
    # awaiting_followup with no question, and query() would fall through
    # to a status="completed" response carrying an empty answer.
    _DEFAULT_FOLLOWUP_QUESTION = (
        "ขอรายละเอียดเพิ่มเติมเกี่ยวกับเหตุการณ์นี้ได้ไหมครับ "
        "(เช่น ผู้โจมตีเข้าถึงระบบครั้งแรกได้อย่างไร)"
    )

    def _node_prepare_followup(self, state: AgentState) -> dict:
        """Prepare a follow-up question for the user.

        Guarantees a non-empty question so awaiting_followup is never set
        without one — the evaluator's follow_up field can come back blank.
        """
        evaluation = state.get("evaluation")
        question = (getattr(evaluation, "follow_up", "") or "").strip()
        return {
            "awaiting_followup": True,
            "followup_question": question or self._DEFAULT_FOLLOWUP_QUESTION,
        }

    def _node_broaden_search(self, state: AgentState) -> dict:
        """Execute the BROADEN_SEARCH strategy by rewriting the query and looping."""
        evaluation = state.get("evaluation")
        rewritten_queries: list = list(state.get("rewritten_queries") or [])
        # Evaluator-written rewrites carry the same markdown/ID pollution risk
        # as merger output — same sanitizer before they hit retrieval.
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
        gap_warning = state.get("gap_warning", "")

        if not self.reasoning_llm:
            return {
                "answer": "Cannot generate answer without an LLM (ANTHROPIC_API_KEY not set)."
            }

        # ── Fast path for ACKNOWLEDGE_LIMIT ───────────────────────────────
        # Only skip reasoning if retries are truly exhausted — guard against
        # local LLMs that output strategy=ACKNOWLEDGE_LIMIT even on the first
        # pass while simultaneously returning verdict=SUFFICIENT.
        total_retries = state.get("followup_count", 0) + state.get("broaden_count", 0)
        if (
            strategy == "ACKNOWLEDGE_LIMIT"
            and ack_message
            and total_retries >= MAX_FOLLOWUP_RETRIES
        ):
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
            incident_facts=state.get("incident_facts") or {},
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
        answer = str(response.content)

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
        thai_answer = str(response.content)

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

        New logic (per pipeline.md):
        - SUFFICIENT               → "sufficient" (proceed to reasoning)
        - INSUFFICIENT             → "followup"   (ask a follow-up question)
        - strategy = BROADEN       → "broaden"
        """
        evaluation: EvaluationResult = state.get("evaluation")  # type: ignore[assignment]
        followup_count = state.get("followup_count", 0)
        broaden_count = state.get("broaden_count", 0)

        # No evaluation object → proceed
        if evaluation is None:
            return "sufficient"

        if evaluation.verdict == VERDICT_SUFFICIENT:
            return "sufficient"

        # Check strategy if we hit the limit
        total_retries = followup_count + broaden_count
        if total_retries >= MAX_FOLLOWUP_RETRIES:
            strategy = getattr(evaluation, "strategy", "")
            if (
                strategy == "BROADEN_SEARCH" and broaden_count < 2
            ):  # hard cap on broaden loops
                return "broaden"
            # PARTIAL_ANSWER, ACKNOWLEDGE_LIMIT, or fallback
            return "sufficient"

        # INSUFFICIENT → ask follow-up
        return "followup"

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
