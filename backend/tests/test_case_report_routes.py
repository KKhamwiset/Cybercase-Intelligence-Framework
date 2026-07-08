import asyncio
import pytest
from fastapi import HTTPException
from app.routers.cases import generate_case_report, resume_case_report, get_case_report
from app.routers.reports import list_reports
from app.schemas.report import (
    GenerateCaseReportRequest,
    ReportResumeRequest,
    CyberCaseReport,
    CaseFactPack,
    CaseInformationCompleteness,
)
from app.services.report_workflow import ReportWorkflowService


class _MockRagClient:
    async def post_json(self, path, payload):
        if path == "/query":
            return {"retrieval_context_id": "ctx-123"}
        return {}

    async def get_json(self, path):
        if path == "/retrieval-contexts/ctx-123":
            return {
                "retrieval_context_id": "ctx-123",
                "query": "Suspicious logins from foreign IP.",
                "rag_result": {},
                "context": "Sample threat context data",
                "answer": "Sample RAG answer",
                "mitre_table": [],
            }
        return {}


class _MockReportGenerator:
    def preview_case_fact_pack(self, query, legal=False, evidence_registry=None):
        return CaseFactPack(
            facts=[],
            evidence_registry=evidence_registry or [],
            indicators=[],
            timeline=[],
            mitre_assessments=[],
            legal_assessments=[],
            missing_information=[],
            limitations=[],
            completeness_percentage=100,
            completeness=CaseInformationCompleteness(
                percentage=100,
                status="Sufficient for preliminary report",
                missing_fields=[],
                fields=[],
            ),
            review_status="draft",
        )

    def generate(
        self,
        query,
        context,
        rag_result=None,
        mitre_table=None,
        rag_answer="",
        report_type="overview",
        legal=False,
        evidence_registry=None,
        force_generate=False,
    ):
        return CyberCaseReport(
            report_id="rep-123",
            title="Incident Report",
            report_type=report_type,
            executive_case_summary="Synthesized incident report",
            case_information_completeness=CaseInformationCompleteness(
                percentage=100,
                status="Sufficient for preliminary report",
                missing_fields=[],
                fields=[],
            ),
            evidence_and_indicators_table=[],
            incident_timeline=[],
            mitre_attack_assessment=[],
            evidence_still_required=[],
            investigation_next_steps=[],
            legal_assessments=[],
            limitations_and_disclaimers=[],
            review_status="draft",
            case_fact_pack=CaseFactPack(
                facts=[],
                evidence_registry=evidence_registry or [],
                indicators=[],
                timeline=[],
                mitre_assessments=[],
                legal_assessments=[],
                missing_information=[],
                limitations=[],
                completeness_percentage=100,
                completeness=CaseInformationCompleteness(
                    percentage=100,
                    status="Sufficient for preliminary report",
                    missing_fields=[],
                    fields=[],
                ),
                review_status="draft",
            ),
            created_at="2026-07-08T00:00:00Z",
        )

    def render_report_markdown(self, report):
        return "# Incident Report\nRendered markdown preview."


class _FakeDb:
    def __init__(self, records=None) -> None:
        self.records = records or {}
        self.added = []
        self.deleted = []
        self.commits = 0

    def add(self, record) -> None:
        self.added.append(record)
        key = (
            getattr(record, "case_id", None)
            or getattr(record, "report_id", None)
            or getattr(record, "session_id", None)
        )
        if key:
            self.records[key] = record

    async def commit(self) -> None:
        self.commits += 1

    async def execute(self, statement):
        from sqlalchemy.sql.dml import Delete

        if isinstance(statement, Delete):
            self.deleted.append(statement)
            return _Result(None)

        stmt_str = str(statement)
        matched_record = None
        for key, rec in self.records.items():
            if key in stmt_str:
                matched_record = rec
                break
        if not matched_record and self.records:
            matched_record = list(self.records.values())[0]

        return _Result(matched_record)


class _Result:
    def __init__(self, record) -> None:
        self.record = record

    def scalars(self):
        return _Scalars(self.record)

    def all(self):
        if not self.record:
            return []
        from app.models.case import CaseRecord
        case_rec = CaseRecord(
            case_id=self.record.case_id,
            title="Test Case",
            status="open",
            severity="high",
            data={},
        )
        return [(self.record, case_rec)]


class _Scalars:
    def __init__(self, record) -> None:
        self.record = record

    def first(self):
        return self.record


def test_generate_case_report() -> None:
    from app.models.case import CaseRecord

    case_rec = CaseRecord(
        case_id="CASE-123",
        title="Phishing breach",
        status="open",
        severity="high",
        data={"incident_summary": "Suspicious logins from foreign IP."},
    )
    db = _FakeDb(records={"CASE-123": case_rec})
    service = ReportWorkflowService(
        report_gen=_MockReportGenerator(),
        client=_MockRagClient(),
        db=db,
    )

    req = GenerateCaseReportRequest(report_type="overview")
    response = asyncio.run(generate_case_report("CASE-123", req, service=service))

    assert response.status == "completed"
    assert response.report_id == "rep-123"
    assert len(db.added) == 1
    assert db.commits == 1


def test_get_case_report_not_found() -> None:
    db = _FakeDb()
    service = ReportWorkflowService(
        report_gen=_MockReportGenerator(),
        client=_MockRagClient(),
        db=db,
    )
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_case_report("CASE-999", service=service))
    assert exc_info.value.status_code == 404


def test_list_reports() -> None:
    from app.models.report import ReportRecord

    report_rec = ReportRecord(
        report_id="rep-123",
        case_id="CASE-123",
        report_type="overview",
        workflow_status="completed",
        review_status="draft",
        report_payload_json={
            "report_id": "rep-123",
            "title": "Incident Report",
            "report_type": "overview",
            "executive_case_summary": "Summary",
            "case_information_completeness": {
                "percentage": 100,
                "status": "Sufficient for preliminary report",
                "missing_fields": [],
                "fields": [],
            },
            "evidence_and_indicators_table": [],
            "incident_timeline": [],
            "mitre_attack_assessment": [],
            "evidence_still_required": [],
            "investigation_next_steps": [],
            "legal_assessments": [],
            "limitations_and_disclaimers": [],
            "review_status": "draft",
            "case_fact_pack": {
                "facts": [],
                "evidence_registry": [],
                "indicators": [],
                "timeline": [],
                "mitre_assessments": [],
                "legal_assessments": [],
                "missing_information": [],
                "limitations": [],
                "completeness_percentage": 100,
                "completeness": {
                    "percentage": 100,
                    "status": "Sufficient for preliminary report",
                    "missing_fields": [],
                    "fields": [],
                },
                "review_status": "draft",
            },
            "created_at": "2026-07-08T00:00:00Z",
        },
        case_fact_pack_json={},
    )
    db = _FakeDb(records={"rep-123": report_rec})
    service = ReportWorkflowService(
        report_gen=_MockReportGenerator(),
        client=_MockRagClient(),
        db=db,
    )

    reports = asyncio.run(list_reports(service=service))
    assert len(reports) == 1
    assert reports[0].report_id == "rep-123"
