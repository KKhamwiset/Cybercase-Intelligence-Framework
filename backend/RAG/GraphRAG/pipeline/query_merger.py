"""
Query Clarification Merger
==========================
Merges the user's original query with their clarification answer into a
single, self-contained query ready for vector-store retrieval.

Why a separate module?
  The naive approach — string concatenation — produces bloated, redundant
  queries that confuse the retriever.  This module calls a lightweight LLM
  once to produce a clean 1-3 sentence merged query.

Used in:
  agent_graph._resume_with_answer — after the user responds to a follow-up
  question, the merged query replaces the original before re-retrieval.
"""

from __future__ import annotations

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage

from ..config import (
    ANTHROPIC_API_KEY,
    EVALUATOR_LLM_MODEL,
    EVALUATOR_MAX_TOKENS,
    EVALUATOR_TEMPERATURE,
    sep,
)

# ──────────────────────────────────────────────────────────────────────────────
# Prompt
# ──────────────────────────────────────────────────────────────────────────────
_MERGE_PROMPT_TEMPLATE = """\
You are a query rewriting assistant in a cybersecurity RAG pipeline that retrieves
from the MITRE ATT&CK knowledge base.

Your job is to merge the user's original incident query with their clarification
answer into a single, optimised retrieval query that will be sent to a vector store.

## Rules
1. **MITRE-alignment**: Map the user's answer to the most likely MITRE ATT&CK
   technique name(s) and/or Tactic name(s). Include the technique keyword(s)
   prominently at the START of the merged query.
   Example: if the user says "SQL Injection", write
   "Exploit Public-Facing Application SQL Injection T1190 ..."
2. **Self-contained**: The merged query must not assume the retriever has memory
   of previous turns. It must stand alone.
3. **Preserve the incident chain**: Keep the key incident actions from the original
   query (e.g., credential theft, privilege escalation, data destruction).
4. **Concise**: 1–4 sentences or a tight keyword list. No explanation or preamble.
5. **English only**: Output must be in English regardless of input language.

## Input
Original query (may be Thai): {original_query}
Clarifying question asked: {followup_question}
User's clarification answer: {user_answer}

## Output
A single merged English retrieval query ready for MITRE ATT&CK vector search.\
"""


# ──────────────────────────────────────────────────────────────────────────────
# Merger class
# ──────────────────────────────────────────────────────────────────────────────
class QueryMerger:
    """Merges an original query + follow-up answer into a clean retrieval query.

    Uses the same lightweight model as the post-retrieval evaluator
    (claude-haiku) since this is a simple rewriting task — low latency and
    low cost are the priority.
    """

    def __init__(self) -> None:
        if ANTHROPIC_API_KEY:
            self.llm = ChatAnthropic(  # type: ignore[call-arg]
                model=EVALUATOR_LLM_MODEL,
                api_key=ANTHROPIC_API_KEY,
                temperature=EVALUATOR_TEMPERATURE,
                max_tokens=EVALUATOR_MAX_TOKENS,
            )
        else:
            self.llm = None

    # ------------------------------------------------------------------
    def merge(
        self,
        original_query: str,
        followup_question: str,
        user_answer: str,
        verbose: bool = True,
    ) -> str:
        """Produce a merged, self-contained retrieval query.

        Args:
            original_query:    The user's raw input (may be Thai or English).
            followup_question: The clarifying question the agent asked.
            user_answer:       The user's response to that question.
            verbose:           Print the merged result.

        Returns:
            A clean merged query string.  Falls back to simple concatenation
            when no LLM is available.
        """
        if not self.llm:
            # Graceful degradation — simple concatenation as before
            merged = f"{original_query} {user_answer}"
            if verbose:
                print(f"[QUERY MERGER] No LLM — using concatenation: {merged}")
            return merged

        prompt = _MERGE_PROMPT_TEMPLATE.format(
            original_query=original_query,
            followup_question=followup_question,
            user_answer=user_answer,
        )

        response = self.llm.invoke([HumanMessage(content=prompt)])
        merged = str(response.content).strip()

        if verbose:
            sep("AGENT — QUERY MERGE")
            print(f"  Original  : {original_query}")
            print(f"  Follow-up : {followup_question}")
            print(f"  Answer    : {user_answer}")
            print(f"  Merged    : {merged}")

        return merged
