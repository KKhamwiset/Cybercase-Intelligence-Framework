import asyncio
import pytest
from fastapi import HTTPException
from app.schemas.report import (
    GenerateCaseReportRequest,
    CyberCaseReport,
    CaseFactPack,
    CaseInformationCompleteness,
)
from app.services.report_workflow import ReportWorkflowService
from app.models.case import CaseRecord
from app.models.case_chat import CaseChatState, CaseChatTurn
from app.services.case_context import CaseContextService


class _MockRagClient:
    def __init__(self):
        self.queries_called = 0
        self.contexts_fetched = []

    async def post_json(self, path, payload):
        if path == "/query":
            self.queries_called += 1
            return {"retrieval_context_id": "ctx-123"}
        return {}

    async def get_json(self, path):
        self.contexts_fetched.append(path)
        if path == "/retrieval-contexts/ctx-123":
            return {
                "retrieval_context_id": "ctx-123",
                "query": "Suspicious logins from foreign IP.",
                "rag_result": {
                    "vector_results": [],
                    "graph_results": []
                },
                "context": "Sample threat context data",
                "answer": "Sample RAG answer",
                "mitre_table": [
                    {
                        "technique_id": "T1566",
                        "name": "Phishing",
                        "entity_type": "Technique",
                        "score": 0.98,
                        "source": "graph",
                        "relevance": "cited_in_answer",
                        "description": "Email phishing technique"
                    }
                ],
            }
        elif path == "/retrieval-contexts/ctx-expired":
            return {}  # empty snapshot
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
        from app.schemas.report import MitreAssessment
        
        mitre_assessments = []
        if mitre_table:
            for row in mitre_table:
                technique_id = getattr(row, "technique_id", "") if not isinstance(row, dict) else row.get("technique_id", "")
                name = getattr(row, "name", "") if not isinstance(row, dict) else row.get("name", "")
                entity_type = getattr(row, "entity_type", "Technique") if not isinstance(row, dict) else row.get("entity_type", "Technique")
                mitre_assessments.append(
                    MitreAssessment(
                        technique_id=technique_id,
                        technique_name=name,
                        mapping_status="confirmed",
                        evidence_ids=["E-001"],
                        justification="Test",
                    )
                )

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
            mitre_attack_assessment=mitre_assessments,
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
        # Must return the expected headings
        headings = [
            "# CyberCase Investigation Report",
            "## 1. Case Summary",
            "## 2. Found Indicators",
            "## 3. MITRE ATT&CK Mapping",
            "## 4. Mapping Rationale",
            "## 5. Evidence That Should Be Checked",
            "## 6. Preliminary Recommendations",
            "## 7. System Limitations"
        ]
        return "\n\n".join(headings)


class _FakeDb:
    def __init__(self, records=None, chat_state=None) -> None:
        self.records = records or {}
        self.chat_state = chat_state
        case = next(
            (record for record in self.records.values() if isinstance(record, CaseRecord)),
            None,
        )
        self.chat_turn = (
            CaseChatTurn(
                turn_id=chat_state.latest_analysis_turn_id,
                case_id=case.case_id,
                role="assistant",
                content="Completed analysis",
                turn_type="analysis",
                turn_status="completed",
                case_version=case.case_version,
                case_snapshot_hash=case.case_snapshot_hash,
                retrieval_context_id=chat_state.latest_retrieval_context_id,
            )
            if isinstance(chat_state, CaseChatState)
            and chat_state.latest_analysis_turn_id
            and isinstance(case, CaseRecord)
            else None
        )
        self.report_sessions = {}
        self.added = []
        self.commits = 0

    def add(self, record) -> None:
        self.added.append(record)
        from app.models.report import ReportRecord, ReportSessionRecord

        if isinstance(record, ReportSessionRecord):
            self.report_sessions[record.session_id] = record
        elif isinstance(record, ReportRecord):
            self.records[record.report_id] = record

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        return None

    async def execute(self, statement):
        stmt_str = str(statement)
        if "report_sessions" in stmt_str:
            return _Result(next(iter(self.report_sessions.values()), None))
        if "case_chat_states" in stmt_str:
            return _Result(self.chat_state)
        if "case_chat_turns" in stmt_str:
            return _Result(self.chat_turn)
        if "FROM cases" in stmt_str:
            return _Result(
                next(
                    (
                        record
                        for record in self.records.values()
                        if isinstance(record, CaseRecord)
                    ),
                    None,
                )
            )
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


class _Scalars:
    def __init__(self, record) -> None:
        self.record = record

    def first(self):
        return self.record


