"""
Context Sufficiency Evaluator
==============================
Uses the LLM to judge whether retrieved context can adequately answer
the user's query.  Returns one of two verdicts:

  SUFFICIENT    → proceed to reasoning
  INSUFFICIENT  → ask the user a targeted follow-up question

This is the "Self-RAG" reflective loop that makes the pipeline *agentic*.

Slot-awareness
--------------
- The evaluator receives ``incident_facts`` (already-known structured facts)
  and ``asked_slots`` (slots already asked about) so it never re-asks for
  information the user already provided.
- On follow-up iteration ≥ 2 (MAX_FOLLOWUP) the agent short-circuits to
  SUFFICIENT without calling the LLM, to prevent infinite loops.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

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
# Legacy constant kept for backwards-compat; no longer returned by the LLM
VERDICT_NEED_CLARIFICATION = "NEED_CLARIFICATION"

VALID_VERDICTS = {VERDICT_SUFFICIENT, VERDICT_INSUFFICIENT, VERDICT_NEED_CLARIFICATION}

# Maximum follow-up iterations before we force SUFFICIENT (guarded in agent_graph)
MAX_RETRIES = 2


@dataclass
class EvaluationResult:
    """Structured result from the context evaluator."""

    verdict: str  # SUFFICIENT | INSUFFICIENT
    reason: str  # Brief justification
    covered_phases: list[str] = None
    missing_phases: list[str] = None
    missing_slot: str = ""
    follow_up: str = ""
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

RULES:
- Judge based on SEMANTIC coverage, not exact keyword match
- If the context contains techniques that MAP to the described behavior, mark as SUFFICIENT
- A technique is "covered" if its description matches the attack behavior, even if not explicitly named
- Only mark INSUFFICIENT if a critical attack phase is completely absent from context
- Prefer SUFFICIENT over INSUFFICIENT when in doubt — it is better to answer with partial context than to over-ask

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
  "missing_slot": "<slot_name or null>",
  "reason": "<brief explanation>",
  "follow_up": "<question if INSUFFICIENT, else null>",
  "strategy": "<BROADEN_SEARCH | PARTIAL_ANSWER | ACKNOWLEDGE_LIMIT or null>",
  "new_query": "<new query if BROADEN_SEARCH, else null>",
  "gap_warning": "<warning if PARTIAL_ANSWER, else null>",
  "message": "<message if ACKNOWLEDGE_LIMIT, else null>"
}

Threshold:
- If 2 or more phases are covered → verdict SUFFICIENT
- If only 1 phase is covered but the context clearly explains that phase → verdict SUFFICIENT
- If fewer than 2 phases are covered AND the context does not meaningfully address the incident → verdict INSUFFICIENT, ask about the most critical missing phase
- Single-technique incidents (e.g. only SQL Injection, only Phishing) naturally cover 1–2 phases — do NOT mark INSUFFICIENT just because Privilege Escalation or Lateral Movement are absent

You are tracking information slots for a multi-turn incident analysis.

SLOT DEFINITIONS (strictly follow these):
- initial_access     : How attacker first entered the system (e.g., phishing, SQL injection, exposed service)
- credential_theft   : How attacker obtained credentials (e.g., keylogger, phishing, credential dump)
- privilege_escalation: How attacker elevated privileges AFTER obtaining credentials (e.g., exploit CVE, sudo abuse, token impersonation)
- lateral_movement   : How attacker moved to other systems (optional)
- impact             : What damage was done (e.g., data deletion, ransomware, exfiltration)

IMPORTANT:
- Phishing is credential_theft OR initial_access — NOT privilege_escalation
- "Login as admin with stolen password" = Valid Credentials (T1078), NOT privilege_escalation exploit
- Only ask follow-up for the NEXT unfilled slot in attack chain order

Current filled slots: {filled_slots}
Next missing slot: {next_missing_slot}

Generate follow-up question targeting ONLY the next missing slot. The question MUST be in the same language as the user's original query.

You are deciding the fallback strategy when context is still INSUFFICIENT after {max_retries} attempts.
(If the number of attempts is less than {max_retries}, set strategy to null and provide a follow_up question).

Available strategies (pick ONE based on situation):

1. BROADEN_SEARCH
   Use when: missing slot is a technique detail (sub-technique level)
   Action: Re-query using parent technique name + broader ATT&CK tactic
   Output: { "strategy": "BROADEN_SEARCH", "new_query": "..." }

2. PARTIAL_ANSWER
   Use when: at least 2 phases are covered, only 1 detail is missing
   Action: Answer with covered phases, explicitly flag gaps
   Output: { "strategy": "PARTIAL_ANSWER", "gap_warning": "..." }

3. ACKNOWLEDGE_LIMIT
   Use when: fewer than 2 phases covered even after retries
   Action: Tell user the knowledge base lacks sufficient data on this attack pattern
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
                model=EVALUATOR_LLM_MODEL,
                api_key=ANTHROPIC_API_KEY,
                temperature=EVALUATOR_TEMPERATURE,
                max_tokens=EVALUATOR_MAX_TOKENS,
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
        incident_facts: Optional[dict] = None,
        asked_slots: Optional[list] = None,
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
            incident_facts: Structured facts already collected from the user,
                            e.g. {"initial_access": "SQL Injection"}.
            asked_slots: List of slot names already asked about, e.g.
                         ["initial_access"]. The evaluator will not generate
                         a follow-up question targeting these slots.

        Returns:
            EvaluationResult with verdict + optional follow-up question and
            slot_name identifying the missing information gap.
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
            incident_facts=incident_facts or {},
            asked_slots=asked_slots or [],
        )

        if verbose:
            sep("AGENT — CONTEXT EVALUATION")

        # Determine next missing slot based on the ordered list
        ordered_slots = [
            "initial_access",
            "credential_theft",
            "privilege_escalation",
            "lateral_movement",
            "impact",
        ]
        next_missing_slot = "unknown"
        for slot in ordered_slots:
            if slot not in (asked_slots or []) and slot not in (incident_facts or {}):
                next_missing_slot = slot
                break

        system_prompt = (
            EVALUATOR_SYSTEM_PROMPT.replace(
                "{filled_slots}", json.dumps(list((incident_facts or {}).keys()))
            )
            .replace("{next_missing_slot}", next_missing_slot)
            .replace("{max_retries}", str(MAX_RETRIES))
        )

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
            if result.missing_slot:
                print(f"  Slot      : {result.missing_slot}")
            if result.follow_up:
                print(f"  Follow-up : {result.follow_up}")
            if result.strategy:
                print(f"  Strategy  : {result.strategy}")
        return result

    # ------------------------------------------------------------------
    @staticmethod
    def _build_prompt(
        original_query: str,
        english_query: str,
        context: str,
        retry_count: int = 0,
        incident_facts: Optional[dict] = None,
        asked_slots: Optional[list] = None,
    ) -> str:
        """Build the evaluation prompt.

        Injects known incident facts and already-asked slots so the LLM
        never re-asks for information the user already provided.
        """
        parts = []

        # ── Known incident facts (structured answers already collected) ────
        facts = incident_facts or {}
        slots = asked_slots or []

        if facts:
            parts.append("=== KNOWN INCIDENT FACTS ===")
            for slot, value in facts.items():
                parts.append(f"  {slot}: {value}")
            parts.append(
                "\nThese facts are already known. "
                "Do NOT ask about them again. Treat them as confirmed information."
            )
            parts.append("")

        if slots:
            parts.append("=== ALREADY ASKED SLOTS ===")
            parts.append(", ".join(slots))
            parts.append(
                "\nDo NOT generate a follow-up question targeting any of these slots."
            )
            parts.append("")

        # ── Retry hint ────────────────────────────────────────────────
        if retry_count > 0:
            parts.append(
                f"=== RETRY CONTEXT ==="
                f"\nThis is follow-up iteration {retry_count}."
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
                    missing_slot=data.get("missing_slot", ""),
                    follow_up=data.get("follow_up", ""),
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
                    missing_slot=data.get("missing_slot", ""),
                    follow_up=data.get("follow_up", ""),
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

