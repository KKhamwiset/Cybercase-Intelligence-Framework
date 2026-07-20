import asyncio

import pytest
from fastapi import HTTPException

from app.models.case import CaseRecord
from app.models.case_chat import CaseChatState, CaseChatTurn
from app.services.case_context import CaseContextService
from app.services.case_output_summary import CaseOutputSummaryService


class _Scalars:
    def __init__(self, records):
        self.records = records

    def first(self):
        return self.records[0] if self.records else None


class _Result:
    def __init__(self, records):
        self.records = records

    def scalars(self):
        return _Scalars(self.records)


class _FakeDb:
    def __init__(self, case, state=None, turns=None):
        self.case = case
        self.state = state
        self.turns = turns or []

    async def execute(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        if entity is CaseRecord:
            return _Result([self.case] if self.case else [])
        if entity is CaseChatState:
            return _Result([self.state] if self.state else [])
        if entity is CaseChatTurn:
            params = set(statement.compile().params.values())
            return _Result([turn for turn in self.turns if turn.turn_id in params])
        raise AssertionError(f"Unexpected entity: {entity}")


def _case() -> CaseRecord:
    case = CaseRecord(
        case_id="CASE-OUTPUTS",
        title="Output lifecycle",
        status="investigating",
        severity="high",
        case_version=3,
        data={
            "incident_summary": "The analyst reported a phishing message.",
            "evidence_items": [
                {
                    "evidence_id": "E-LOG",
                    "title": "Sign-in log",
                    "description": "Collected from Microsoft 365.",
                    "source_type": "log",
                }
            ],
            "attack_mappings": [
                {
                    "mapping_id": "RULE-T1566",
                    "technique_id": "T1566",
                    "technique_name": "Phishing",
                    "rationale": "Keyword rule",
                    "metadata": {
                        "source_type": "system_rule",
                        "status": "candidate",
                        "analyst_verified": False,
                        "evidence_ids": ["E-LOG"],
                    },
                }
            ],
            "gaps": ["Legacy gap without run provenance"],
            "recommendations": [
                {"action_id": "LEGACY-REC", "title": "Legacy recommendation"}
            ],
        },
    )
    case.case_snapshot_hash = CaseContextService.hash_for_case(case)
    return case


def _completed(case: CaseRecord, *, valid_outputs: bool = True):
    turn_id = "CCT-CURRENT"
    context_id = "ctx-current"
    state = CaseChatState(
        case_id=case.case_id,
        case_version=case.case_version,
        case_snapshot_hash=case.case_snapshot_hash,
        status="completed",
        requires_followup=False,
        latest_analysis_turn_id=turn_id,
        latest_retrieval_context_id=context_id,
        analysis_case_version=case.case_version,
        analysis_snapshot_hash=case.case_snapshot_hash,
    )
    item_run_id = turn_id if valid_outputs else "CCT-WRONG"
    turn = CaseChatTurn(
        turn_id=turn_id,
        case_id=case.case_id,
        role="assistant",
        content="Grounded result",
        turn_type="analysis",
        turn_status="completed",
        case_version=case.case_version,
        case_snapshot_hash=case.case_snapshot_hash,
        retrieval_context_id=context_id,
        analysis_outputs_json={
            "analysis_run_id": item_run_id,
            "case_id": case.case_id,
            "case_version": case.case_version,
            "case_snapshot_hash": case.case_snapshot_hash,
            "retrieval_context_id": context_id,
            "evidence": [],
            "gaps": [],
            "attack_mappings": [
                {
                    "item_id": "T1114",
                    "title": "Email Collection",
                    "description": "Returned by RAG",
                    "source_type": "rag",
                    "analysis_run_id": item_run_id,
                    "case_id": case.case_id,
                    "case_version": case.case_version,
                    "case_snapshot_hash": case.case_snapshot_hash,
                    "generated_at": "2026-07-10T00:00:00Z",
                    "source_references": [context_id],
                    "review_status": "unreviewed",
                    "status": "candidate",
                    "details": {"technique_id": "T1114"},
                }
            ],
            "recommendations": [],
        },
    )
    return state, turn


def test_new_case_has_only_honest_intake_and_rule_candidates_current() -> None:
    case = _case()
    result = asyncio.run(CaseOutputSummaryService(db=_FakeDb(case)).get_outputs(case.case_id))

    assert result.analysis.status == "not_started"
    assert result.analysis.analysis_run_id is None
    assert result.outputs.evidence.current_count == 2
    assert result.outputs.evidence.source_types == ["analyst_input", "log"]
    assert result.outputs.gaps.current_count == 0
    assert result.outputs.recommendations.current_count == 0
    assert result.outputs.attack_mappings.current_count == 1
    assert result.outputs.attack_mappings.items[0].source_type == "system_rule"
    assert result.outputs.attack_mappings.items[0].status == "candidate"
    assert result.historical_outputs.gaps.historical_count == 1
    assert result.historical_outputs.recommendations.historical_count == 1


def test_outputs_for_missing_case_return_404() -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(CaseOutputSummaryService(db=_FakeDb(None)).get_outputs("CASE-MISSING"))
    assert exc_info.value.status_code == 404


def test_completed_matching_analysis_exposes_structured_rag_output() -> None:
    case = _case()
    state, turn = _completed(case)
    result = asyncio.run(
        CaseOutputSummaryService(db=_FakeDb(case, state, [turn])).get_outputs(case.case_id)
    )

    assert result.analysis.status == "completed"
    assert result.analysis.analysis_run_id == turn.turn_id
    assert result.analysis.analyzed_case_version == case.case_version
    assert result.outputs.attack_mappings.current_count == 1
    rag_item = next(
        item for item in result.outputs.attack_mappings.items if item.source_type == "rag"
    )
    assert rag_item.analysis_run_id == turn.turn_id
    assert rag_item.case_version == case.case_version


@pytest.mark.parametrize("state_status", ["pending", "failed", "stale", "expired"])
def test_non_completed_lifecycle_never_exposes_analysis_outputs(state_status: str) -> None:
    case = _case()
    state, turn = _completed(case)
    state.status = state_status
    result = asyncio.run(
        CaseOutputSummaryService(db=_FakeDb(case, state, [turn])).get_outputs(case.case_id)
    )

    assert result.analysis.status == state_status
    assert result.analysis.analysis_run_id is None
    assert all(
        item.source_type != "rag" for item in result.outputs.attack_mappings.items
    )
    assert result.historical_outputs.attack_mappings.historical_count >= 1
    assert any(
        item.source_type == "rag"
        for item in result.historical_outputs.attack_mappings.items
    )


def test_mismatched_run_provenance_is_stale_and_excluded() -> None:
    case = _case()
    state, turn = _completed(case, valid_outputs=False)
    result = asyncio.run(
        CaseOutputSummaryService(db=_FakeDb(case, state, [turn])).get_outputs(case.case_id)
    )

    assert result.analysis.status == "stale"
    assert result.analysis.analysis_run_id is None
    assert all(
        item.source_type != "rag" for item in result.outputs.attack_mappings.items
    )
    malformed = next(
        item
        for item in result.historical_outputs.attack_mappings.items
        if item.item_id == "T1114"
    )
    assert malformed.source_type == "legacy_unverified"
    assert malformed.analysis_run_id is None
    assert malformed.case_version == 0


def test_model_output_without_analysis_run_is_rejected_from_current_counts() -> None:
    case = _case()
    state, turn = _completed(case)
    turn.analysis_outputs_json["analysis_run_id"] = None
    turn.analysis_outputs_json["attack_mappings"][0]["analysis_run_id"] = None
    result = asyncio.run(
        CaseOutputSummaryService(db=_FakeDb(case, state, [turn])).get_outputs(case.case_id)
    )

    assert result.analysis.status == "stale"
    assert result.analysis.analysis_run_id is None
    assert result.outputs.gaps.current_count == 0
    assert result.outputs.recommendations.current_count == 0
    assert all(
        item.source_type != "rag" for item in result.outputs.attack_mappings.items
    )
    assert any(
        item.source_type == "legacy_unverified"
        for item in result.historical_outputs.attack_mappings.items
    )


def test_trusted_input_evidence_preserves_its_origin_type() -> None:
    case = _case()
    case.data["evidence_items"] = [
        {
            "evidence_id": "E-USER",
            "title": "Analyst statement",
            "source_type": "user_input",
        },
        {
            "evidence_id": "E-DOC",
            "title": "Uploaded incident document",
            "source_type": "document",
        },
        {
            "evidence_id": "E-LOG",
            "title": "Identity log",
            "source_type": "log",
        },
    ]
    result = asyncio.run(CaseOutputSummaryService(db=_FakeDb(case)).get_outputs(case.case_id))

    by_id = {item.item_id: item for item in result.outputs.evidence.items}
    assert by_id["E-USER"].source_type == "user_input"
    assert by_id["E-DOC"].source_type == "document"
    assert by_id["E-LOG"].source_type == "log"
