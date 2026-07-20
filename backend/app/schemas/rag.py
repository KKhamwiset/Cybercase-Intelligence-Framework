from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.case_analysis import CaseAnalysisArtifact


class QueryRequest(BaseModel):
    """Compatibility request forwarded to the existing RAG service."""

    model_config = ConfigDict(extra="allow")

    query: str
    use_agent: bool = True


class ResumeRequest(BaseModel):
    """Compatibility request for an existing RAG follow-up session."""

    model_config = ConfigDict(extra="allow")

    session_id: str
    answer: str


class QueryResponse(BaseModel):
    """Lossless-enough response contract for the fields consumed by this backend."""

    model_config = ConfigDict(extra="allow")

    status: str
    answer: str = ""
    followup_question: str = ""
    session_id: str = ""
    retrieval_context_id: UUID | None = None
    mitre_table: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("retrieval_context_id", mode="before")
    @classmethod
    def normalize_empty_retrieval_context_id(cls, value: Any) -> Any:
        """Treat the RAG service's empty-string sentinel as no frozen context."""

        return None if value == "" else value


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


class ExperimentalAnalysisResponse(BaseModel):
    """Server-owned analysis artifact and its deterministic report decision."""

    analysis: CaseAnalysisArtifact
    report: CyberCaseReport | None = None
    reportability_reasons: list[str] = Field(default_factory=list)
