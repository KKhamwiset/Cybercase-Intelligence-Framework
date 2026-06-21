import re

from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

# CJK ideographs + Japanese kana + Korean Hangul. Haiku occasionally code-switches
# a single word into Chinese mid-Thai (e.g. "隔离" for "isolate"); a strict Thai-only
# prompt does NOT reliably stop it, so we detect + repair after generation.
_CJK_RE = re.compile(r"[぀-ヿ㐀-䶿一-鿿가-힣豈-﫿]")

from ..config import (
    ANTHROPIC_API_KEY,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_TEMPERATURE,
    LOCAL_LLM_MODEL,
    OLLAMA_BASE_URL,
)


class MitreEntity(BaseModel):
    """One retrieved MITRE ATT&CK entity for the output table (part 2).

    Sourced straight from RETRIEVAL (vector hits + graph nodes), NOT the LLM — so
    the IDs are real and never hallucinated. Use this (not the LLM's
    ``mitre_mapping``) to render the ID table.
    """

    id: str = Field(..., description="ATT&CK ID, e.g. T1566, G0016, S0154, M1037, TA0001")
    name: str = Field(..., description="Entity name, e.g. Phishing")
    type: str = Field(
        ...,
        description="Entity type: Technique / Subtechnique / Tactic / Group / Software / Mitigation / Campaign",
    )


class CyberCaseReport(BaseModel):
    """Structured incident report matching the 7 required sections."""

    case_summary: str = Field(
        ...,
        description="5.1 Case Summary (สรุปคดี): A concise summary of the security incident in Thai.",
    )
    detected_indicators: list[str] = Field(
        ...,
        description="5.2 Detected Indicators/Artifacts (ตัวบ่งชี้ที่พบ): List of IoCs, file hashes, IP addresses, or artifacts found.",
    )
    mitre_mapping: list[str] = Field(
        ...,
        description="5.3 MITRE ATT&CK Mapping (พื้นที่แสดงผล MITRE Mapping): List of MITRE ATT&CK techniques mapped to the incident (e.g., T1566).",
    )
    mitre_entities: list[MitreEntity] = Field(
        default_factory=list,
        description="ตาราง MITRE ATT&CK (ส่วน 2): the FAITHFUL retrieved entities "
        "(id/name/type) for the output table. Populated from retrieval (not the "
        "LLM) after generation, so IDs are never hallucinated. Render the table "
        "from THIS, not from mitre_mapping.",
    )
    mapping_justification: str = Field(
        ...,
        description="5.4 Mapping Justification/Reasoning (เหตุผลของการ mapping): Explanation for why the specific MITRE techniques were chosen.",
    )
    evidence_to_investigate: list[str] = Field(
        ...,
        description="5.5 Evidence to Investigate/Validate (หลักฐานที่ควรตรวจสอบ): Logs or data sources analysts should check to verify the incident.",
    )
    preliminary_recommendations: list[str] = Field(
        ...,
        description="5.6 Preliminary Recommendations (คำแนะนำเบื้องต้น): Immediate actions to mitigate or remediate the threat.",
    )
    system_limitations: str = Field(
        ...,
        description="5.7 System Limitations (ข้อจำกัดของระบบ): Caveats or missing data that limit the accuracy of this report.",
    )
    legal_advice: str | None = Field(
        default=None,
        description="คำแนะนำทางกฎหมาย (จาก Thanoy): preliminary Thai-law analysis "
        "(relevant statutes/มาตรา + damages) for this incident, with a disclaimer. "
        "Populated separately via the Thanoy API after the report is generated; "
        "None when Thanoy is disabled or unavailable.",
    )


