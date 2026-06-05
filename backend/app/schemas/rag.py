from pydantic import BaseModel, Field


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
