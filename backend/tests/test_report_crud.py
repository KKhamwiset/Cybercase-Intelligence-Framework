from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.models.case import CaseRecord
from app.models.case_chat import CaseChatState, CaseChatTurn
from app.models.report import ReportRecord, ReportSessionRecord
from app.schemas.report import (
    CaseFactPack,
    CaseInformationCompleteness,
    CyberCaseReport,
    GenerateCaseReportRequest,
    ReportUpdate,
    ReviewStatusUpdate,
)
from app.services.case_context import CaseContextService
from app.services.report_workflow import ReportWorkflowService


_CLAIM_RESULT = object()


class _Scalars:
    def __init__(self, first: object | None) -> None:
        self._first = first

    def first(self) -> object | None:
        return self._first


class _Result:
    def __init__(
        self,
        first: object | None = None,
        *,
        rows: list[tuple[ReportRecord, CaseRecord]] | None = None,
    ) -> None:
        self._first = first
        self._rows = rows or []

    def scalars(self) -> _Scalars:
        return _Scalars(self._first)

    def all(self) -> list[tuple[ReportRecord, CaseRecord]]:
        return self._rows


class _QueueDb:
    def __init__(self, *results: object) -> None:
        self.results = list(results)
        self.statements: list[object] = []
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.commits = 0
        self.rollbacks = 0

    async def execute(self, statement: object) -> _Result:
        self.statements.append(statement)
        if not self.results:
            return _Result()
        result = self.results.pop(0)
        if result is _CLAIM_RESULT:
            claim = next(
                (
                    record
                    for record in self.added
                    if isinstance(record, ReportSessionRecord)
                ),
                None,
            )
            return _Result(claim)
        assert isinstance(result, _Result)
        return result

    def add(self, record: object) -> None:
        self.added.append(record)

    async def delete(self, record: object) -> None:
        self.deleted.append(record)

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1

    async def flush(self) -> None:
        return None


def _fact_pack() -> CaseFactPack:
    completeness = CaseInformationCompleteness(
        percentage=100,
        status="Sufficient for preliminary report",
        missing_fields=[],
        fields=[],
    )
    return CaseFactPack(
        facts=[],
        evidence_registry=[],
        indicators=[],
        timeline=[],
        mitre_assessments=[],
        legal_assessments=[],
        missing_information=[],
        limitations=[],
        completeness_percentage=100,
        completeness=completeness,
        review_status="ai_generated",
    )


def _report(report_id: str = "REP-1") -> CyberCaseReport:
    fact_pack = _fact_pack()
    return CyberCaseReport(
        report_id=report_id,
        title="Generated report",
        report_type="overview",
        executive_case_summary="Generated summary",
        case_information_completeness=fact_pack.completeness,
        evidence_and_indicators_table=[],
        incident_timeline=[],
        mitre_attack_assessment=[],
        evidence_still_required=["Generated evidence request"],
        investigation_next_steps=["Generated next step"],
        legal_assessments=[],
        limitations_and_disclaimers=["Generated limitation"],
        review_status="ai_generated",
        case_fact_pack=fact_pack,
        created_at="2026-07-10T00:00:00Z",
    )


def _report_record(
    report_id: str = "REP-1",
    *,
    case_id: str = "CASE-1",
    workflow_status: str = "completed",
) -> ReportRecord:
    report = _report(report_id)
    payload = report.model_dump(mode="json")
    payload["metadata"] = {
        "origin": "generated",
        "edited_fields": [],
        "retrieval_context_id": "CTX-1",
        "analysis_run_id": "TURN-1",
        "analysis_case_version": 1,
        "analysis_snapshot_hash": "hash-1",
    }
    return ReportRecord(
        report_id=report_id,
        case_id=case_id,
        report_type="overview",
        workflow_status=workflow_status,
        review_status="ai_generated",
        report_payload_json=payload,
        case_fact_pack_json=report.case_fact_pack.model_dump(mode="json"),
        created_at=datetime(2026, 7, 10, tzinfo=timezone.utc),
        updated_at=datetime(2026, 7, 10, tzinfo=timezone.utc),
    )


