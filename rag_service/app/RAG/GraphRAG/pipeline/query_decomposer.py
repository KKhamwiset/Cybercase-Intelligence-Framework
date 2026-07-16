"""
Query Decomposer
================
Breaks a compound security-incident query into multiple ATOMIC MITRE search
queries — one per distinct attacker action — so each technique is retrieved on
its own channel (parallel multi-query retrieval, fed into ``retrieve_multi_quota``).

Language policy
---------------
Sub-queries are emitted in the SAME language as the incident (Thai stays Thai).
We deliberately do NOT translate to English: BGE-M3 is multilingual, so a Thai
sub-query matches the English MITRE corpus directly. Well-known MITRE technique
names (SQL Injection, Phishing, …) are kept verbatim — they already appear in
English inside Thai incident text and anchor the sparse channel. This replaces
the old Thai↔English dual-query / input-translation step entirely.

Example
-------
"ผู้ต้องหาใช้ SQL Injection เจาะระบบ แล้ว dump credential เพื่อยกระดับสิทธิ์
 จากนั้นลบฐานข้อมูล PostgreSQL ทั้งหมด"
  →
  - SQL Injection เจาะเว็บแอปพลิเคชันเพื่อเข้าถึงระบบครั้งแรก
  - dump credential เพื่อขโมยข้อมูลบัญชี
  - ยกระดับสิทธิ์เป็น root / administrator
  - ลบหรือทำลายข้อมูลในฐานข้อมูล

Uses the STOCK utility model (``LLM_MODEL`` / ``LOCAL_LLM_MODEL``), NOT the MITRE
fine-tune — decomposition is an instruction-following task; the fine-tune would
answer the question instead of planning queries.
"""

from __future__ import annotations

import re

from langchain_core.messages import HumanMessage, SystemMessage

from ..config import (
    ANTHROPIC_API_KEY,
    LLM_MODEL,
    LOCAL_LLM_MODEL,
    LOCAL_NUM_CTX,
    OLLAMA_BASE_URL,
)

_SYSTEM = (
    "You are a retrieval query planner for a MITRE ATT&CK RAG system. Given a "
    "cybersecurity incident description, break it into ATOMIC search queries — "
    "one per distinct attacker action across the kill chain (initial access, "
    "execution, persistence, privilege escalation, credential access, discovery, "
    "lateral movement, collection, exfiltration, impact).\n\n"
    "RULES:\n"
    "1. Cover EVERY stage actually present in the incident. Do NOT stop early — if "
    "the incident describes data theft / exfiltration / destruction at the end, you "
    "MUST emit a sub-query for it (these late stages matter most for the case).\n"
    "2. Each sub-query must be a SPECIFIC phrase grounded in the incident: include "
    "the action AND its object/target as described. Do NOT output bare category "
    "words like 'Malware', 'Execution', 'Discovery' on their own — they retrieve "
    "generic detection metadata, not the real technique.\n"
    "3. Write each sub-query in the SAME LANGUAGE as the incident (Thai stays Thai); "
    "keep well-known MITRE names verbatim (e.g. 'SQL Injection', 'Phishing', "
    "'Mimikatz', 'RDP').\n"
    "4. Output ONE query per line, plain text, no numbering, no commentary.\n"
    "5. If the input does NOT actually describe an incident — no concrete attacker "
    "actions to search for (e.g. it only says 'this incident' / 'the attack' without "
    "details, or is a meta-request) — output exactly one line: NONE\n"
    "6. NEVER address the user, ask for clarification, or request more details. Your "
    "output is fed directly into a retrieval engine — any sentence that is not a "
    "search query (or NONE) becomes a garbage retrieval query.\n\n"
    "Example incident: 'ผู้ต้องหาส่งอีเมลฟิชชิ่งให้พนักงานเปิดไฟล์แนบมัลแวร์ "
    "ติดตั้ง backdoor แล้วขโมยรหัสผ่าน ยกระดับสิทธิ์เป็น admin ก่อนคัดลอกฐานข้อมูล "
    "ลูกค้าส่งออกไปเซิร์ฟเวอร์ภายนอก'\n"
    "Example output:\n"
    "อีเมล Phishing พร้อมไฟล์แนบมัลแวร์หลอกพนักงานเปิดไฟล์\n"
    "มัลแวร์ติดตั้ง backdoor เพื่อคงการเข้าถึงเครื่อง\n"
    "ขโมยรหัสผ่านที่เก็บไว้ในเครื่อง (credential theft)\n"
    "ยกระดับสิทธิ์เป็น administrator\n"
    "คัดลอกข้อมูลฐานข้อมูลลูกค้า\n"
    "ส่งข้อมูลออกไปยังเซิร์ฟเวอร์ภายนอก (exfiltration)"
)