class ReportGenerator:
    """Generates structured cybersecurity reports using GraphRAG context."""

    def __init__(self, use_local: bool = False) -> None:
        self.use_local = use_local

        if use_local:
            from langchain_ollama import ChatOllama

            # reasoning=False disables Qwen3.5 thinking (no <think> in the report).
            self.llm = ChatOllama(
                model=LOCAL_LLM_MODEL,
                base_url=OLLAMA_BASE_URL,
                temperature=0,
                num_predict=LLM_MAX_TOKENS,
                reasoning=False,
            )
            print(f"[REPORT] Local model: {LOCAL_LLM_MODEL}")
        elif ANTHROPIC_API_KEY:
            self.llm = ChatAnthropic(
                model_name=LLM_MODEL,
                api_key=ANTHROPIC_API_KEY,
                temperature=0,  # Strict reporting
                max_tokens_to_sample=LLM_MAX_TOKENS,
            )
        else:
            self.llm = None
            print(
                "[REPORT] Warning: no LLM configured "
                "(set ANTHROPIC_API_KEY, or USE_LOCAL=true + Ollama). Report generation will fail."
            )
            return

        # with_structured_output → guaranteed schema. Claude uses tool-calling;
        # ChatOllama uses Ollama structured outputs (JSON-schema `format`). On a
        # small local model schema adherence is LESS reliable than Claude — verify
        # the 7-section output when running USE_LOCAL.
        self.structured_llm = self.llm.with_structured_output(CyberCaseReport)

        self.prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You are an elite Cyber Threat Intelligence (CTI) analyst supporting Thai cybercrime case review. "
                        "Your task is to analyze the provided security incident context and generate a preliminary cyber case analysis/report draft in Thai language. "
                        "The report must support human investigators, prosecutors, or related reviewers by summarizing the case details, cyber techniques/methods, MITRE ATT&CK mapping, evidence-based justification, limitations, and recommended next validation steps. "
                        "You must strictly follow the provided 7-section structure. "
                        "Base your analysis ONLY on the provided context. If information is missing, "
                        "note it in the 'System Limitations' section.\n\n"
                        "LANGUAGE: Every field MUST be written in 100% Thai. Do NOT use Chinese, "
                        "Japanese, Korean, or any non-Thai prose. The ONLY tokens allowed to stay "
                        "in English are preserved technical identifiers — ATT&CK IDs (T1566, TA0001, "
                        "G0016, S0154), and the English names of techniques/tactics/tools/groups/CVEs. "
                        "Never substitute a Thai word with a foreign-language equivalent. "
                        "Do not present the output as a final legal case file, prosecution decision, "
                        "charge/no-charge decision, or replacement for expert/legal review."
                    ),
                ),
                (
                    "human",
                    (
                        "Analyze the following incident and generate a complete report in Thai.\n\n"
                        "User Query/Incident Description:\n{query}\n\n"
                        "Retrieved Context (Knowledge Base):\n{context}"
                    ),
                ),
            ]
        )

    def generate(self, query: str, context: str) -> CyberCaseReport:
        """Invokes the LLM to generate a structured report."""
        if not self.llm:
            raise ValueError("LLM not initialized. Check ANTHROPIC_API_KEY.")

        chain = self.prompt | self.structured_llm
        report = chain.invoke({"query": query, "context": context})
        return self._sanitize_thai(report)

    # ------------------------------------------------------------------
    # Thai-only guard
    # ------------------------------------------------------------------
    def _rewrite_to_thai(self, text: str) -> str:
        """Re-translate a single field that leaked non-Thai (CJK) into pure Thai.

        Falls back to stripping the offending characters if the repair call fails,
        so the report always ships without foreign-language tokens.
        """
        try:
            resp = self.llm.invoke(
                "เขียนข้อความต่อไปนี้ใหม่เป็นภาษาไทยทั้งหมด ห้ามมีอักษรจีน/ญี่ปุ่น/เกาหลี "
                "คงเฉพาะ ATT&CK ID และชื่อ technique/tool/group ที่เป็นภาษาอังกฤษไว้ "
                "ตอบกลับเฉพาะข้อความที่แก้แล้วเท่านั้น ห้ามมีคำอธิบายนำ:\n\n" + text
            )
            cleaned = (resp.content if hasattr(resp, "content") else str(resp)).strip()
            return cleaned if cleaned and not _CJK_RE.search(cleaned) else _CJK_RE.sub("", text)
        except Exception:
            return _CJK_RE.sub("", text)

    def _sanitize_thai(self, report: CyberCaseReport) -> CyberCaseReport:
        """Repair any report field that contains CJK characters (foreign-language
        leakage). Scans the free-text + list fields; leaves ATT&CK IDs untouched."""
        for field in ("case_summary", "mapping_justification", "system_limitations"):
            val = getattr(report, field, "") or ""
            if _CJK_RE.search(val):
                print(f"[REPORT] CJK leak in '{field}' — repairing to Thai")
                setattr(report, field, self._rewrite_to_thai(val))

        for field in (
            "detected_indicators",
            "evidence_to_investigate",
            "preliminary_recommendations",
        ):
            items = getattr(report, field, None) or []
            repaired = []
            for item in items:
                if isinstance(item, str) and _CJK_RE.search(item):
                    print(f"[REPORT] CJK leak in '{field}' item — repairing to Thai")
                    repaired.append(self._rewrite_to_thai(item))
                else:
                    repaired.append(item)
            setattr(report, field, repaired)

        return report


# The mapping table (part 2) is a Technique→incident map for a prosecutor, NOT a
# data dump. Only these node types belong in it. Groups/Software/Campaigns are
# attribution context (graph section), not mapping rows — and graph EXPANSION
# neighbours pull in hundreds of unrelated entities (every Group that uses
# Phishing, every mobile malware), so we deliberately skip neighbours.
_MAPPING_TABLE_TYPES = {"Technique", "Subtechnique", "Tactic"}
_MAPPING_TABLE_MAX = 25


def extract_mitre_entities(rag_result, max_rows: int = _MAPPING_TABLE_MAX) -> list[MitreEntity]:
    """Build the faithful MITRE table (part 2) from the RETRIEVED entities.

    Sourced from retrieval (never the LLM, so IDs can't be hallucinated), but kept
    FOCUSED:
      - vector hits (already reranked + capped) filtered to Technique/Subtechnique/Tactic
      - graph CENTER nodes only (the reranked seed of each subgraph) — NOT neighbours
    Groups/Software/Campaigns and graph neighbours are excluded so the table maps
    techniques to the incident instead of dumping the whole knowledge base.
    """
    seen: set[str] = set()
    rows: list[MitreEntity] = []

    def add(attack_id, name, etype):
        attack_id = (attack_id or "").strip()
        etype = (etype or "").strip()
        if not attack_id or attack_id in seen or etype not in _MAPPING_TABLE_TYPES:
            return
        seen.add(attack_id)
        rows.append(MitreEntity(id=attack_id, name=(name or "").strip(), type=etype))

    # Vector hits — metadata is a dict (shapes mirror context_builder). These are
    # already in reranked relevance order, so the table follows relevance too.
    for vr in getattr(rag_result, "vector_results", None) or []:
        if len(rows) >= max_rows:
            break
        md = getattr(vr, "metadata", None) or {}
        add(
            md.get("attack_id", ""),
            md.get("name", md.get("source_name", "")),
            md.get("node_label", md.get("edge_label", "")),
        )

    # Graph CENTER nodes only (skip neighbours — they explode the table).
    for sg in getattr(rag_result, "graph_results", None) or []:
        if len(rows) >= max_rows:
            break
        center = getattr(sg, "center_node", None)
        if center:
            add(getattr(center, "attack_id", ""), getattr(center, "name", ""), getattr(center, "label", ""))

    return rows[:max_rows]
