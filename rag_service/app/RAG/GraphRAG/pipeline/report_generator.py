from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

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
                        "You are an elite Cyber Threat Intelligence (CTI) analyst. "
                        "Your task is to analyze the provided security incident context and "
                        "generate a formal, highly accurate incident report in Thai language. "
                        "You must strictly follow the provided 7-section structure. "
                        "Base your analysis ONLY on the provided context. If information is missing, "
                        "note it in the 'System Limitations' section."
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
        return chain.invoke({"query": query, "context": context})


def extract_mitre_entities(rag_result) -> list[MitreEntity]:
    """Build the faithful MITRE table (part 2) from the RETRIEVED entities —
    vector hits (``metadata``) + graph nodes (center + neighbours) — deduped by
    ATT&CK ID. Sourced from retrieval, never the LLM, so IDs can't be hallucinated.
    """
    seen: set[str] = set()
    rows: list[MitreEntity] = []

    def add(attack_id, name, etype):
        attack_id = (attack_id or "").strip()
        if not attack_id or attack_id in seen:
            return
        seen.add(attack_id)
        rows.append(
            MitreEntity(
                id=attack_id,
                name=(name or "").strip(),
                type=(etype or "").strip(),
            )
        )

    # Vector hits — metadata is a dict (shapes mirror context_builder).
    for vr in getattr(rag_result, "vector_results", None) or []:
        md = getattr(vr, "metadata", None) or {}
        add(
            md.get("attack_id", ""),
            md.get("name", md.get("source_name", "")),
            md.get("node_label", md.get("edge_label", "")),
        )

    # Graph nodes — center + neighbours each carry attack_id/name/label.
    for sg in getattr(rag_result, "graph_results", None) or []:
        nodes = []
        center = getattr(sg, "center_node", None)
        if center:
            nodes.append(center)
        nodes.extend(getattr(sg, "neighbors", None) or [])
        for n in nodes:
            add(getattr(n, "attack_id", ""), getattr(n, "name", ""), getattr(n, "label", ""))

    return rows