def _mutation_db(
    record: ReportRecord,
    *,
    active_session: ReportSessionRecord | None = None,
) -> _QueueDb:
    case = CaseRecord(
        case_id=record.case_id,
        title="Mutation case",
        status="open",
        severity="high",
        data={},
    )
    results = [_Result(record), _Result(case), _Result(active_session)]
    if active_session is None:
        results.append(_Result(record))
    return _QueueDb(*results)


class _Renderer:
    def render_report_markdown(self, report: CyberCaseReport) -> str:
        return f"{report.title}|{report.executive_case_summary}"


def test_list_reports_can_filter_case_and_returns_single_report() -> None:
    case = CaseRecord(
        case_id="CASE-1",
        title="Case one",
        status="open",
        severity="high",
        data={},
    )
    first = _report_record("REP-1")
    db = _QueueDb(_Result(rows=[(first, case)]))
    service = ReportWorkflowService(report_gen=_Renderer(), db=db)

    reports = asyncio.run(service.list_reports(case_id="CASE-1"))

    assert [item.report_id for item in reports] == ["REP-1"]
    assert "CASE-1" in db.statements[0].compile().params.values()


def test_report_patch_materializes_overlay_and_preserves_generated_payload() -> None:
    record = _report_record()
    generated_payload = deepcopy(record.report_payload_json)
    generated_fact_pack = deepcopy(record.case_fact_pack_json)
    db = _mutation_db(record)
    service = ReportWorkflowService(report_gen=_Renderer(), db=db)

    response = asyncio.run(
        service.update_report(
            record.report_id,
            ReportUpdate(
                title="  Analyst title  ",
                executive_case_summary="Analyst summary",
                investigation_next_steps=["  Preserve audit logs  "],
            ),
        )
    )

    assert response.status == "completed"
    assert response.report.title == "Analyst title"
    assert response.report.executive_case_summary == "Analyst summary"
    assert response.answer == "Analyst title|Analyst summary"
    assert response.edit_metadata.origin == "manual_edit"
    assert response.edit_metadata.edited_fields == [
        "executive_case_summary",
        "investigation_next_steps",
        "title",
    ]
    assert record.report_payload_json["title"] == generated_payload["title"]
    assert (
        record.report_payload_json["executive_case_summary"]
        == generated_payload["executive_case_summary"]
    )
    assert record.case_fact_pack_json == generated_fact_pack
    metadata = record.report_payload_json["metadata"]
    assert metadata["origin"] == "manual_edit"
    assert metadata["manual_overlay"]["title"] == "Analyst title"
    assert metadata["edit_history"][-1]["edited_fields"] == [
        "executive_case_summary",
        "investigation_next_steps",
        "title",
    ]

    case = CaseRecord(
        case_id=record.case_id,
        title="Case one",
        status="open",
        severity="high",
        data={},
    )
    list_db = _QueueDb(_Result(rows=[(record, case)]))
    listed = asyncio.run(
        ReportWorkflowService(report_gen=_Renderer(), db=list_db).list_reports(
            case_id=record.case_id
        )
    )
    assert listed[0].executive_summary_preview == "Analyst summary"
    assert listed[0].edit_metadata.origin == "manual_edit"


def test_review_status_uses_registry_metadata_without_rewriting_generated_payload() -> None:
    record = _report_record()
    generated_payload = deepcopy(record.report_payload_json)
    generated_fact_pack = deepcopy(record.case_fact_pack_json)
    db = _mutation_db(record)
    service = ReportWorkflowService(report_gen=_Renderer(), db=db)

    response = asyncio.run(
        service.update_review_status(
            record.report_id,
            ReviewStatusUpdate(review_status="approved"),
        )
    )

    assert response.report.review_status == "approved"
    assert response.report.case_fact_pack.review_status == "approved"
    assert record.report_payload_json == generated_payload
    assert record.case_fact_pack_json == generated_fact_pack


