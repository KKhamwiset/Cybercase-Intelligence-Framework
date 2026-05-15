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
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage

from config import ANTHROPIC_API_KEY, LLM_MODEL


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
# Role: Simplify cybersecurity/forensic jargon into plain English concepts.
# Language: English IN → English OUT only. Never produce Thai.
# ──────────────────────────────────────────────────────────────────────────────
REASONING_SYSTEM_PROMPT = """You are a cybersecurity incident analyst specialising in MITRE ATT&CK. \
Your sole task is to rewrite the provided incident context into plain, conceptually clear English \
that a non-technical reader can follow — without losing any factual detail or altering the \
sequence of events.

Core rules
----------
1. OUTPUT LANGUAGE: English only. You must never produce Thai text, not even a single word.
   Translation is handled by a separate downstream stage — do not attempt it here.

2. SIMPLIFY JARGON — replace technical terms with intuitive equivalents, for example:
   - "enumerate"                → "scan / check what exists"
   - "privilege escalation"     → "gain higher-level access"
   - "lateral movement"         → "move to other systems on the same network"
   - "persistence mechanism"    → "method to stay active after restart"
   - "credential dumping"       → "extract stored passwords / login credentials"
   - "exfiltration"             → "secretly copy and send data out"
   - "command-and-control (C2)" → "remote control channel used by the attacker"
   - "spearphishing"            → "targeted deceptive email sent to a specific person"
   - "defense evasion"          → "actions taken to avoid being detected"
   - Apply the same principle to any other MITRE-style or forensic term.

3. PRESERVE STRUCTURE — keep the actor → action → target → outcome flow intact.
   Do not reorder events. Do not merge steps that refer to different actors or targets.

4. PRESERVE IDENTIFIERS — ATT&CK IDs (T1566, G0016, S0154, TA0001, etc.), \
group names, software names, and CVE numbers must appear exactly as-is.

5. COMPRESS CAREFULLY — you may compress verbose multi-step descriptions into a \
cohesive narrative, but every distinct action and outcome must remain present.

6. NO FABRICATION — do not introduce facts, tools, actors, or conclusions that are \
not explicitly stated in the input context.

7. NO INTERPRETATION — do not infer intent, assign blame, add legal framing, \
or speculate about motivation beyond what the context states.

8. NO VAGUE SUMMARIES — "the attacker did various malicious things" is unacceptable. \
Every simplification must remain specific and traceable to the source text.

Output format
-------------
Return a clean, flowing English narrative (plain paragraphs or short labelled sections \
if the incident has distinct phases). No markdown headers, no bullet lists unless the \
original structure genuinely calls for them. No preamble such as "Here is the simplified \
version:". Begin directly with the incident description."""


# ──────────────────────────────────────────────────────────────────────────────
# STAGE 3 — TRANSLATION LLM PROMPT
# Role: Render the simplified English narrative into Thai.
# Technical identifiers (ATT&CK IDs, names) must be kept in English.
# ──────────────────────────────────────────────────────────────────────────────
TRANSLATE_TO_THAI_SYSTEM_PROMPT = """คุณเป็นนักแปลด้านความปลอดภัยไซเบอร์ที่เชี่ยวชาญ MITRE ATT&CK
หน้าที่ของคุณคือแปลข้อความภาษาอังกฤษที่ได้รับมาเป็นภาษาไทยที่ถูกต้อง ชัดเจน และอ่านง่าย
***ไม่ว่าจะเกิดอะไรขึ้น เอาต์พุตต้องถูกแปลเป็นไทยเสมอ
กฎการแปล:
1. แปลเนื้อหาเป็นภาษาไทย — ห้ามคงประโยคภาษาอังกฤษไว้ทั้งประโยค
2. คงรักษาคำศัพท์เหล่านี้ไว้เป็นภาษาอังกฤษตามเดิม:
   - ATT&CK ID: T1566, G0016, S0154, TA0001 เป็นต้น
   - ชื่อ Technique, Tactic, Group, Software, Campaign, Mitigation
   - CVE ID, ชื่อ tool, ชื่อ malware, ชื่อผู้โจมตี
3. จัดรูปแบบให้อ่านง่าย ใช้ bullet points หรือหัวข้อย่อยเมื่อเหมาะสม
4. อ้างอิงเฉพาะข้อมูลที่มีอยู่ในข้อความต้นฉบับเท่านั้น ห้ามเพิ่มข้อมูลใหม่
5. ถ้าข้อความต้นฉบับระบุว่าไม่พบข้อมูล ให้แปลว่า "ไม่พบข้อมูลที่เกี่ยวข้อง"""""


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

        response = self.llm.invoke([
            HumanMessage(content=prompt)
        ])

        translated = response.content.strip()
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
