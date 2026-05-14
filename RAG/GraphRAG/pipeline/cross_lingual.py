"""
Cross-Lingual Translation Layer
=================================
Handles Thai ↔ English translation for the cross-lingual RAG pipeline.

Strategy:
  - Pre-retrieval:  Thai query → English query (for vector/graph search)
  - Post-generation: LLM system prompt instructs Thai output
  - Technical terms (ATT&CK IDs, technique names, group names) are preserved as-is
"""

import re
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage

from RAG.GraphRAG.config import ANTHROPIC_API_KEY, LLM_MODEL


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
# THAI RESPONSE SYSTEM PROMPT
# ──────────────────────────────────────────────────────────────────────────────
THAI_SYSTEM_PROMPT = """คุณเป็นผู้เชี่ยวชาญด้าน Cybersecurity ที่มีความรู้ลึกเกี่ยวกับ MITRE ATT&CK Framework
คุณต้องตอบคำถามเป็นภาษาไทยเสมอ โดยปฏิบัติตามกฎต่อไปนี้:

1. ตอบเป็นภาษาไทย แต่คงศัพท์เทคนิคเป็นภาษาอังกฤษ เช่น:
   - ชื่อ Technique, Tactic, Group, Software, Campaign, Mitigation → ภาษาอังกฤษ
   - ATT&CK ID (T1566, G0016, S0154) → ภาษาอังกฤษ
   - ศัพท์เฉพาะ เช่น Phishing, Lateral Movement, Credential Dumping → ภาษาอังกฤษ

2. จัดรูปแบบคำตอบให้อ่านง่าย ใช้ bullet points หรือ numbered lists เมื่อเหมาะสม

3. อ้างอิงข้อมูลจาก context ที่ได้รับเท่านั้น ถ้าไม่มีข้อมูลในContext ให้บอกว่าไม่พบข้อมูล

4. ถ้ามีข้อมูลความสัมพันธ์จาก Graph Context ให้อธิบายความเชื่อมโยงระหว่าง entities ด้วย

5. ระบุ ATT&CK ID กำกับทุกครั้งที่กล่าวถึง technique, group, software หรือ mitigation"""


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
    def get_system_prompt() -> str:
        """Get the Thai response system prompt for the generation LLM."""
        return THAI_SYSTEM_PROMPT

    @staticmethod
    def should_respond_in_thai(query: str) -> bool:
        """Determine if the response should be in Thai based on the query language."""
        return _is_thai(query)
