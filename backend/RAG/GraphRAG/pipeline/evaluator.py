"""
Context Sufficiency Evaluator
==============================
Uses the LLM to judge whether retrieved context can adequately answer
the user's query.  Returns one of three verdicts:

  SUFFICIENT          → proceed to reasoning
  INSUFFICIENT        → rewrite query and re-retrieve
  NEED_CLARIFICATION  → ask the user a follow-up question

This is the "Self-RAG" reflective loop that makes the pipeline *agentic*.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from ..config import ANTHROPIC_API_KEY, LLM_MODEL, LLM_TEMPERATURE, sep

# ──────────────────────────────────────────────────────────────────────────────
# Evaluation verdicts
# ──────────────────────────────────────────────────────────────────────────────
VERDICT_SUFFICIENT = "SUFFICIENT"
VERDICT_INSUFFICIENT = "INSUFFICIENT"
VERDICT_NEED_CLARIFICATION = "NEED_CLARIFICATION"

VALID_VERDICTS = {VERDICT_SUFFICIENT, VERDICT_INSUFFICIENT, VERDICT_NEED_CLARIFICATION}


@dataclass
class EvaluationResult:
    """Structured result from the context evaluator."""

    verdict: str  # One of VALID_VERDICTS
    reason: str  # Brief justification
    rewritten_query: str = ""  # Populated when verdict == INSUFFICIENT
    followup_question: str = ""  # Populated when verdict == NEED_CLARIFICATION


# ──────────────────────────────────────────────────────────────────────────────
# System prompt
# ──────────────────────────────────────────────────────────────────────────────
EVALUATOR_SYSTEM_PROMPT = """\
You are an evaluation agent inside a cybersecurity RAG system built on MITRE ATT&CK.

Your job is to assess whether the **retrieved context** can adequately answer the
**user's query**.  You must return a JSON object with exactly these keys:

{
  "verdict": "<SUFFICIENT | INSUFFICIENT | NEED_CLARIFICATION>",
  "reason": "<one-sentence justification>",
  "rewritten_query": "<improved English search query — required when verdict is INSUFFICIENT, empty string otherwise>",
  "followup_question": "<clarifying question to ask the user — required when verdict is NEED_CLARIFICATION, empty string otherwise>"
}

Decision rules
--------------
SUFFICIENT
  The context contains enough relevant information (entities, techniques,
  relationships) to produce a meaningful answer.  Minor gaps are OK as long
  as the core of the question is addressable.

INSUFFICIENT
  The context is mostly irrelevant or too sparse to answer the question.
  You MUST supply a **followup_question** in the same language the user used
  (Thai or English) to ask for more specific details or clarification.

NEED_CLARIFICATION
  The user's query itself is too vague, ambiguous, or missing critical
  details (e.g., no attack technique mentioned, unclear target, no
  actionable specifics).  You MUST supply a **followup_question** in
  the same language the user used (Thai or English) to ask for the
  missing information.

Important
---------
- Return ONLY valid JSON.  No markdown fences, no extra text.
- The followup_question must be in the **same language** as the user's original query.
- Never fabricate ATT&CK IDs or technique names in the rewritten_query.
- Prefer SUFFICIENT when context is roughly on-topic — be conservative
  about triggering re-retrieval loops."""


# ──────────────────────────────────────────────────────────────────────────────
# Evaluator class
# ──────────────────────────────────────────────────────────────────────────────
class ContextEvaluator:
    """Evaluates whether retrieved context is sufficient to answer a query."""

    def __init__(self) -> None:
        if ANTHROPIC_API_KEY:
            self.llm = ChatAnthropic(  # type: ignore[call-arg]
                model=LLM_MODEL,
                api_key=ANTHROPIC_API_KEY,
                temperature=LLM_TEMPERATURE,
                max_tokens=512,
            )
        else:
            self.llm = None

    # ------------------------------------------------------------------
    def evaluate(
        self,
        original_query: str,
        english_query: str,
        context: str,
        verbose: bool = True,
    ) -> EvaluationResult:
        """Judge context sufficiency.

        Args:
            original_query: The user's original query (may be Thai).
            english_query: The translated English query.
            context: The assembled context string from the retriever.
            verbose: Print evaluation details.

        Returns:
            EvaluationResult with verdict + optional rewritten query or
            follow-up question.
        """
        if not self.llm:
            # No LLM → always assume sufficient (fall through to reasoning)
            return EvaluationResult(
                verdict=VERDICT_SUFFICIENT,
                reason="No LLM configured — skipping evaluation.",
            )

        user_prompt = self._build_prompt(original_query, english_query, context)

        if verbose:
            sep("AGENT — CONTEXT EVALUATION")

        response = self.llm.invoke(
            [
                SystemMessage(content=EVALUATOR_SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ]
        )

        result = self._parse_response(str(response.content))

        if verbose:
            print(f"  Verdict : {result.verdict}")
            print(f"  Reason  : {result.reason}")
            if result.rewritten_query:
                print(f"  Rewrite : {result.rewritten_query}")
            if result.followup_question:
                print(f"  Follow-up: {result.followup_question}")

        return result

    # ------------------------------------------------------------------
    @staticmethod
    def _build_prompt(
        original_query: str,
        english_query: str,
        context: str,
    ) -> str:
        """Build the evaluation prompt."""
        parts = [
            "=== USER QUERY ===",
            f"Original : {original_query}",
        ]
        if english_query != original_query:
            parts.append(f"English  : {english_query}")

        parts.append("")
        parts.append("=== RETRIEVED CONTEXT ===")
        # Limit context length to keep the evaluation prompt manageable
        ctx_preview = context[:4000]
        if len(context) > 4000:
            ctx_preview += "\n... [truncated]"
        parts.append(ctx_preview)

        return "\n".join(parts)

    # ------------------------------------------------------------------
    @staticmethod
    def _parse_response(raw: str) -> EvaluationResult:
        """Parse the LLM's JSON response into an EvaluationResult.

        Includes fallback logic for malformed responses.
        """
        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            # Remove opening fence (```json or ```)
            first_newline = cleaned.index("\n")
            cleaned = cleaned[first_newline + 1 :]
        if cleaned.endswith("```"):
            cleaned = cleaned[: -len("```")]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            # Fallback: assume sufficient to avoid blocking the pipeline
            return EvaluationResult(
                verdict=VERDICT_SUFFICIENT,
                reason=f"Failed to parse evaluator response — defaulting to SUFFICIENT. Raw: {raw[:200]}",
            )

        verdict = data.get("verdict", VERDICT_SUFFICIENT).upper().strip()
        if verdict not in VALID_VERDICTS:
            verdict = VERDICT_SUFFICIENT

        return EvaluationResult(
            verdict=verdict,
            reason=data.get("reason", ""),
            rewritten_query=data.get("rewritten_query", ""),
            followup_question=data.get("followup_question", ""),
        )
