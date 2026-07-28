"""
Context Sufficiency Evaluator
==============================
Uses the LLM to judge whether retrieved context can adequately answer
the user's query.  Returns one of two verdicts:

  SUFFICIENT    → proceed to reasoning
  INSUFFICIENT  → rewrite the query and re-retrieve (BROADEN_SEARCH)

This is the "Self-RAG" reflective loop that makes the pipeline *agentic*.
The loop is fully autonomous: the evaluator never asks the user anything, so
on INSUFFICIENT it must supply a ``new_query`` the agent can retrieve with.

- On broaden iteration ≥ MAX_RETRIES the evaluator short-circuits to
  SUFFICIENT without calling the LLM, to prevent infinite loops.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

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
# Evaluation verdicts
# ──────────────────────────────────────────────────────────────────────────────
VERDICT_SUFFICIENT = "SUFFICIENT"
VERDICT_INSUFFICIENT = "INSUFFICIENT"

VALID_VERDICTS = {VERDICT_SUFFICIENT, VERDICT_INSUFFICIENT}

# Maximum broaden iterations before we force SUFFICIENT (guarded in agent_graph)
MAX_RETRIES = 2


@dataclass
class EvaluationResult:
    """Structured result from the context evaluator."""

    verdict: str  # SUFFICIENT | INSUFFICIENT
    reason: str  # Brief justification
    covered_phases: list[str] | None = None
    missing_phases: list[str] | None = None
    strategy: str = ""
    new_query: str = ""
    gap_warning: str = ""
    message: str = ""

    def __post_init__(self):
        if self.covered_phases is None:
            self.covered_phases = []
        if self.missing_phases is None:
            self.missing_phases = []


# ──────────────────────────────────────────────────────────────────────────────
# System prompt
# ──────────────────────────────────────────────────────────────────────────────
EVALUATOR_SYSTEM_PROMPT = """\
You are a context sufficiency evaluator for a MITRE ATT&CK incident analysis system.

Evaluate whether the retrieved context is sufficient to answer the incident query.