# Cap high enough to hold a full kill chain (~10 stages). The decomposer lists in
# kill-chain order, so a low cap silently dropped the late stages (exfiltration /
# impact) — exactly the ones a prosecutor case needs.
_MAX_SUBQUERIES = 10

# Sentinel the LLM emits (prompt rule 5) when the input has no incident to
# decompose — e.g. "map this incident" with nothing attached.
_NO_INCIDENT_RE = re.compile(r"none\.?", re.IGNORECASE)

# Openers that mark a line as the LLM talking to the user (clarification
# request, refusal, question, preamble) instead of a retrieval query. Real
# sub-queries are action phrases — never questions, never first-person prose.
# Thai sub-queries stay Thai, so English interrogatives never collide.
_CONVERSATIONAL_RE = re.compile(
    r"^(?:i['’]m\b|i\s+(?:am|cannot|can['’]t|notice|need|will|would|apologize)\b"
    r"|please\b|sorry\b|unfortunately\b|however\b|sure\b|here\s+(?:is|are)\b"
    r"|for\s+example\b|such\s+as\b|provide\b"
    r"|(?:what|how|when|where|who|why|which|whether|could|can|do|does|did|is|are|was|were)\s)",
    re.IGNORECASE,
)


def _is_conversational(line: str) -> bool:
    """True when a line addresses the user rather than the retrieval engine."""
    if line.endswith("?") or line.endswith(":"):
        return True
    if "**" in line:  # markdown emphasis = commentary, never a query
        return True
    return bool(_CONVERSATIONAL_RE.match(line))


def _parse(text: str, cap: int) -> list[str]:
    """Turn the LLM's line-per-query output into a clean, deduped query list.

    Returns [] when the reply is the NONE sentinel or conversational prose (a
    clarification request / refusal) — the caller then falls back to the whole
    query. Without this, a "please provide the incident details…" reply was
    split line-by-line into garbage retrieval queries that burned the entire
    multi-query quota.
    """
    out: list[str] = []
    seen: set[str] = set()
    rejected = 0
    for line in text.splitlines():
        line = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line.strip())  # strip bullets/numbers
        line = line.strip(" \"'`")
        if _NO_INCIDENT_RE.fullmatch(line):
            return []
        if len(line) < 4:
            continue
        if _is_conversational(line):
            rejected += 1
            continue
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(line)
    # More rejected than kept → the whole reply was prose; the survivors are
    # stray bullet fragments from it, not real queries.
    if rejected > len(out):
        return []
    return out[:cap]


class QueryDecomposer:
    """LLM step: incident → list of atomic, native-language sub-queries."""

    def __init__(self, use_local: bool = False):
        self.llm = None
        if use_local:
            from langchain_ollama import ChatOllama

            self.llm = ChatOllama(
                model=LOCAL_LLM_MODEL,
                base_url=OLLAMA_BASE_URL,
                temperature=0,
                num_predict=256,
                num_ctx=LOCAL_NUM_CTX,
                reasoning=False,  # Qwen3.5: keep <think> out of the query list
            )
            print(f"[DECOMPOSE] Local model: {LOCAL_LLM_MODEL}")
        elif ANTHROPIC_API_KEY:
            from langchain_anthropic import ChatAnthropic

            self.llm = ChatAnthropic(  # type: ignore[call-arg]
                model_name=LLM_MODEL,
                api_key=ANTHROPIC_API_KEY,
                temperature=0,
                max_tokens_to_sample=512,
            )
        else:
            print("[DECOMPOSE] No LLM — falling back to the whole query")

    def decompose(
        self,
        incident: str,
        max_subqueries: int = _MAX_SUBQUERIES,
        verbose: bool = True,
    ) -> list[str]:
        """Return atomic native-language sub-queries, or a single-element fallback."""
        if not self.llm or not incident or not incident.strip():
            return [incident]

        try:
            resp = self.llm.invoke(
                [
                    SystemMessage(content=_SYSTEM),
                    HumanMessage(content=f"Incident:\n{incident}"),
                ]
            )
            subs = _parse(str(resp.content), max_subqueries)
        except Exception as e:  # network / model error → don't sink retrieval
            print(f"[DECOMPOSE] failed ({e}); using the whole query")
            return [incident]

        if not subs:
            if verbose:
                print(
                    "[DECOMPOSE] no usable sub-queries (NONE / conversational "
                    "reply) — using the whole query"
                )
            return [incident]

        if verbose:
            print(f"[DECOMPOSE] {len(subs)} sub-queries:")
            for i, s in enumerate(subs, 1):
                print(f"  ({i}) {s}")
        return subs
