from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from ..config import ANTHROPIC_API_KEY, LLM_MAX_TOKENS, LLM_MODEL, LLM_TEMPERATURE


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


class ReportGenerator:
    """Generates structured cybersecurity reports using GraphRAG context."""

    def __init__(self) -> None:
        if not ANTHROPIC_API_KEY:
            self.llm = None
            print(
                "[REPORT] Warning: ANTHROPIC_API_KEY not set. Report generation will fail."
            )
            return

        self.llm = ChatAnthropic(
            model_name=LLM_MODEL,
            api_key=ANTHROPIC_API_KEY,
            temperature=0,  # Strict reporting
            max_tokens_to_sample=LLM_MAX_TOKENS,
        )
        # Use with_structured_output for guaranteed schema adherence
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