STEP 0 — ANSWERABILITY GATE (check this BEFORE judging the context):
An incident analysis needs an incident. If the query contains NO concrete
attacker action — e.g. it only refers to "this incident" / "the attack" without
describing what happened, or states only an outcome ("data leaked", "system was
hacked") with no HOW — the verdict is INSUFFICIENT no matter how relevant the
retrieved context looks. Topically related context can NEVER substitute for a
missing incident description. You cannot ask the user for the missing details,
so in this case set strategy to ACKNOWLEDGE_LIMIT and write a message stating
that the incident description is too vague to map to ATT&CK techniques and
naming what is needed (attack vector / attacker actions / affected systems).

RULES:
- Coverage is judged against the RETRIEVED CONTEXT only. Mark a phase
  covered only when the context contains a technique whose description matches
  that behavior.
- Ignore retrieved entries that do not match any described attacker action
  (unrelated threat groups, software, campaigns, mitigations) — they add no
  coverage even if they dominate the context.
- Judge based on SEMANTIC coverage, not exact keyword match
- If the context contains techniques that MAP to the described behavior, mark as SUFFICIENT
- A technique is "covered" if its description matches the attack behavior, even if not explicitly named
- Only mark INSUFFICIENT if a critical attack phase is completely absent from context
- Once the incident description is concrete (gate passed), prefer SUFFICIENT
  over INSUFFICIENT when in doubt — it is better to answer with partial context
  than to over-ask
- In `reason`, refer to attack phases by NAME only (e.g. "Credential Access", "Privilege Escalation"). Do NOT cite numeric ATT&CK IDs (T#### or TA####) — invented IDs mislead the analyst. Only quote an ID if it appears VERBATIM in the RETRIEVED CONTEXT.

ATTACK PHASES to check (mark each as covered / partial / missing):
1. Initial Access
2. Credential Access
3. Privilege Escalation
4. Impact / Data Destruction

Output JSON:
{
  "verdict": "SUFFICIENT" | "INSUFFICIENT",
  "covered_phases": [...],
  "missing_phases": [...],
  "reason": "<brief explanation>",
  "strategy": "<BROADEN_SEARCH | PARTIAL_ANSWER | ACKNOWLEDGE_LIMIT or null>",
  "new_query": "<new query if BROADEN_SEARCH, else null>",
  "gap_warning": "<warning if PARTIAL_ANSWER, else null>",
  "message": "<message if ACKNOWLEDGE_LIMIT, else null>"
}

Threshold:
- If 2 or more phases are covered → verdict SUFFICIENT
- If only 1 phase is covered but the context clearly explains that phase → verdict SUFFICIENT
- If fewer than 2 phases are covered AND the context does not meaningfully address the incident → verdict INSUFFICIENT
- Single-technique incidents (e.g. only SQL Injection, only Phishing) naturally cover 1–2 phases — do NOT mark INSUFFICIENT just because Privilege Escalation or Lateral Movement are absent

STRATEGY — required whenever the verdict is INSUFFICIENT.
This is a fully automated retrieval loop. You CANNOT ask the user for more
information, and no further input will arrive: the incident description you
were given is all there will ever be. Recovery must come from re-querying the
knowledge base. You are on attempt {retry_hint} of {max_retries}.

Pick exactly ONE strategy:

1. BROADEN_SEARCH  ← prefer this while attempts remain
   Use when: the incident IS described but the retrieved context missed a phase
   Action: Re-query using parent technique names + the broader ATT&CK tactic,
           describing the missing attacker behavior in plain language
   Output: { "strategy": "BROADEN_SEARCH", "new_query": "..." }
   The new_query is embedded verbatim for vector search, so write ONE plain
   sentence: no markdown, no ATT&CK ID numbers (T1110, TA0006), no bullet lists.
   It must differ meaningfully from the queries already tried — repeating them
   retrieves the same context and wastes the attempt.

2. PARTIAL_ANSWER
   Use when: at least 2 phases are covered, only 1 detail is missing
   Action: Answer with covered phases, explicitly flag gaps
   Output: { "strategy": "PARTIAL_ANSWER", "gap_warning": "..." }

3. ACKNOWLEDGE_LIMIT
   Use when: the incident description is too vague to map (answerability gate
             above), or fewer than 2 phases are covered and attempts are spent
   Action: Tell the user what is missing — either that the description lacks
           the detail needed, or that the knowledge base has no data on this
           attack pattern. Write the message in the same language as the query.
   Output: { "strategy": "ACKNOWLEDGE_LIMIT", "message": "ฐานข้อมูล MITRE ATT&CK ที่มีอยู่ไม่มีข้อมูลเพียงพอสำหรับ..." }

Never use FORCE_SUFFICIENT — answering with known-incomplete context without flagging gaps misleads the analyst."""


# ──────────────────────────────────────────────────────────────────────────────
# Evaluator class
# ──────────────────────────────────────────────────────────────────────────────
class ContextEvaluator:
    """Evaluates whether retrieved context is sufficient to answer a query."""

    def __init__(self, use_local: bool = False) -> None:
        if use_local:
            from langchain_ollama import ChatOllama
            self.llm = ChatOllama(
                model=LOCAL_EVAL_MODEL,
                base_url=OLLAMA_BASE_URL,
                temperature=EVALUATOR_TEMPERATURE,
                num_predict=EVALUATOR_MAX_TOKENS,
            )
            print(f"[EVALUATOR] Local model: {LOCAL_EVAL_MODEL}")
        elif ANTHROPIC_API_KEY:
            self.llm = ChatAnthropic(  # type: ignore[call-arg]
                model_name=EVALUATOR_LLM_MODEL,
                api_key=ANTHROPIC_API_KEY,
                temperature=EVALUATOR_TEMPERATURE,
                max_tokens_to_sample=EVALUATOR_MAX_TOKENS,
            )
        else:
            self.llm = None

    # ------------------------------------------------------------------
    def evaluate(
        self,
        original_query: str,
        english_query: str,
        context: str,
        retry_count: int = 0,
        verbose: bool = True,
    ) -> EvaluationResult:
        """Judge context sufficiency.

        Args:
            original_query: The user's original query (may be Thai).
            english_query: The translated English query.
            context: The assembled context string from the retriever.
            retry_count: Number of re-retrieval attempts already made.
                         When this reaches MAX_RETRIES the evaluator
                         short-circuits to SUFFICIENT to avoid infinite loops.
            verbose: Print evaluation details.

        Returns:
            EvaluationResult with verdict + the fallback strategy (and its
            ``new_query`` / ``gap_warning`` / ``message`` payload).
        """
        # ── Max-retry guard — skip LLM call entirely ──────────────────
        if retry_count >= MAX_RETRIES:
            reason = (
                f"Max retries reached (attempt {retry_count}/{MAX_RETRIES}) "
                "— answering with best available context."
            )
            if verbose:
                sep("AGENT — CONTEXT EVALUATION")
                print(f"  Verdict : {VERDICT_SUFFICIENT} [forced — max retries]")
                print(f"  Reason  : {reason}")
            return EvaluationResult(
                verdict=VERDICT_SUFFICIENT,
                reason=reason,
            )

        if not self.llm:
            # No LLM → always assume sufficient (fall through to reasoning)
            return EvaluationResult(
                verdict=VERDICT_SUFFICIENT,
                reason="No LLM configured — skipping evaluation.",
            )

        user_prompt = self._build_prompt(
            original_query,
            english_query,
            context,
            retry_count,
        )

        if verbose:
            sep("AGENT — CONTEXT EVALUATION")

        system_prompt = EVALUATOR_SYSTEM_PROMPT.replace(
            "{retry_hint}", str(retry_count + 1)
        ).replace("{max_retries}", str(MAX_RETRIES))

        response = self.llm.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        )

        result = self._parse_response(str(response.content))

        if verbose:
            print(f"  Verdict   : {result.verdict}")
            print(f"  Reason    : {result.reason}")
            if result.strategy:
                print(f"  Strategy  : {result.strategy}")
            if result.new_query:
                print(f"  Rewrite   : {result.new_query}")
        return result

    # ------------------------------------------------------------------
    @staticmethod
    def _build_prompt(
        original_query: str,
        english_query: str,
        context: str,
        retry_count: int = 0,
    ) -> str:
        """Build the evaluation prompt."""
        parts = []

        # ── Retry hint ────────────────────────────────────────────────
        if retry_count > 0:
            parts.append(
                f"=== RETRY CONTEXT ==="
                f"\nThis is broaden iteration {retry_count} — the context below"
                " was retrieved with an already-rewritten query."
                "\nApply slightly looser sufficiency criteria — prefer SUFFICIENT"
                " when context is at least partially on-topic."
            )
            parts.append("")

        parts.append("=== USER QUERY ===")
        parts.append(f"Original : {original_query}")
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

        Extraction strategy (most → least strict):
        1. Regex: find the first complete ``{ … }`` block in the response,
           handles markdown fences (```json … ```) transparently.
        2. Brace scan: locate the outermost ``{`` … ``}`` pair and try to
           parse it — catches cases where the fence stripping leaves debris.
        3. Fallback: default to SUFFICIENT so the pipeline is never blocked.
        """
        import re as _re

        cleaned = raw.strip()

        # ── Stage 1: regex extraction of first complete JSON object ───────
        # Works whether the response is bare JSON or wrapped in ```json … ```
        match = _re.search(r"\{.*?\}", cleaned, _re.DOTALL)
        if match:
            candidate = match.group(0)
            try:
                data = json.loads(candidate)
                verdict = data.get("verdict", VERDICT_SUFFICIENT).upper().strip()
                if verdict not in VALID_VERDICTS:
                    verdict = VERDICT_SUFFICIENT
                return EvaluationResult(
                    verdict=verdict,
                    reason=data.get("reason", ""),
                    covered_phases=data.get("covered_phases", []),
                    missing_phases=data.get("missing_phases", []),
                    strategy=data.get("strategy", ""),
                    new_query=data.get("new_query", ""),
                    gap_warning=data.get("gap_warning", ""),
                    message=data.get("message", ""),
                )
            except json.JSONDecodeError:
                pass  # fall through to stage 2

        # ── Stage 2: brace-pair scan (handles truncated responses) ────────
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(cleaned[start : end + 1])
                verdict = data.get("verdict", VERDICT_SUFFICIENT).upper().strip()
                if verdict not in VALID_VERDICTS:
                    verdict = VERDICT_SUFFICIENT
                return EvaluationResult(
                    verdict=verdict,
                    reason=data.get("reason", ""),
                    covered_phases=data.get("covered_phases", []),
                    missing_phases=data.get("missing_phases", []),
                    strategy=data.get("strategy", ""),
                    new_query=data.get("new_query", ""),
                    gap_warning=data.get("gap_warning", ""),
                    message=data.get("message", ""),
                )
            except json.JSONDecodeError:
                pass

        # ── Stage 3: last-resort fallback ─────────────────────────────────
        return EvaluationResult(
            verdict=VERDICT_SUFFICIENT,
            reason=(
                f"Could not parse evaluator response — defaulting to SUFFICIENT. "
                f"Raw: {raw[:200]}"
            ),
        )
