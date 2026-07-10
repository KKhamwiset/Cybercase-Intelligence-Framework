import asyncio
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.models.case import CaseRecord
from app.models.case_chat import CaseChatState, CaseChatTurn
from app.schemas.case_chat import CaseChatMessageRequest
from app.services.case_chat import CaseChatService
from app.services.case_context import CaseContextService


class _Scalars:
    def __init__(self, records):
        self.records = records

    def first(self):
        return self.records[0] if self.records else None

    def all(self):
        return list(self.records)


class _Result:
    def __init__(self, records):
        self.records = records

    def scalars(self):
        return _Scalars(self.records)


class _FakeDb:
    """Small select-aware persistence fake for service orchestration tests."""

    def __init__(self, case: CaseRecord, state: CaseChatState) -> None:
        self.case = case
        self.state = state
        self.turns: list[CaseChatTurn] = []
        self.commits = 0

    def add(self, record) -> None:
        if isinstance(record, CaseChatTurn):
            self.turns.append(record)

    async def commit(self) -> None:
        self.commits += 1

    async def execute(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        if entity is CaseRecord:
            return _Result([self.case])
        if entity is CaseChatState:
            return _Result([self.state])
        if entity is CaseChatTurn:
            params = statement.compile().params
            values = set(params.values())
            matched = list(self.turns)
            turn_ids = [value for value in values if isinstance(value, str) and value.startswith("CCT-")]
            if turn_ids:
                matched = [turn for turn in matched if turn.turn_id in turn_ids]
            keys = [
                value for value in values
                if isinstance(value, str) and any(turn.idempotency_key == value for turn in self.turns)
            ]
            if "idempotency_key" in str(statement.whereclause):
                matched = [turn for turn in matched if turn.idempotency_key in keys]
            if "assistant" in values:
                matched = [turn for turn in matched if turn.role == "assistant"]
            return _Result(matched)
        raise AssertionError(f"Unexpected statement entity: {entity!r}")


class _RagClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.contexts_fetched: list[str] = []

    async def post_json(self, path: str, payload: dict):
        self.calls.append((path, payload))
        return {
            "status": "completed",
            "answer": "Grounded investigation response",
            "retrieval_context_id": "ctx-current",
        }

    async def get_json(self, path: str):
        self.contexts_fetched.append(path)
        return {"retrieval_context_id": "ctx-current", "context": "Current context"}


class _ExpiredContextRagClient(_RagClient):
    async def get_json(self, path: str):
        self.contexts_fetched.append(path)
        raise HTTPException(status_code=404, detail="Retrieval context not found")


class _ExpiredFollowupRagClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def post_json(self, path: str, payload: dict):
        self.calls.append((path, payload))
        raise HTTPException(status_code=404, detail="RAG session not found")


def _case_and_state() -> tuple[CaseRecord, CaseChatState]:
    case = CaseRecord(
        case_id="CASE-CHAT",
        title="Chat case",
        status="investigating",
        severity="high",
        data={
            "incident_summary": "Finance received a phishing message.",
            "evidence_items": [{"evidence_id": "E-001", "title": "Original email"}],
            "gaps": ["Confirm sender infrastructure"],
            "attack_mappings": [
                {"mapping_id": "MAP-1", "technique_id": "T1566", "technique_name": "Phishing"}
            ],
        },
        case_version=1,
    )
    case.case_snapshot_hash = CaseContextService.hash_for_case(case)
    state = CaseChatState(
        case_id=case.case_id,
        case_version=case.case_version,
        case_snapshot_hash=case.case_snapshot_hash,
        status="idle",
        requires_followup=False,
    )
    return case, state


def test_get_workspace_never_calls_rag_and_exposes_pinned_context() -> None:
    case, state = _case_and_state()
    db = _FakeDb(case, state)
    rag = _RagClient()

    workspace = asyncio.run(CaseChatService(db=db, client=rag).get_workspace(case.case_id))

    assert rag.calls == []
    assert workspace.context.gaps == ["Confirm sender infrastructure"]
    assert workspace.context.attack_candidates[0].technique_id == "T1566"
    assert db.commits == 1


def test_get_workspace_backfills_legacy_snapshot_idempotently_without_rag() -> None:
    case, state = _case_and_state()
    case.case_version = 0
    case.case_snapshot_hash = ""
    state.case_version = 0
    state.case_snapshot_hash = ""
    db = _FakeDb(case, state)
    rag = _RagClient()
    service = CaseChatService(db=db, client=rag)

    first = asyncio.run(service.get_workspace(case.case_id))
    backfilled_hash = case.case_snapshot_hash
    second = asyncio.run(service.get_workspace(case.case_id))

    assert rag.calls == []
    assert case.case_version == 1
    assert state.case_version == 1
    assert backfilled_hash and len(backfilled_hash) == 64
    assert case.case_snapshot_hash == backfilled_hash
    assert first.context.case_snapshot_hash == second.context.case_snapshot_hash


def test_followup_rag_404_marks_workspace_expired_without_new_query() -> None:
    case, state = _case_and_state()
    state.status = "completed"
    state.requires_followup = True
    state.active_session_id = "session-active"
    state.latest_retrieval_context_id = "ctx-before"
    state.analysis_case_version = case.case_version
    state.analysis_snapshot_hash = case.case_snapshot_hash
    db = _FakeDb(case, state)
    rag = _ExpiredFollowupRagClient()

    response = asyncio.run(
        CaseChatService(db=db, client=rag).send_message(
            case.case_id,
            CaseChatMessageRequest(action="followup", message="The event occurred at 10:00 UTC."),
            idempotency_key="followup-404",
        )
    )

    assert rag.calls == [
        ("/resume", {"session_id": "session-active", "answer": "The event occurred at 10:00 UTC."})
    ]
    assert response.status == "expired"
    assert response.turn_status == "expired"
    assert db.turns[0].turn_status == "expired"
    assert state.active_session_id is None
    assert state.latest_retrieval_context_id is None
    assert state.requires_followup is False


def test_explicit_analyze_builds_backend_prompt_and_persists_turns() -> None:
    case, state = _case_and_state()
    db = _FakeDb(case, state)
    rag = _RagClient()
    service = CaseChatService(db=db, client=rag)

    response = asyncio.run(
        service.send_message(
            case.case_id,
            CaseChatMessageRequest(action="analyze"),
            idempotency_key="analyze-1",
        )
    )

    assert response.status == "completed"
    assert [turn.role for turn in db.turns] == ["user", "assistant"]
    assert db.turns[0].content == "Analyze saved case"
    assert rag.calls[0][0] == "/query"
    assert "Finance received a phishing message." in rag.calls[0][1]["query"]
    assert rag.calls[0][1]["use_agent"] is True
    assert state.latest_retrieval_context_id == "ctx-current"


def test_readiness_exposes_current_analysis_and_validates_context_without_query() -> None:
    case, state = _case_and_state()
    state.status = "completed"
    state.latest_analysis_turn_id = "CCT-analysis"
    state.latest_retrieval_context_id = "ctx-current"
    state.analysis_case_version = case.case_version
    state.analysis_snapshot_hash = case.case_snapshot_hash
    db = _FakeDb(case, state)
    rag = _RagClient()

    readiness = asyncio.run(
        CaseChatService(db=db, client=rag).get_report_readiness(case.case_id)
    )

    assert readiness.analysis_status == "completed"
    assert readiness.reason == "ready"
    assert readiness.report_eligible is True
    assert readiness.latest_analysis_turn_id == "CCT-analysis"
    assert readiness.latest_retrieval_context_id == "ctx-current"
    assert rag.contexts_fetched == ["/retrieval-contexts/ctx-current"]
    assert rag.calls == []


@pytest.mark.parametrize(
    ("state_status", "requires_followup", "analysis_status", "reason"),
    [
        ("idle", False, "missing", "analysis_required"),
        ("pending", False, "pending", "analysis_pending"),
        ("completed", True, "pending", "analysis_pending"),
        ("failed", False, "failed", "analysis_failed"),
        ("stale", False, "stale", "analysis_stale"),
        ("expired", False, "expired", "context_expired"),
    ],
)
def test_readiness_maps_non_ready_states(
    state_status: str,
    requires_followup: bool,
    analysis_status: str,
    reason: str,
) -> None:
    case, state = _case_and_state()
    state.status = state_status
    state.requires_followup = requires_followup
    if state_status != "idle":
        state.analysis_case_version = case.case_version
        state.analysis_snapshot_hash = case.case_snapshot_hash
    db = _FakeDb(case, state)
    rag = _RagClient()

    readiness = asyncio.run(
        CaseChatService(db=db, client=rag).get_report_readiness(case.case_id)
    )

    assert readiness.analysis_status == analysis_status
    assert readiness.reason == reason
    assert readiness.report_eligible is False
    assert readiness.latest_retrieval_context_id is None
    assert rag.calls == []
    assert rag.contexts_fetched == []


def test_readiness_marks_missing_retrieval_context_expired_without_query() -> None:
    case, state = _case_and_state()
    state.status = "completed"
    state.latest_retrieval_context_id = "ctx-current"
    state.analysis_case_version = case.case_version
    state.analysis_snapshot_hash = case.case_snapshot_hash
    db = _FakeDb(case, state)
    rag = _ExpiredContextRagClient()

    readiness = asyncio.run(
        CaseChatService(db=db, client=rag).get_report_readiness(case.case_id)
    )

    assert readiness.analysis_status == "expired"
    assert readiness.reason == "context_expired"
    assert readiness.report_eligible is False
    assert state.status == "expired"
    assert state.latest_retrieval_context_id is None
    assert rag.calls == []


def test_current_analyze_is_rejected_but_explicit_refresh_replaces_analysis() -> None:
    case, state = _case_and_state()
    state.status = "completed"
    state.latest_retrieval_context_id = "ctx-current"
    state.analysis_case_version = case.case_version
    state.analysis_snapshot_hash = case.case_snapshot_hash
    db = _FakeDb(case, state)
    rag = _RagClient()
    service = CaseChatService(db=db, client=rag)

    with pytest.raises(HTTPException) as duplicate:
        asyncio.run(
            service.send_message(
                case.case_id,
                CaseChatMessageRequest(action="analyze"),
                idempotency_key="duplicate-analyze",
            )
        )
    assert duplicate.value.status_code == 409
    assert rag.calls == []

    response = asyncio.run(
        service.send_message(
            case.case_id,
            CaseChatMessageRequest(action="refresh_analysis"),
            idempotency_key="explicit-refresh",
        )
    )

    assert response.status == "completed"
    assert db.turns[-2].content == "Refresh analysis"
    assert rag.calls[0][0] == "/query"


def test_active_followup_blocks_new_analysis_actions_without_rag() -> None:
    case, state = _case_and_state()
    state.status = "completed"
    state.requires_followup = True
    state.active_session_id = "session-active"
    state.analysis_case_version = case.case_version
    state.analysis_snapshot_hash = case.case_snapshot_hash
    db = _FakeDb(case, state)
    rag = _RagClient()

    with pytest.raises(HTTPException) as blocked:
        asyncio.run(
            CaseChatService(db=db, client=rag).send_message(
                case.case_id,
                CaseChatMessageRequest(action="refresh_analysis"),
                idempotency_key="blocked-refresh",
            )
        )

    assert blocked.value.status_code == 409
    assert rag.calls == []


def test_case_edit_marks_current_analysis_stale_and_clears_report_eligibility() -> None:
    case, state = _case_and_state()
    state.status = "completed"
    state.latest_retrieval_context_id = "ctx-current"
    state.analysis_case_version = case.case_version
    state.analysis_snapshot_hash = case.case_snapshot_hash
    db = _FakeDb(case, state)
    service = CaseChatService(db=db, client=_RagClient())

    case.case_version = 2
    case.case_snapshot_hash = "b" * 64
    asyncio.run(service.invalidate_for_case_update(case))

    readiness = service._report_readiness(case, state)
    assert state.status == "stale"
    assert state.latest_retrieval_context_id is None
    assert readiness.analysis_status == "stale"
    assert readiness.report_eligible is False
    assert readiness.reason == "analysis_stale"


def test_idempotency_conflict_and_busy_action_do_not_duplicate_rag_calls() -> None:
    case, state = _case_and_state()
    db = _FakeDb(case, state)
    rag = _RagClient()
    service = CaseChatService(db=db, client=rag)
    request = CaseChatMessageRequest(action="question", message="What evidence is missing?")

    asyncio.run(service.send_message(case.case_id, request, idempotency_key="question-1"))
    replay = asyncio.run(service.send_message(case.case_id, request, idempotency_key="question-1"))
    assert replay.idempotent is True
    assert len(rag.calls) == 1

    with pytest.raises(HTTPException) as conflict:
        asyncio.run(
            service.send_message(
                case.case_id,
                CaseChatMessageRequest(action="question", message="Different payload"),
                idempotency_key="question-1",
            )
        )
    assert conflict.value.status_code == 409

    state.status = "pending"
    state.pending_idempotency_key = "another-action"
    state.pending_started_at = datetime.now(timezone.utc)
    busy = asyncio.run(
        service.send_message(
            case.case_id,
            CaseChatMessageRequest(action="analyze"),
            idempotency_key="new-action",
        )
    )
    assert busy.status == "pending"
    assert len(rag.calls) == 1


def test_case_change_and_late_action_leave_analysis_stale_without_overwriting_new_lock() -> None:
    case, state = _case_and_state()
    db = _FakeDb(case, state)
    service = CaseChatService(db=db, client=_RagClient())
    old_turn = CaseChatTurn(
        turn_id="CCT-old",
        case_id=case.case_id,
        role="user",
        content="Analyze saved case",
        turn_type="analysis",
        turn_status="pending",
        case_version=1,
        case_snapshot_hash=case.case_snapshot_hash,
        idempotency_key="old-key",
        payload_fingerprint="fingerprint",
    )
    db.turns.append(old_turn)
    state.status = "pending"
    state.pending_idempotency_key = "new-key"
    state.pending_started_at = datetime.now(timezone.utc)
    case.case_version = 2
    case.case_snapshot_hash = "b" * 64

    response = asyncio.run(
        service._finalize_success(
            case.case_id,
            old_turn.turn_id,
            "old-key",
            "analysis",
            1,
            old_turn.case_snapshot_hash,
            {"status": "completed", "answer": "Old response", "retrieval_context_id": "ctx-old"},
        )
    )

    assert response.turn_status == "stale"
    assert old_turn.turn_status == "stale"
    assert state.status == "pending"
    assert state.pending_idempotency_key == "new-key"
    assert state.latest_retrieval_context_id is None