def _current_case_and_state() -> tuple[CaseRecord, CaseChatState]:
    case = CaseRecord(
        case_id="CASE-123",
        title="Phishing breach",
        status="open",
        severity="high",
        data={"incident_summary": "Suspicious logins from foreign IP."},
        case_version=1,
    )
    snapshot_hash = CaseContextService.hash_for_case(case)
    case.case_snapshot_hash = snapshot_hash
    return case, CaseChatState(
        case_id=case.case_id,
        case_version=1,
        case_snapshot_hash=snapshot_hash,
        status="completed",
        requires_followup=False,
        latest_analysis_turn_id="turn-123",
        latest_retrieval_context_id="ctx-123",
        analysis_case_version=1,
        analysis_snapshot_hash=snapshot_hash,
    )


def test_generate_report_reuses_retrieval_context() -> None:
    case_rec, chat_state = _current_case_and_state()
    db = _FakeDb(records={"CASE-123": case_rec}, chat_state=chat_state)
    client = _MockRagClient()
    service = ReportWorkflowService(
        report_gen=_MockReportGenerator(),
        client=client,
        db=db,
    )

    req = GenerateCaseReportRequest(
        report_type="overview",
        retrieval_context_id="ctx-123"
    )
    response = asyncio.run(service.generate_report("CASE-123", req))

    assert response.status == "completed"
    assert client.queries_called == 0
    assert "/retrieval-contexts/ctx-123" in client.contexts_fetched
    assert len(response.report.mitre_attack_assessment) == 1
    assert response.report.mitre_attack_assessment[0].technique_id == "T1566"
    persisted = next(
        record
        for record in db.added
        if getattr(record, "report_id", None) == response.report_id
    )
    assert persisted.report_payload_json["metadata"] == {
        "origin": "generated",
        "edited_fields": [],
        "retrieval_context_id": "ctx-123",
        "analysis_run_id": "turn-123",
        "analysis_case_version": 1,
        "analysis_snapshot_hash": case_rec.case_snapshot_hash,
    }


def test_generate_report_resolves_the_current_chat_context_when_omitted() -> None:
    case_rec, chat_state = _current_case_and_state()
    db = _FakeDb(records={"CASE-123": case_rec}, chat_state=chat_state)
    client = _MockRagClient()
    service = ReportWorkflowService(
        report_gen=_MockReportGenerator(),
        client=client,
        db=db,
    )

    req = GenerateCaseReportRequest(
        report_type="overview",
        retrieval_context_id=None
    )
    response = asyncio.run(service.generate_report("CASE-123", req))

    assert response.status == "completed"
    assert client.queries_called == 0
    assert client.contexts_fetched == ["/retrieval-contexts/ctx-123"]


def test_generate_report_rejects_a_supplied_context_mismatch() -> None:
    case_rec, chat_state = _current_case_and_state()
    db = _FakeDb(records={"CASE-123": case_rec}, chat_state=chat_state)
    client = _MockRagClient()
    service = ReportWorkflowService(
        report_gen=_MockReportGenerator(),
        client=client,
        db=db,
    )

    response = asyncio.run(
        service.generate_report(
            "CASE-123",
            GenerateCaseReportRequest(
                report_type="overview",
                retrieval_context_id="ctx-not-current",
            ),
        )
    )

    assert response.status == "analysis_stale"
    assert response.error_code == "retrieval_context_mismatch"
    assert client.queries_called == 0
    assert client.contexts_fetched == []


@pytest.mark.parametrize(
    ("state_status", "error_code"),
    [
        ("idle", "analysis_required"),
        ("pending", "analysis_pending"),
        ("failed", "analysis_failed"),
        ("stale", "analysis_stale"),
        ("expired", "context_expired"),
    ],
)
def test_generate_report_rejects_non_ready_chat_state(
    state_status: str, error_code: str
) -> None:
    case_rec, chat_state = _current_case_and_state()
    chat_state.status = state_status
    db = _FakeDb(records={"CASE-123": case_rec}, chat_state=chat_state)
    client = _MockRagClient()
    service = ReportWorkflowService(
        report_gen=_MockReportGenerator(),
        client=client,
        db=db,
    )

    response = asyncio.run(
        service.generate_report("CASE-123", GenerateCaseReportRequest())
    )

    assert response.error_code == error_code
    assert client.queries_called == 0
    assert client.contexts_fetched == []


def test_generate_report_expired_context_returns_error() -> None:
    case_rec, chat_state = _current_case_and_state()
    chat_state.latest_retrieval_context_id = "ctx-expired"
    db = _FakeDb(records={"CASE-123": case_rec}, chat_state=chat_state)
    client = _MockRagClient()
    service = ReportWorkflowService(
        report_gen=_MockReportGenerator(),
        client=client,
        db=db,
    )

    req = GenerateCaseReportRequest(
        report_type="overview",
        retrieval_context_id="ctx-expired"
    )
    response = asyncio.run(service.generate_report("CASE-123", req))

    assert response.status == "context_expired"
    assert client.queries_called == 0
