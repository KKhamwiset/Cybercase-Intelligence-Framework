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

import re

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage

from ..config import (
    ANTHROPIC_API_KEY,
    EVALUATOR_LLM_MODEL,
    EVALUATOR_MAX_TOKENS,
    EVALUATOR_TEMPERATURE,
    LOCAL_EVAL_MODEL,
    OLLAMA_BASE_URL,
    sep,
)

# ──────────────────────────────────────────────────────────────────────────────
# Prompt
# ──────────────────────────────────────────────────────────────────────────────
_MERGE_PROMPT_TEMPLATE = """\
You are a query rewriting assistant in a cybersecurity RAG pipeline that retrieves
from the MITRE ATT&CK knowledge base.

Your job is to merge the user's original incident query with their clarification
answer into a single, self-contained retrieval query for vector search.

## Rules
1. **Describe, don't label**: Write ONE natural-language description of the
   incident chain — what the attacker did, to which target, in order. Use
   well-known MITRE technique NAMES verbatim where they clearly apply (e.g.
   "Brute Force", "Valid Accounts", "SQL Injection"), but NEVER ATT&CK ID
   numbers (T1110, TA0006, S0002) and NEVER markdown (**bold**, bullets,
   headers) — the query is embedded as-is, so labels and formatting match
   corpus metadata instead of the technique descriptions we want.
2. **Self-contained**: The merged query must not assume the retriever has memory
   of previous turns. It must stand alone.
3. **Preserve the incident chain**: Keep every key action from the original
   query AND add the new facts from the user's answer.
4. **Concise**: 1–3 sentences, plain text, no explanation or preamble.
5. **Same language as the original query** (Thai stays Thai); keep MITRE
   technique names in English verbatim.

## Input
Original query: {original_query}
Clarifying question asked: {followup_question}
User's clarification answer: {user_answer}

## Output
The single merged retrieval query, plain text only.\
"""


# ──────────────────────────────────────────────────────────────────────────────
# Output sanitizer — shared with the BROADEN_SEARCH rewrite path
# ──────────────────────────────────────────────────────────────────────────────
_ATTACK_ID_RE = re.compile(r"\b(?:TA|DS|T|S|G|M|C)\d{4}(?:\.\d{3})?\b")
_MARKDOWN_RE = re.compile(r"[*_`#>]+")


def sanitize_retrieval_query(text: str) -> str:
    """Strip markdown and bare ATT&CK ID tokens from a rewritten query.

    Rewrites go straight into embedding + rerank; bold markers and ID tokens
    (seen live: a resume rewrite ``**Brute Force T1110 Credential Access, …``)
    pull in ID/metadata matches instead of technique descriptions.
    """
    t = _MARKDOWN_RE.sub(" ", text)
    t = _ATTACK_ID_RE.sub(" ", t)
    t = re.sub(r"\(\s*\)", " ", t)  # empty parens left by removed IDs
    t = re.sub(r"\s+", " ", t)  # also collapses newlines — queries are one line
    return t.strip(" .,;:-–—")


# ──────────────────────────────────────────────────────────────────────────────
# Merger class
# ──────────────────────────────────────────────────────────────────────────────
class QueryMerger:
    """Merges an original query + follow-up answer into a clean retrieval query.

    Uses the same lightweight model as the post-retrieval evaluator
    (claude-haiku) since this is a simple rewriting task — low latency and
    low cost are the priority.
    """

    def __init__(self, use_local: bool = False) -> None:
        if use_local:
            from langchain_ollama import ChatOllama
            self.llm = ChatOllama(
                model=LOCAL_EVAL_MODEL,
                base_url=OLLAMA_BASE_URL,
                temperature=EVALUATOR_TEMPERATURE,
                num_predict=EVALUATOR_MAX_TOKENS,
            )
            print(f"[QUERY MERGER] Local model: {LOCAL_EVAL_MODEL}")
        elif ANTHROPIC_API_KEY:
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
        merged = sanitize_retrieval_query(str(response.content))
        if not merged:
            merged = f"{original_query} {user_answer}"

        if verbose:
            sep("AGENT — QUERY MERGE")
            print(f"  Original  : {original_query}")
            print(f"  Follow-up : {followup_question}")
            print(f"  Answer    : {user_answer}")
            print(f"  Merged    : {merged}")

        return merged
