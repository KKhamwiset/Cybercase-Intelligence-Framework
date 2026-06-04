"""
Cross-Lingual Translation Layer
=================================
Handles language routing for the cross-lingual RAG pipeline.

Pipeline stages:
  1. Pre-retrieval  : Thai query  → English query  (query translate LLM)
  2. Reasoning      : English context → Simplified English narrative (reasoning LLM)
  3. Translation    : Simplified English → Thai output (translation LLM)

Technical terms (ATT&CK IDs, technique names, group names) are preserved as-is
throughout all stages.
"""

import re

from ..config import ANTHROPIC_API_KEY, LLM_MODEL
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

# ──────────────────────────────────────────────────────────────────────────────
# TRANSLATION PROMPT
# ──────────────────────────────────────────────────────────────────────────────
TRANSLATE_TO_ENGLISH_PROMPT = """You are a cybersecurity translation assistant.
Translate the following Thai query into English for searching the MITRE ATT&CK knowledge base.

Rules:
1. Preserve all technical terms exactly as they appear (e.g., APT29, T1566, Phishing, Ransomware, MITRE ATT&CK)
2. Preserve any ATT&CK IDs (T####, G####, S####, M####, TA####, C####)
3. If the query is already in English, return it as-is
4. If the query mixes Thai and English, translate only the Thai parts
5. Return ONLY the translated query, nothing else

Thai query: {query}"""

# ──────────────────────────────────────────────────────────────────────────────
# STAGE 2 — REASONING LLM SYSTEM PROMPT
# Role: Translate cybersecurity jargon into plain language for non-technical readers.
# Language: English IN → English OUT only. Never produce Thai.
# ──────────────────────────────────────────────────────────────────────────────
REASONING_SYSTEM_PROMPT = """You are a cybersecurity incident analyst specialising in MITRE ATT&CK. \
Your task is to rewrite the provided incident context into plain, easy-to-understand English \
for a non-technical reader — without losing any factual detail or altering the sequence of events.

Core rules
----------
1. OUTPUT LANGUAGE: English only. Never produce Thai — translation is handled downstream.

2. SIMPLIFY JARGON — replace every technical term with a plain equivalent, for example:
   - "exploit a vulnerability"   → "take advantage of a security weakness"
   - "privilege escalation"      → "gain administrator-level control of the system"
   - "lateral movement"          → "move to other machines on the same network"
   - "persistence mechanism"     → "a method installed to keep access even after restart"
   - "credential dumping"        → "extracting stored usernames and passwords from the system"
   - "exfiltration"              → "secretly copying and sending data to an outside server"
   - "command-and-control (C2)"  → "a hidden channel used to remotely control the infected system"
   - "spearphishing attachment"  → "a deceptive email with a malicious file sent to a specific target"
   - "defense evasion"           → "steps taken to avoid being detected by security tools"
   - Apply the same principle to any other MITRE-style or forensic term.

3. PRESERVE STRUCTURE — keep the actor → action → target → outcome flow intact. \
Do not reorder events or merge distinct steps.

4. PRESERVE IDENTIFIERS — ATT&CK IDs (T1566, TA0001, G0016, S0154, etc.), \
software names, group names, and CVE numbers must appear verbatim.

5. NO FABRICATION — only state facts explicitly present in the provided context.

6. NO INTERPRETATION — do not infer intent, assign blame, add legal framing, \
or draw conclusions beyond what the context states. \
The reader will draw their own conclusions from the plain-language description.

7. NO VAGUE SUMMARIES — every statement must be specific and traceable to the source context.

Output format — use EXACTLY these four section headers:
--------------------------------------------------------
## INCIDENT SUMMARY
One concise paragraph: what happened, to which system, and what was the outcome.

## ATTACK SEQUENCE
Numbered chronological steps. Each step: plain-language description of the action \
+ the corresponding ATT&CK technique in parentheses.
Example: 1. The attacker sent a deceptive email containing a malicious file to an employee \
(Spearphishing Attachment — T1566.001).

## MITRE ATT&CK TECHNIQUES IDENTIFIED
Bullet list. Each entry: [ID] Technique Name — one sentence explaining what this technique \
means in the context of this specific incident.

## IMPACT ASSESSMENT
- What data or systems were affected and the scope of access obtained.
- What damage or disruption occurred as a direct result of the attack.
--------------------------------------------------------
Begin directly with "## INCIDENT SUMMARY". No preamble."""


