"""
LangGraph Agentic RAG Pipeline
================================
Replaces the linear LCEL chain with a stateful graph that supports:

  1. **Self-Reflection** — evaluates retrieved context quality and
     re-retrieves with a rewritten query when results are insufficient.
  2. **Follow-Up Module** — asks the user for clarification when the
     query is too vague, then re-retrieves with enriched context.

The graph preserves the existing cross-lingual flow:

    input → route → translate → retrieve → evaluate_context
                                                 │
                                   ┌─ sufficient ┤ insufficient ─┐
                                   ↓                              ↓
                              reasoning              rewrite_query
                                   ↓                      ↓
                           translate_output        retrieve (loop)
                                   ↓                      ↓
                                output           evaluate_context
                                                 (max 2 retries)

                              ─── or ───

                          need_clarification
                                   ↓
                            ask_followup → (user input) → retrieve → …
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

    # ── Evaluation ────────────────────────────────────────────────────────
    evaluation: Any  # EvaluationResult
    retry_count: int  # Number of re-retrieval attempts so far

    # ── Follow-up ─────────────────────────────────────────────────────────
    followup_question: str  # Question to ask the user
    followup_answer: str  # User's response
    awaiting_followup: bool  # True while waiting for user input

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
          user's answer, and continue — returning a completed ``AgentResponse``.
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
            "awaiting_followup": False,
            "followup_answer": "",
        }

        # Run the graph until we hit END (or follow-up pause)
        result = self.graph.invoke(initial_state)

        # ── Handle follow-up ──────────────────────────────────────────
        if result.get("awaiting_followup") and result.get("followup_question"):
            question = result["followup_question"]

            if verbose:
                sep("AGENT — FOLLOW-UP REQUIRED")
                print(f"  Question: {question}")

            # ── CLI mode: use callback synchronously ──────────────────
            if followup_callback is not None:
                user_answer = followup_callback(question)

                if user_answer:
                    result = self._resume_with_answer(result, user_answer)
                    return AgentResponse(
                        status="completed",
                        answer=result.get("answer", ""),
                    )
                # User declined to answer → proceed with what we have
                result = self._force_continue(result)
                return AgentResponse(
                    status="completed",
                    answer=result.get("answer", ""),
                )

            # ── API mode: park the session and return follow-up ───────
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
        """Enrich the query with the user's follow-up answer and re-run."""
        state["followup_answer"] = user_answer
        state["awaiting_followup"] = False

        # Enrich the original query with the follow-up context
        enriched = f"{state['original_query']}\n\nAdditional context from user: {user_answer}"
        state["original_query"] = enriched

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
        graph.add_node("rewrite_and_retrieve", self._node_rewrite_and_retrieve)
        graph.add_node("prepare_followup", self._node_prepare_followup)
        graph.add_node("reasoning", self._node_reasoning)
        graph.add_node("translate_output", self._node_translate_output)

        # ── Entry point ───────────────────────────────────────────────
        graph.set_entry_point("route_query")

        # ── Edges ─────────────────────────────────────────────────────
        # After routing, decide which path
        graph.add_conditional_edges(
            "route_query",
            self._edge_after_route,
            {
                "general": "general_explanation",
                "incident": "translate_query",
            },
        )

        # General explanation goes straight to END
        graph.add_edge("general_explanation", END)

        # Translation → Retrieval → Evaluation
        graph.add_edge("translate_query", "retrieve")
        graph.add_edge("retrieve", "evaluate_context")

        # Evaluation decides next step
        graph.add_conditional_edges(
            "evaluate_context",
            self._edge_after_evaluation,
            {
                "sufficient": "reasoning",
                "insufficient": "rewrite_and_retrieve",
                "need_clarification": "prepare_followup",
            },
        )

        # Re-retrieval loops back to evaluation
        graph.add_edge("rewrite_and_retrieve", "evaluate_context")

        # Follow-up → END (will be resumed externally)
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

    def _node_translate_query(self, state: AgentState) -> dict:
        """Detect language and translate to English for retrieval."""
        query = state.get("original_query", "")
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
        """Execute hybrid retrieval (Vector + Graph) — always uses both."""
        english_query = state.get("english_query", state.get("original_query", ""))
        verbose = state.get("verbose", True)

        if verbose:
            sep("AGENT — HYBRID RETRIEVAL")

        graphrag_result = self.retriever.retrieve(english_query, top_k=VECTOR_TOP_K)
        context = build_context(graphrag_result)

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
        retry_count = state.get("retry_count", 0)

        evaluation = self.evaluator.evaluate(
            original_query=state.get("original_query", ""),
            english_query=state.get("english_query", state.get("original_query", "")),
            context=state.get("context", ""),
            verbose=verbose,
        )

        return {
            "evaluation": evaluation,
            "retry_count": retry_count,
        }

    def _node_rewrite_and_retrieve(self, state: AgentState) -> dict:
        """Rewrite the query and re-retrieve when context was insufficient."""
        evaluation: EvaluationResult | None = state.get("evaluation")
        verbose = state.get("verbose", True)
        retry_count = state.get("retry_count", 0) + 1

        new_query = (
            evaluation.rewritten_query
            if evaluation and evaluation.rewritten_query
            else state.get("english_query", state.get("original_query", ""))
        )

        if verbose:
            sep(f"AGENT — RE-RETRIEVAL (attempt {retry_count}/{MAX_RETRIEVAL_RETRIES})")
            print(f"  Rewritten query: {new_query}")

        graphrag_result = self.retriever.retrieve(new_query, top_k=VECTOR_TOP_K)
        context = build_context(graphrag_result)

        if verbose:
            sep("CONTEXT PREVIEW (re-retrieved)")
            print(context[:500] + "..." if len(context) > 500 else context)

        return {
            "english_query": new_query,
            "graphrag_result": graphrag_result,
            "context": context,
            "retry_count": retry_count,
        }

    def _node_prepare_followup(self, state: AgentState) -> dict:
        """Prepare a follow-up question for the user."""
        evaluation: EvaluationResult | None = state.get("evaluation")

        question = evaluation.followup_question if evaluation else ""
        if not question:
            question = "Could you please provide more specific details about the attack technique, target, or context?"

        return {
            "followup_question": question,
            "awaiting_followup": True,
        }

    def _node_reasoning(self, state: AgentState) -> dict:
        """Stage 2: Reasoning LLM — simplify jargon into plain English."""
        verbose = state.get("verbose", True)

        if not self.reasoning_llm:
            return {"answer": state.get("context", "")}

        reasoning_prompt = build_generation_prompt(
            context=state.get("context", ""),
            original_query=state.get("original_query", ""),
            english_query=state.get("english_query", state.get("original_query", "")),
            respond_in_thai=False,  # Reasoning always outputs English
        )

        if verbose:
            sep("AGENT — REASONING LLM (English simplification)")

        response = self.reasoning_llm.invoke(
            [
                SystemMessage(content=CrossLingualLayer.get_reasoning_system_prompt()),
                HumanMessage(content=reasoning_prompt),
            ]
        )
        simplified = str(response.content)

        if verbose:
            sep("SIMPLIFIED ENGLISH NARRATIVE")
            print(simplified)

        return {"answer": simplified}

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
        """Decide next step based on context evaluation."""
        evaluation: EvaluationResult = state.get("evaluation")  # type: ignore[assignment]
        retry_count = state.get("retry_count", 0)

        if evaluation is None:
            return "sufficient"

        if evaluation.verdict == VERDICT_SUFFICIENT:
            return "sufficient"

        # User request: If INSUFFICIENT or NEED_CLARIFICATION, immediately ask follow-up
        if evaluation.verdict in (VERDICT_INSUFFICIENT, VERDICT_NEED_CLARIFICATION):
            if retry_count == 0:
                return "need_clarification"
            # Already retried → proceed with what we have
            return "sufficient"

        return "sufficient"

    @staticmethod
    def _edge_after_reasoning(state: AgentState) -> str:
        """Decide whether to translate the answer to Thai."""
        if state.get("respond_in_thai", False):
            return "translate"
        return "done"