@pytest.mark.parametrize("operation", ["content", "review"])
def test_report_updates_block_active_generation_session(operation: str) -> None:
    record = _report_record()
    session = ReportSessionRecord(
        session_id="SESSION-1",
        case_id=record.case_id,
        request_payload_json={},
        followup_question="Provide a timestamp",
    )
    db = _mutation_db(record, active_session=session)
    service = ReportWorkflowService(report_gen=_Renderer(), db=db)

    with pytest.raises(HTTPException) as error:
        if operation == "content":
            asyncio.run(service.update_report(record.report_id, ReportUpdate(title="Title")))
        else:
            asyncio.run(
                service.update_review_status(
                    record.report_id,
                    ReviewStatusUpdate(review_status="approved"),
                )
            )

    assert error.value.status_code == 409
    assert db.commits == 0


@pytest.mark.parametrize("operation", ["update", "delete"])
def test_missing_report_update_and_delete_return_404(operation: str) -> None:
    db = _QueueDb(_Result())
    service = ReportWorkflowService(report_gen=_Renderer(), db=db)

    with pytest.raises(HTTPException) as error:
        if operation == "update":
            asyncio.run(service.update_report("MISSING", ReportUpdate(title="Title")))
        else:
            asyncio.run(service.delete_report("MISSING"))

    assert error.value.status_code == 404


def test_delete_report_blocks_active_session_and_preserves_case() -> None:
    case = CaseRecord(
        case_id="CASE-1",
        title="Case one",
        status="open",
        severity="high",
        data={},
    )
    record = _report_record()
    session = ReportSessionRecord(
        session_id="SESSION-1",
        case_id=case.case_id,
        request_payload_json={},
        followup_question="Provide a timestamp",
    )
    blocked_db = _mutation_db(record, active_session=session)
    blocked_service = ReportWorkflowService(report_gen=_Renderer(), db=blocked_db)

    with pytest.raises(HTTPException) as error:
        asyncio.run(blocked_service.delete_report(record.report_id))

    assert error.value.status_code == 409
    assert blocked_db.deleted == []
    assert case.case_id == "CASE-1"

    deleted_db = _mutation_db(record)
    deleted_service = ReportWorkflowService(report_gen=_Renderer(), db=deleted_db)
    asyncio.run(deleted_service.delete_report(record.report_id))

    assert deleted_db.deleted == [record]
    assert deleted_db.commits == 1
    assert case.case_id == "CASE-1"


def test_expired_generation_claim_is_recovered_but_followup_claim_is_retained() -> None:
    stale = ReportSessionRecord(
        session_id="STALE-1",
        case_id="CASE-1",
        request_payload_json={"_report_claim_state": "generating"},
        followup_question="",
        created_at=datetime(2026, 7, 10, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 7, 10, 0, 0, tzinfo=timezone.utc),
    )
    db = _QueueDb(_Result(stale))
    service = ReportWorkflowService(report_gen=_Renderer(), db=db)

    asyncio.run(service._reject_active_report_session("CASE-1", for_update=True))

    assert db.deleted == [stale]

    followup = ReportSessionRecord(
        session_id="FOLLOWUP-1",
        case_id="CASE-1",
        request_payload_json={"_report_claim_state": "followup"},
        followup_question="Provide a timestamp",
        created_at=datetime(2026, 7, 10, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 7, 10, 0, 0, tzinfo=timezone.utc),
    )
    db = _QueueDb(_Result(followup))
    service = ReportWorkflowService(report_gen=_Renderer(), db=db)
    with pytest.raises(HTTPException) as error:
        asyncio.run(service._reject_active_report_session("CASE-1", for_update=True))
    assert error.value.status_code == 409

def test_pending_report_cannot_be_edited_or_deleted() -> None:
    pending = _report_record(workflow_status="pending")
    edit_service = ReportWorkflowService(
        report_gen=_Renderer(),
        db=_mutation_db(pending),
    )
    delete_service = ReportWorkflowService(
        report_gen=_Renderer(),
        db=_mutation_db(pending),
    )

    with pytest.raises(HTTPException) as edit_error:
        asyncio.run(edit_service.update_report(pending.report_id, ReportUpdate(title="Title")))
    with pytest.raises(HTTPException) as delete_error:
        asyncio.run(delete_service.delete_report(pending.report_id))

    assert edit_error.value.status_code == 409
    assert delete_error.value.status_code == 409