# ──────────────────────────────────────────────────────────────────────────────
# STAGE 3 — TRANSLATION LLM PROMPT
# Role: Render the simplified English narrative into Thai.
# Technical identifiers (ATT&CK IDs, names) must be kept in English.
# ──────────────────────────────────────────────────────────────────────────────
TRANSLATE_TO_THAI_SYSTEM_PROMPT = (
    """คุณเป็นนักแปลด้านความปลอดภัยไซเบอร์ที่เชี่ยวชาญ MITRE ATT&CK
หน้าที่ของคุณคือแปลรายงานภาษาอังกฤษเป็นภาษาไทยที่ถูกต้อง ชัดเจน และอ่านง่ายสำหรับผู้ที่ไม่มีพื้นฐานเทคนิค

กฎการแปล:
1. แปลเนื้อหาทุกส่วนเป็นภาษาไทย — ห้ามคงประโยคภาษาอังกฤษไว้ทั้งประโยค
2. คงรักษาคำศัพท์ต่อไปนี้ไว้เป็นภาษาอังกฤษเสมอ:
   - ATT&CK ID: T1566, G0016, S0154, TA0001 เป็นต้น
   - ชื่อ Technique, Tactic, Group, Software, Campaign, Mitigation
   - CVE ID, ชื่อ tool, ชื่อ malware, ชื่อผู้โจมตี
3. คงโครงสร้างหัวข้อทั้งสี่ส่วนไว้ตามเดิม โดยแปลชื่อหัวข้อดังนี้:
   - "INCIDENT SUMMARY"                   → "สรุปเหตุการณ์"
   - "ATTACK SEQUENCE"                    → "ลำดับการโจมตี"
   - "MITRE ATT&CK TECHNIQUES IDENTIFIED" → "เทคนิคการโจมตีที่ตรวจพบ (MITRE ATT&CK)"
   - "IMPACT ASSESSMENT"                  → "ผลกระทบที่เกิดขึ้น"
4. อ้างอิงเฉพาะข้อมูลที่มีอยู่ในข้อความต้นฉบับเท่านั้น ห้ามเพิ่มข้อมูลหรือตีความใหม่
5. ถ้าข้อความต้นฉบับระบุว่าไม่พบข้อมูล ให้แปลว่า "ไม่พบข้อมูลที่เกี่ยวข้อง" """
    ""
)


def _is_thai(text: str) -> bool:
    """Check if text contains Thai characters."""
    thai_pattern = re.compile(r"[\u0E00-\u0E7F]")
    return bool(thai_pattern.search(text))


def _is_mostly_english(text: str) -> bool:
    """Check if text is predominantly English."""
    ascii_chars = sum(1 for c in text if c.isascii() and c.isalpha())
    total_alpha = sum(1 for c in text if c.isalpha())
    if total_alpha == 0:
        return True
    return (ascii_chars / total_alpha) > 0.7


class CrossLingualLayer:
    """Manages Thai ↔ English translation for cross-lingual RAG."""

    def __init__(self):
        if not ANTHROPIC_API_KEY:
            print("[WARN] No ANTHROPIC_API_KEY — translation will be skipped")
            self.llm = None
        else:
            self.llm = ChatAnthropic(
                model=LLM_MODEL,
                api_key=ANTHROPIC_API_KEY,
                temperature=0,
                max_tokens=256,
            )

    def translate_query(self, query: str) -> str:
        """Translate a Thai query to English for retrieval.

        If the query is already in English, returns it as-is.
        If no LLM is available, returns the original query.
        """
        # Skip translation if already English
        if not _is_thai(query) or _is_mostly_english(query):
            print(f"[TRANSLATE] Query is English, skipping translation")
            return query

        if not self.llm:
            print(f"[TRANSLATE] No LLM available, using original query")
            return query

        print(f"[TRANSLATE] Thai → English...")

        prompt = TRANSLATE_TO_ENGLISH_PROMPT.format(query=query)

        response = self.llm.invoke([HumanMessage(content=prompt)])

        translated = response.content
        print(f"[TRANSLATE] Original: {query}")
        print(f"[TRANSLATE] English:  {translated}")

        return translated

    @staticmethod
    def get_reasoning_system_prompt() -> str:
        """Return the system prompt for the Reasoning LLM (Stage 2).

        This prompt instructs the LLM to simplify cybersecurity jargon into
        plain English. The output is always English — never Thai.
        """
        return REASONING_SYSTEM_PROMPT

    @staticmethod
    def get_translation_system_prompt() -> str:
        """Return the system prompt for the Translation LLM (Stage 3).

        This prompt instructs the LLM to render the simplified English
        narrative into Thai, preserving all ATT&CK identifiers as-is.
        """
        return TRANSLATE_TO_THAI_SYSTEM_PROMPT

    @staticmethod
    def should_respond_in_thai(query: str) -> bool:
        """Determine if the final output should be in Thai based on the query language."""
        return _is_thai(query)
