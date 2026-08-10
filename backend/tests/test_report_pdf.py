from datetime import datetime, timezone
from io import BytesIO
from uuid import uuid4

from pypdf import PdfReader

from app.schemas.chat.reports import (
    ChatReportRead,
    ReportClaim,
    ReportSection,
    StructuredReport,
)
from app.services.reports.report_pdf import render_chat_report_pdf


def test_render_chat_report_pdf_contains_formal_metadata_and_sections() -> None:
    report = _report_read()

    content = render_chat_report_pdf(
        report,
        thread_title="Suspicious PowerShell activity - เหตุการณ์น่าสงสัย",
    )

    assert content.startswith(b"%PDF-")
    reader = PdfReader(BytesIO(content))
    assert len(reader.pages) >= 2
    assert reader.metadata is not None
    assert reader.metadata.title == "Validated structured report"
    assert reader.metadata.author == "CyberCase Intelligence Framework"


def _report_read() -> ChatReportRead:
    report_id = uuid4()
    thread_id = uuid4()
    sections = [
        ReportSection(
            section_id=section_id,
            heading=heading,
            paragraphs=[f"Content for {heading}."],
            items=[],
        )
        for section_id, heading in (
            ("executive_summary", "Executive Summary"),
            ("case_background_scope", "Case Background and Scope"),
            ("evidence_findings", "Evidence Findings"),
            (
                "individuals_accounts_systems_roles",
                "Individuals, Accounts, Systems, and Reported Roles",
            ),
            ("chronological_timeline", "Chronological Timeline"),
            (
                "technical_analysis_mitre",
                "Technical Analysis and MITRE ATT&CK Mapping",
            ),
            (
                "conclusions_limitations_next_steps",
                "Conclusions, Limitations, and Recommended Next Investigative Steps",
            ),
        )
    ]
    structured = StructuredReport(
        report_version="baseline_report_v1",
        status="provisional_unverified",
        title="Validated structured report",
        sections=sections,
        claims=[
            ReportClaim(
                claim_id="claim-1",
                section_id="executive_summary",
                text="A user-reported event is retained as a candidate finding.",
                support_type="user_reported",
                evidence_ids=["E-1"],
            )
        ],
        limitations=["This report is not confirmed forensic evidence."],
    )
    now = datetime.now(timezone.utc)
    return ChatReportRead(
        report_id=report_id,
        thread_id=thread_id,
        version_number=4,
        idempotency_key="test-report",
        source_snapshot_hash="a" * 64,
        extraction_id=uuid4(),
        extraction_version="baseline_extraction_v1",
        prompt_version="chat_report_prompt_v1",
        provider="anthropic",
        model="claude-haiku-4-5-20251001",
        decoding_settings={"temperature": 0.0, "max_output_tokens": 8192},
        persistence_status="completed",
        validation_status="validated",
        report=structured,
        validation_errors=[],
        failure_code=None,
        failure_message=None,
        created_at=now,
        finished_at=now,
        latency_ms=100.0,
        input_tokens=100,
        output_tokens=200,
    )