class _RaceClient:
    def __init__(self, case: CaseRecord) -> None:
        self.case = case

    async def get_json(self, path: str) -> dict:
        assert path == "/retrieval-contexts/CTX-1"
        self.case.data = {"incident_summary": "Edited while report generation ran"}
        self.case.case_version = 2
        self.case.case_snapshot_hash = CaseContextService.hash_for_case(self.case)
        return {
            "retrieval_context_id": "CTX-1",
            "query": "Original incident",
            "context": "retrieved context",
            "rag_result": {},
            "answer": "retrieved answer",
            "mitre_table": [],
        }


class _Generator(_Renderer):
    def preview_case_fact_pack(self, *args: object, **kwargs: object) -> CaseFactPack:
        return _fact_pack()

    def generate(self, *args: object, **kwargs: object) -> CyberCaseReport:
        return _report()


def test_case_version_race_returns_stale_and_never_persists_report() -> None:
    case = CaseRecord(
        case_id="CASE-1",
        title="Case one",
        status="open",
        severity="high",
        data={"incident_summary": "Original incident"},
        case_version=1,
    )
    original_hash = CaseContextService.hash_for_case(case)
    case.case_snapshot_hash = original_hash
    state = CaseChatState(
        case_id=case.case_id,
        case_version=1,
        case_snapshot_hash=original_hash,
        status="completed",
        requires_followup=False,
        latest_analysis_turn_id="TURN-1",
        latest_retrieval_context_id="CTX-1",
        analysis_case_version=1,
        analysis_snapshot_hash=original_hash,
    )
    turn = CaseChatTurn(
        turn_id="TURN-1",
        case_id=case.case_id,
        role="assistant",
        content="Completed analysis",
        turn_type="analysis",
        turn_status="completed",
        case_version=1,
        case_snapshot_hash=original_hash,
        retrieval_context_id="CTX-1",
    )
    db = _QueueDb(
        _Result(case),
        _Result(),
        _Result(state),
        _Result(turn),
        _Result(case),
        _CLAIM_RESULT,
        _Result(state),
        _Result(turn),
        _Result(),
    )
    service = ReportWorkflowService(
        report_gen=_Generator(),
        client=_RaceClient(case),
        db=db,
    )

    response = asyncio.run(
        service.generate_report(case.case_id, GenerateCaseReportRequest(force_generate=True))
    )

    assert response.status == "analysis_stale"
    assert response.error_code == "analysis_changed_during_report_generation"
    assert not any(isinstance(record, ReportRecord) for record in db.added)
    assert db.rollbacks == 0
    assert db.commits == 2


def test_completed_question_turn_cannot_masquerade_as_analysis_run() -> None:
    case = CaseRecord(
        case_id="CASE-1",
        title="Case one",
        status="open",
        severity="high",
        data={"incident_summary": "Original incident"},
        case_version=1,
    )
    snapshot_hash = CaseContextService.hash_for_case(case)
    case.case_snapshot_hash = snapshot_hash
    state = CaseChatState(
        case_id=case.case_id,
        case_version=1,
        case_snapshot_hash=snapshot_hash,
        status="completed",
        requires_followup=False,
        latest_analysis_turn_id="TURN-QUESTION",
        latest_retrieval_context_id="CTX-1",
        analysis_case_version=1,
        analysis_snapshot_hash=snapshot_hash,
    )
    question_turn = CaseChatTurn(
        turn_id="TURN-QUESTION",
        case_id=case.case_id,
        role="assistant",
        content="Ordinary question response",
        turn_type="question",
        turn_status="completed",
        case_version=1,
        case_snapshot_hash=snapshot_hash,
        retrieval_context_id="CTX-1",
    )
    service = ReportWorkflowService(
        report_gen=_Generator(),
        db=_QueueDb(_Result(state), _Result(question_turn)),
    )

    result = asyncio.run(
        service._validated_case_chat_context(case, GenerateCaseReportRequest())
    )

    assert result.status == "analysis_required"
    assert result.error_code == "analysis_run_invalid"
