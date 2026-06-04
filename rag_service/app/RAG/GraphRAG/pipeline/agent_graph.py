"""
LangGraph Agentic RAG Pipeline
================================
Replaces the linear LCEL chain with a stateful graph that supports:

   1. **Follow-Up Module** — on insufficient context the agent immediately
      asks a targeted follow-up question, stores the answer as a structured
      incident fact, rewrites the query (MITRE-aligned), then re-retrieves
      using ALL accumulated queries in parallel.
   2. **Multi-Query Retrieval** — original query + all rewrites are run
      through retrieve_multi() and merged/deduplicated before evaluation.
 
 The graph flow:
 
     input → route → translate → retrieve_multi → evaluate_context
                                                        │
                                        ┌─ sufficient   │  insufficient
                                        ↓               ↓
                                   reasoning     prepare_followup
                                        ↓               ↓
                               translate_output   (user input)
                                        ↓               ↓
                                     output      append fact + rewrite
                                                         ↓
                                                  retrieve_multi (loop)
                                              (max 2 follow-up iterations)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Optional, TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from FlagEmbedding import BGEM3FlagModel

from langgraph.graph import END, StateGraph

from ..config import (
    ANTHROPIC_API_KEY,
    EMBED_MODEL,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_TEMPERATURE,
    USE_FP16,
    VECTOR_TOP_K,
    sep,
)
from ..retrieval.hybrid_retriever import GraphRAGResult, HybridRetriever
from .context_builder import build_context, build_generation_prompt
from .cross_lingual import CrossLingualLayer
from .evaluator import (
    ContextEvaluator,
    EvaluationResult,
    VERDICT_INSUFFICIENT,
    VERDICT_NEED_CLARIFICATION,
    VERDICT_SUFFICIENT,
)
from .query_merger import QueryMerger
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

    def __init__(self, embed_model: Optional[BGEM3FlagModel] = None) -> None:
        sep("Initializing GraphRAG Agent (LangGraph)")

        # Shared embedding model
        if embed_model is None:
            print(f"[AGENT] Loading embedding model: {EMBED_MODEL}")
            self.embed_model = BGEM3FlagModel(EMBED_MODEL, use_fp16=USE_FP16)
        else:
            self.embed_model = embed_model

        # Components (reused from the linear pipeline)
        self.translator = CrossLingualLayer()
        self.retriever = HybridRetriever(embed_model=self.embed_model)
        self.router = QueryRouter()
        self.evaluator = ContextEvaluator()
        self.query_merger = QueryMerger()

        # In-memory session store for paused follow-up states.
        # Maps session_id → AgentState snapshot so the API can resume.
        self._sessions: dict[str, dict] = {}

        # LLMs
        if ANTHROPIC_API_KEY:
            self.reasoning_llm = ChatAnthropic(  # type: ignore[call-arg]
                model=LLM_MODEL,
                api_key=ANTHROPIC_API_KEY,
                temperature=LLM_TEMPERATURE,
                max_tokens=LLM_MAX_TOKENS,
            )
            self.translation_llm = ChatAnthropic(  # type: ignore[call-arg]
                model=LLM_MODEL,
                api_key=ANTHROPIC_API_KEY,
                temperature=LLM_TEMPERATURE,
                max_tokens=LLM_MAX_TOKENS,
            )
            print(f"[AGENT] Reasoning LLM : {LLM_MODEL}")
            print(f"[AGENT] Translation LLM: {LLM_MODEL}")
        else:
            self.reasoning_llm = None
            self.translation_llm = None
            print("[AGENT] No LLM configured (ANTHROPIC_API_KEY not set)")

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
        # Use a loop so CLI mode can handle multiple follow-up iterations
        while result.get("awaiting_followup") and result.get("followup_question"):
            question = result["followup_question"]

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
        2. ``agent.resume(session_id, user_answer)`` → ``AgentResponse(status="completed", answer=...)``

        Args:
            session_id: The session ID returned by ``query()``.
            user_answer: The user's response to the follow-up question.
            verbose: Print intermediate steps.

        Returns:
            ``AgentResponse`` with ``status="completed"``.

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

        return AgentResponse(
            status="completed",
            answer=result.get("answer", ""),
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
            evaluation.slot_name
            if evaluation and getattr(evaluation, "slot_name", "")
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
        graph.add_node("translate_query", self._node_translate_query)
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
                "incident": "translate_query",
            },
        )

        graph.add_edge("general_explanation", END)

        # Translation → Multi-Query Retrieval → Evaluation
        graph.add_edge("translate_query", "retrieve")
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
        query = state["original_query"]
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
        query = state["original_query"]
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

    def _node_translate_query(self, state: AgentState) -> dict:
        """Detect language and translate to English for retrieval."""
        query = state["original_query"]
        verbose = state.get("verbose", True)

        respond_in_thai = CrossLingualLayer.should_respond_in_thai(query)
        english_query = self.translator.translate_query(query)

        if verbose and english_query != query:
            print(f"  Translated: {english_query}")

        return {
            "english_query": english_query,
            "respond_in_thai": respond_in_thai,
        }

    def _node_retrieve(self, state: AgentState) -> dict:
        """Execute multi-query hybrid retrieval (Vector + Graph).

        On the first pass only ``english_query`` is used.  After each
        follow-up round, MITRE-aligned rewritten queries are appended to
        ``rewritten_queries`` and all queries are retrieved in parallel via
        ``retrieve_multi()``.
        """
        english_query = state["english_query"]
        rewritten_queries: list = list(state.get("rewritten_queries") or [])
        verbose = state.get("verbose", True)

        # Build the full query list: original always first
        all_queries = [english_query] + rewritten_queries

        if verbose:
            sep("AGENT — HYBRID RETRIEVAL (multi-query)")
            for i, q in enumerate(all_queries, 1):
                print(f"  [{i}] {q[:100]}")

        graphrag_result = self.retriever.retrieve_multi(all_queries, top_k=VECTOR_TOP_K)
        context = build_context(graphrag_result)

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
            original_query=state["original_query"],
            english_query=state["english_query"],
            context=state["context"],
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

    def _node_prepare_followup(self, state: AgentState) -> dict:
        """Prepare a follow-up question for the user."""
        evaluation: EvaluationResult = state["evaluation"]
        return {
            "awaiting_followup": True,
            "followup_question": evaluation.follow_up,
        }

    def _node_broaden_search(self, state: AgentState) -> dict:
        """Execute the BROADEN_SEARCH strategy by rewriting the query and looping."""
        evaluation: EvaluationResult = state["evaluation"]
        rewritten_queries: list = list(state.get("rewritten_queries") or [])
        new_query = getattr(evaluation, "new_query", "")
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

        # ── Fast path for ACKNOWLEDGE_LIMIT ───────────────────────────────
        if strategy == "ACKNOWLEDGE_LIMIT" and ack_message:
            if verbose:
                sep("AGENT — REASONING LLM (ACKNOWLEDGE_LIMIT)")
                print(ack_message)
            return {"answer": ack_message}

        # ── Standard reasoning ────────────────────────────────────────────
        reasoning_prompt = build_generation_prompt(
            context=state["context"],
            original_query=state["original_query"],
            english_query=state["english_query"],
            respond_in_thai=False,
        )

        if verbose:
            sep("AGENT — REASONING LLM (context-grounded QA)")

        response = self.reasoning_llm.invoke(
            [
                SystemMessage(content=CrossLingualLayer.get_reasoning_system_prompt()),
                HumanMessage(content=reasoning_prompt),
            ]
        )
        english_answer = str(response.content)

        if verbose:
            sep("ENGLISH ANSWER")
            print(english_answer)

        return {"answer": english_answer}

    def _node_translate_output(self, state: AgentState) -> dict:
        """Stage 3: Translation LLM — render English answer into Thai."""
        verbose = state.get("verbose", True)
        simplified = state["answer"]

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
            if strategy == "BROADEN_SEARCH" and broaden_count < 2:  # hard cap on broaden loops
                return "broaden"
            # PARTIAL_ANSWER, ACKNOWLEDGE_LIMIT, or fallback
            return "sufficient"

        # INSUFFICIENT → ask follow-up
        return "followup"

    @staticmethod
    def _edge_after_reasoning(state: AgentState) -> str:
        """Decide whether to translate the answer to Thai."""
        if state.get("respond_in_thai", False):
            return "translate"
        return "done"
