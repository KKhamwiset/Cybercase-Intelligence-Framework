from __future__ import annotations

import asyncio
import os
from typing import AsyncIterator

import pytest
from fastapi import Depends, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.pool import NullPool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.dependencies import get_report_workflow_service
from app.main import app as backend_app
from app.models.case import CaseRecord
from app.models.case_chat import CaseChatState, CaseChatTurn
from app.models.report import ReportRecord, ReportSessionRecord
from app.schemas.report import (
    CaseFactPack,
    CaseInformationCompleteness,
    CyberCaseReport,
    GenerateCaseReportRequest,
    ReportResumeRequest,
    ReportUpdate,
    ReviewStatusUpdate,
)
from app.services.report_workflow import ReportWorkflowService
from app.services.case_context import CaseContextService


TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/cybercase_framework_test",
)

if not TEST_DATABASE_URL.startswith("postgresql"):
    pytest.skip("HTTP report tests require PostgreSQL", allow_module_level=True)

engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _check_database() -> None:
    async with engine.connect():
        return None


try:
    asyncio.run(_check_database())
except Exception as exc:  # pragma: no cover - environment-specific skip
    pytest.skip(
        f"PostgreSQL test database is unavailable: {exc}",
        allow_module_level=True,
    )


def _fastapi_app():
    return getattr(backend_app, "app", backend_app)


@pytest.fixture(autouse=True)
def reset_database() -> None:
    async def _reset() -> None:
        import app.models  # noqa: F401

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_reset())


@pytest.fixture
def report_generator() -> "_MockReportGenerator":
    return _MockReportGenerator()


@pytest.fixture
def client(report_generator: "_MockReportGenerator") -> TestClient:
    app = _fastapi_app()

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with SessionLocal() as session:
            yield session

    def override_report_service(
        db: AsyncSession = Depends(get_db),
    ) -> ReportWorkflowService:
        return ReportWorkflowService(
            report_gen=report_generator,
            client=_MockRagClient(),
            db=db,
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_report_workflow_service] = override_report_service
    try:
        with TestClient(backend_app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


class _MockRagClient:
    async def post_json(self, path: str, payload: dict) -> dict:
        if path == "/query":
            return {"retrieval_context_id": "ctx-http"}
        return {}

    async def get_json(self, path: str) -> dict:
        if path == "/retrieval-contexts/ctx-http":
            return {
                "retrieval_context_id": "ctx-http",
                "query": "Suspicious logins from a foreign IP.",
                "rag_result": {},
                "context": "Sample threat context data",
                "answer": "Sample RAG answer",
                "mitre_table": [],
            }
        return {}


class _BlockingRagClient:
    def __init__(self, entered: asyncio.Event, release: asyncio.Event) -> None:
        self.entered = entered
        self.release = release

    async def get_json(self, path: str) -> dict:
        assert path == "/retrieval-contexts/ctx-http"
        self.entered.set()
        await self.release.wait()
        return {
            "retrieval_context_id": "ctx-http",
            "query": "Suspicious logins from a foreign IP.",
            "rag_result": {},
            "context": "Sample threat context data",
            "answer": "Sample RAG answer",
            "mitre_table": [],
        }

class _MockReportGenerator:
    def __init__(self) -> None:
        self.preview_queries: list[str] = []
        self.generated_reports = 0

    def preview_case_fact_pack(
        self,
        query: str,
        legal: bool = False,
        evidence_registry: list | None = None,
    ) -> CaseFactPack:
        self.preview_queries.append(query)
        has_prior_answer = "Previously provided follow-up answers" in query
        return _case_fact_pack(
            evidence_registry=evidence_registry or [],
            complete=has_prior_answer,
        )

    def generate(
        self,
        query: str,
        context: str,
        rag_result: dict | None = None,
        mitre_table: list | None = None,
        rag_answer: str = "",
        report_type: str = "overview",
        legal: bool = False,
        evidence_registry: list | None = None,
        force_generate: bool = False,
    ) -> CyberCaseReport:
        self.generated_reports += 1
        completeness = _completeness(complete=True)
        return CyberCaseReport(
            report_id=f"rep-http-{self.generated_reports}",
            title="HTTP Incident Report",
            report_type=report_type,  # type: ignore[arg-type]
            executive_case_summary="Synthesized HTTP incident report",
            case_information_completeness=completeness,
            evidence_and_indicators_table=[],
            incident_timeline=[],
            mitre_attack_assessment=[],
            evidence_still_required=[],
            investigation_next_steps=[],
            legal_assessments=[],
            limitations_and_disclaimers=[],
            review_status="draft",
            case_fact_pack=_case_fact_pack(
                evidence_registry=evidence_registry or [],
                complete=True,
            ),
            created_at="2026-07-08T00:00:00Z",
        )

    def render_report_markdown(self, report: CyberCaseReport) -> str:
        return "# HTTP Incident Report\nRendered markdown preview."


def _completeness(complete: bool) -> CaseInformationCompleteness:
    return CaseInformationCompleteness(
        percentage=100 if complete else 20,
        status=(
            "Sufficient for preliminary report"
            if complete
            else "Incomplete - follow-up required"
        ),
        missing_fields=[] if complete else ["incident date/time"],
        fields=[],
    )


def _case_fact_pack(
    *,
    evidence_registry: list,
    complete: bool,
) -> CaseFactPack:
    completeness = _completeness(complete)
    return CaseFactPack(
        facts=[],
        evidence_registry=evidence_registry,
        indicators=[],
        timeline=[],
        mitre_assessments=[],
        legal_assessments=[],
        missing_information=[] if complete else ["incident date/time"],
        limitations=[],
        completeness_percentage=completeness.percentage,
        completeness=completeness,
        review_status="draft",
    )


def _create_case(client: TestClient, title: str = "HTTP Case") -> str:
    response = client.post(
        "/api/v1/cases",
        json={
            "title": title,
            "severity": "high",
            "incident_summary": "Suspicious logins from a foreign IP.",
        },
    )
    assert response.status_code == 201
    case_id = response.json()["case_id"]

    async def _seed_current_chat_analysis() -> None:
        async with SessionLocal() as session:
            result = await session.execute(select(CaseRecord).where(CaseRecord.case_id == case_id))
            case = result.scalars().first()
            assert case is not None
            snapshot_hash = CaseContextService.hash_for_case(case)
            analysis_turn_id = f"analysis-{case_id}"
            session.add(
                CaseChatTurn(
                    turn_id=analysis_turn_id,
                    case_id=case_id,
                    role="assistant",
                    content="Completed HTTP analysis",
                    turn_type="analysis",
                    turn_status="completed",
                    case_version=case.case_version,
                    case_snapshot_hash=snapshot_hash,
                    retrieval_context_id="ctx-http",
                )
            )
            session.add(
                CaseChatState(
                    case_id=case_id,
                    case_version=case.case_version,
                    case_snapshot_hash=snapshot_hash,
                    status="completed",
                    requires_followup=False,
                    latest_analysis_turn_id=analysis_turn_id,
                    latest_retrieval_context_id="ctx-http",
                    analysis_case_version=case.case_version,
                    analysis_snapshot_hash=snapshot_hash,
                )
            )
            await session.commit()

    asyncio.run(_seed_current_chat_analysis())
    return case_id


def test_case_owned_report_accepts_body_without_query(
    client: TestClient,
    report_generator: _MockReportGenerator,
) -> None:
    case_id = _create_case(client)

    response = client.post(
        f"/api/v1/cases/{case_id}/report",
        json={"report_type": "overview", "legal": False, "force_generate": True},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert report_generator.preview_queries[0].startswith("Suspicious logins")


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/reports/generate",
        "/api/v1/reports/generate-file",
        "/api/v1/reports/resume",
        "/api/v1/rag/generate-report",
    ],
)
def test_legacy_report_endpoints_are_gone(client: TestClient, path: str) -> None:
    response = client.post(path, json={})
    assert response.status_code in {404, 405}


def test_report_registry_get_and_review_status(client: TestClient) -> None:
    case_id = _create_case(client)
    generated = client.post(
        f"/api/v1/cases/{case_id}/report",
        json={"report_type": "overview", "force_generate": True, "retrieval_context_id": "ctx-http"},
    )
    assert generated.status_code == 200
    report_id = generated.json()["report_id"]

    listing = client.get("/api/v1/reports")
    assert listing.status_code == 200
    assert listing.json()[0]["report_id"] == report_id

    detail = client.get(f"/api/v1/reports/{report_id}")
    assert detail.status_code == 200
    assert detail.json()["report"]["report_id"] == report_id

    updated = client.patch(
        f"/api/v1/reports/{report_id}/review-status",
        json={"review_status": "approved"},
    )
    assert updated.status_code == 200
    assert updated.json()["report"]["review_status"] == "approved"


def test_successful_regeneration_replaces_current_report_and_resets_manual_state(
    client: TestClient,
) -> None:
    case_id = _create_case(client)
    initial = client.post(
        f"/api/v1/cases/{case_id}/report",
        json={"report_type": "overview", "force_generate": True},
    )
    assert initial.status_code == 200
    stable_report_id = initial.json()["report_id"]

    patched = client.patch(
        f"/api/v1/reports/{stable_report_id}",
        json={"title": "Analyst override"},
    )
    approved = client.patch(
        f"/api/v1/reports/{stable_report_id}/review-status",
        json={"review_status": "approved"},
    )
    assert patched.status_code == approved.status_code == 200

    async def _created_at() -> object:
        async with SessionLocal() as session:
            record = (
                await session.execute(
                    select(ReportRecord).where(ReportRecord.case_id == case_id)
                )
            ).scalars().one()
            return record.created_at

    original_created_at = asyncio.run(_created_at())
    regenerated = client.post(
        f"/api/v1/cases/{case_id}/report",
        json={"report_type": "timeline", "force_generate": True},
    )

    assert regenerated.status_code == 200
    body = regenerated.json()
    assert body["report_id"] == stable_report_id
    assert body["report"]["report_id"] == stable_report_id
    assert body["report"]["report_type"] == "timeline"
    assert body["report"]["title"] == "HTTP Incident Report"
    assert body["report"]["review_status"] == "draft"
    assert body["edit_metadata"] == {
        "origin": "generated",
        "edited_fields": [],
        "edited_at": None,
    }

    case_report = client.get(f"/api/v1/cases/{case_id}/report")
    filtered = client.get("/api/v1/reports", params={"case_id": case_id})
    assert case_report.status_code == filtered.status_code == 200
    assert case_report.json()["report_id"] == stable_report_id
    assert [item["report_id"] for item in filtered.json()] == [stable_report_id]

    async def _assert_replaced_record() -> None:
        async with SessionLocal() as session:
            records = (
                await session.execute(
                    select(ReportRecord).where(ReportRecord.case_id == case_id)
                )
            ).scalars().all()
            assert len(records) == 1
            record = records[0]
            assert record.report_id == stable_report_id
            assert record.created_at == original_created_at
            assert record.report_type == "timeline"
            assert record.review_status == "draft"
            assert record.report_payload_json["report_id"] == stable_report_id
            assert record.case_fact_pack_json["review_status"] == "draft"
            metadata = record.report_payload_json["metadata"]
            assert metadata["origin"] == "generated"
            assert metadata["edited_fields"] == []
            assert "manual_overlay" not in metadata
            assert "edit_history" not in metadata
            assert "edited_at" not in metadata

    asyncio.run(_assert_replaced_record())


def test_failed_regeneration_preserves_current_report(
    client: TestClient,
    report_generator: _MockReportGenerator,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case_id = _create_case(client)
    initial = client.post(
        f"/api/v1/cases/{case_id}/report",
        json={"report_type": "overview", "force_generate": True},
    )
    assert initial.status_code == 200
    report_id = initial.json()["report_id"]
    assert client.patch(
        f"/api/v1/reports/{report_id}",
        json={"title": "Preserve this analyst edit"},
    ).status_code == 200
    assert client.patch(
        f"/api/v1/reports/{report_id}/review-status",
        json={"review_status": "approved"},
    ).status_code == 200

    def _fail_generation(*args: object, **kwargs: object) -> CyberCaseReport:
        raise RuntimeError("sensitive generator failure")

    monkeypatch.setattr(report_generator, "generate", _fail_generation)
    failed = client.post(
        f"/api/v1/cases/{case_id}/report",
        json={"report_type": "timeline", "force_generate": True},
    )

    assert failed.status_code == 500
    assert failed.json()["detail"] == "Report generation failed. Please retry."
    assert "sensitive" not in failed.text

    current = client.get(f"/api/v1/cases/{case_id}/report")
    assert current.status_code == 200
    assert current.json()["report_id"] == report_id
    assert current.json()["report"]["title"] == "Preserve this analyst edit"
    assert current.json()["report"]["review_status"] == "approved"
    assert current.json()["edit_metadata"]["origin"] == "manual_edit"

    async def _assert_preserved_record() -> None:
        async with SessionLocal() as session:
            records = (
                await session.execute(
                    select(ReportRecord).where(ReportRecord.case_id == case_id)
                )
            ).scalars().all()
            claims = (
                await session.execute(
                    select(ReportSessionRecord).where(
                        ReportSessionRecord.case_id == case_id
                    )
                )
            ).scalars().all()
            assert len(records) == 1
            assert records[0].report_id == report_id
            assert records[0].report_type == "overview"
            assert records[0].review_status == "approved"
            assert records[0].report_payload_json["metadata"]["manual_overlay"][
                "title"
            ] == "Preserve this analyst edit"
            assert claims == []

    asyncio.run(_assert_preserved_record())


def test_report_filter_content_patch_and_delete_preserve_case(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.case_chat.RagServiceClient", _MockRagClient)
    first_case_id = _create_case(client, "First report case")
    second_case_id = _create_case(client, "Second report case")
    first = client.post(
        f"/api/v1/cases/{first_case_id}/report",
        json={"report_type": "overview", "force_generate": True},
    )
    second = client.post(
        f"/api/v1/cases/{second_case_id}/report",
        json={"report_type": "overview", "force_generate": True},
    )
    assert first.status_code == second.status_code == 200
    first_report_id = first.json()["report_id"]

    filtered = client.get("/api/v1/reports", params={"case_id": first_case_id})
    assert filtered.status_code == 200
    assert [item["report_id"] for item in filtered.json()] == [first_report_id]

    patched = client.patch(
        f"/api/v1/reports/{first_report_id}",
        json={
            "title": "  Analyst-reviewed title  ",
            "executive_case_summary": "Analyst-reviewed summary",
        },
    )
    assert patched.status_code == 200
    assert patched.json()["report"]["title"] == "Analyst-reviewed title"
    assert patched.json()["edit_metadata"]["origin"] == "manual_edit"

    async def _load_stored_report() -> ReportRecord:
        async with SessionLocal() as session:
            result = await session.execute(
                select(ReportRecord).where(ReportRecord.report_id == first_report_id)
            )
            report = result.scalars().first()
            assert report is not None
            return report

    stored = asyncio.run(_load_stored_report())
    assert stored.report_payload_json["title"] == "HTTP Incident Report"
    assert stored.report_payload_json["metadata"]["manual_overlay"]["title"] == (
        "Analyst-reviewed title"
    )

    deleted = client.delete(f"/api/v1/reports/{first_report_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/reports/{first_report_id}").status_code == 404
    assert client.get(f"/api/v1/cases/{first_case_id}").status_code == 200
    readiness = client.get(f"/api/v1/cases/{first_case_id}/report/readiness")
    assert readiness.status_code == 200
    assert readiness.json()["report_eligible"] is True
    regenerated = client.post(
        f"/api/v1/cases/{first_case_id}/report",
        json={"report_type": "overview", "force_generate": True},
    )
    assert regenerated.status_code == 200


def test_report_delete_conflicts_with_active_followup(client: TestClient) -> None:
    case_id = _create_case(client)
    generated = client.post(
        f"/api/v1/cases/{case_id}/report",
        json={"report_type": "overview", "force_generate": True},
    )
    assert generated.status_code == 200
    followup = client.post(
        f"/api/v1/cases/{case_id}/report",
        json={"report_type": "overview"},
    )
    assert followup.status_code == 200
    assert followup.json()["status"] == "followup"
    duplicate = client.post(
        f"/api/v1/cases/{case_id}/report",
        json={"report_type": "overview"},
    )
    assert duplicate.status_code == 409

    content_update = client.patch(
        f"/api/v1/reports/{generated.json()['report_id']}",
        json={"title": "Blocked edit"},
    )
    review_update = client.patch(
        f"/api/v1/reports/{generated.json()['report_id']}/review-status",
        json={"review_status": "approved"},
    )
    assert content_update.status_code == 409
    assert review_update.status_code == 409

    deleted = client.delete(f"/api/v1/reports/{generated.json()['report_id']}")

    assert deleted.status_code == 409


def test_concurrent_report_start_has_one_durable_case_claim(
    client: TestClient,
    report_generator: _MockReportGenerator,
) -> None:
    case_id = _create_case(client)

    async def _run() -> None:
        entered = asyncio.Event()
        release = asyncio.Event()
        blocking_client = _BlockingRagClient(entered, release)
        async with SessionLocal() as first_session, SessionLocal() as second_session:
            first_service = ReportWorkflowService(
                report_gen=report_generator,
                client=blocking_client,
                db=first_session,
            )
            second_service = ReportWorkflowService(
                report_gen=report_generator,
                client=blocking_client,
                db=second_session,
            )
            first_task = asyncio.create_task(
                first_service.generate_report(
                    case_id,
                    GenerateCaseReportRequest(force_generate=True),
                )
            )
            await asyncio.wait_for(entered.wait(), timeout=2)
            try:
                with pytest.raises(HTTPException) as duplicate_error:
                    await second_service.generate_report(
                        case_id,
                        GenerateCaseReportRequest(force_generate=True),
                    )
                assert duplicate_error.value.status_code == 409
                # A real failed HTTP request closes/rolls back its dependency
                # session before the winning request resumes. Mirror that here
                # so the losing transaction releases its parent-case row lock.
                await second_session.rollback()
            finally:
                release.set()
            completed = await first_task
            assert completed.status == "completed"

        async with SessionLocal() as verification_session:
            claims = (
                await verification_session.execute(
                    select(ReportSessionRecord).where(
                        ReportSessionRecord.case_id == case_id
                    )
                )
            ).scalars().all()
            reports = (
                await verification_session.execute(
                    select(ReportRecord).where(ReportRecord.case_id == case_id)
                )
            ).scalars().all()
            assert claims == []
            assert len(reports) == 1

    asyncio.run(_run())


def test_duplicate_resume_is_rejected_while_first_resume_owns_claim(
    client: TestClient,
    report_generator: _MockReportGenerator,
) -> None:
    case_id = _create_case(client)
    followup = client.post(
        f"/api/v1/cases/{case_id}/report",
        json={"report_type": "overview"},
    )
    assert followup.status_code == 200
    session_id = followup.json()["session_id"]

    async def _run() -> None:
        entered = asyncio.Event()
        release = asyncio.Event()
        blocking_client = _BlockingRagClient(entered, release)
        request = ReportResumeRequest(session_id=session_id, answer="10:00 UTC")
        async with SessionLocal() as first_session, SessionLocal() as second_session:
            first_service = ReportWorkflowService(
                report_gen=report_generator,
                client=blocking_client,
                db=first_session,
            )
            second_service = ReportWorkflowService(
                report_gen=report_generator,
                client=blocking_client,
                db=second_session,
            )
            first_task = asyncio.create_task(first_service.resume_report(case_id, request))
            await asyncio.wait_for(entered.wait(), timeout=2)
            try:
                with pytest.raises(HTTPException) as duplicate_error:
                    await second_service.resume_report(case_id, request)
                assert duplicate_error.value.status_code == 409
                await second_session.rollback()
            finally:
                release.set()
            completed = await first_task
            assert completed.status == "completed"

        async with SessionLocal() as verification_session:
            case = (
                await verification_session.execute(
                    select(CaseRecord).where(CaseRecord.case_id == case_id)
                )
            ).scalars().first()
            assert case is not None
            assert len(case.data["report_followup_answers"]) == 1

    asyncio.run(_run())


def test_report_crud_is_blocked_by_direct_generation_claim(
    client: TestClient,
    report_generator: _MockReportGenerator,
) -> None:
    case_id = _create_case(client)
    existing = client.post(
        f"/api/v1/cases/{case_id}/report",
        json={"report_type": "overview", "force_generate": True},
    )
    assert existing.status_code == 200
    report_id = existing.json()["report_id"]

    async def _run() -> None:
        entered = asyncio.Event()
        release = asyncio.Event()
        blocking_client = _BlockingRagClient(entered, release)
        async with SessionLocal() as generation_session:
            generation_service = ReportWorkflowService(
                report_gen=report_generator,
                client=blocking_client,
                db=generation_session,
            )
            generation_task = asyncio.create_task(
                generation_service.generate_report(
                    case_id,
                    GenerateCaseReportRequest(force_generate=True),
                )
            )
            await asyncio.wait_for(entered.wait(), timeout=2)
            try:
                operations = (
                    lambda service: service.update_report(
                        report_id,
                        ReportUpdate(title="Blocked edit"),
                    ),
                    lambda service: service.update_review_status(
                        report_id,
                        ReviewStatusUpdate(review_status="approved"),
                    ),
                    lambda service: service.delete_report(report_id),
                )
                for operation in operations:
                    async with SessionLocal() as mutation_session:
                        mutation_service = ReportWorkflowService(
                            report_gen=report_generator,
                            client=_MockRagClient(),
                            db=mutation_session,
                        )
                        with pytest.raises(HTTPException) as conflict:
                            await operation(mutation_service)
                        assert conflict.value.status_code == 409
            finally:
                release.set()
            completed = await generation_task
            assert completed.status == "completed"

    asyncio.run(_run())


def test_followup_wrong_case_is_forbidden(client: TestClient) -> None:
    first_case_id = _create_case(client, "First case")
    second_case_id = _create_case(client, "Second case")

    followup = client.post(
        f"/api/v1/cases/{first_case_id}/report",
        json={"report_type": "overview", "retrieval_context_id": "ctx-http"},
    )
    assert followup.status_code == 200
    assert followup.json()["status"] == "followup"

    forbidden = client.post(
        f"/api/v1/cases/{second_case_id}/report/resume",
        json={"session_id": followup.json()["session_id"], "answer": "10:00 UTC"},
    )
    assert forbidden.status_code == 403


def test_followup_answer_persists_and_regenerate_does_not_repeat_question(
    client: TestClient,
    report_generator: _MockReportGenerator,
) -> None:
    case_id = _create_case(client)

    followup = client.post(
        f"/api/v1/cases/{case_id}/report",
        json={"report_type": "overview", "retrieval_context_id": "ctx-http"},
    )
    assert followup.status_code == 200
    assert followup.json()["status"] == "followup"
    question = followup.json()["followup_question"]

    resumed = client.post(
        f"/api/v1/cases/{case_id}/report/resume",
        json={"session_id": followup.json()["session_id"], "answer": "10:00 UTC"},
    )
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "completed"

    async def _load_case_data() -> dict:
        async with SessionLocal() as session:
            result = await session.execute(
                select(CaseRecord).where(CaseRecord.case_id == case_id)
            )
            case = result.scalars().first()
            assert case is not None
            return case.data

    case_data = asyncio.run(_load_case_data())
    answers = case_data["report_followup_answers"]
    assert answers == [
        {
            "question": question,
            "answer": "10:00 UTC",
            "answered_at": answers[0]["answered_at"],
            "source": "report_followup",
        }
    ]

    regenerated = client.post(
        f"/api/v1/cases/{case_id}/report",
        json={"report_type": "overview", "retrieval_context_id": "ctx-http"},
    )
    assert regenerated.status_code == 200
    assert regenerated.json()["status"] == "completed"
    assert "Previously provided follow-up answers" in report_generator.preview_queries[-1]
    assert "10:00 UTC" in report_generator.preview_queries[-1]


def test_export_report_endpoints(client: TestClient) -> None:
    case_id = _create_case(client)
    generated = client.post(
        f"/api/v1/cases/{case_id}/report",
        json={"report_type": "overview", "force_generate": True, "retrieval_context_id": "ctx-http"},
    )
    assert generated.status_code == 200
    report_id = generated.json()["report_id"]

    # Test markdown export
    response = client.get(f"/api/v1/reports/{report_id}/export?format=md")
    assert response.status_code == 200
    assert response.headers["Content-Disposition"] == f'attachment; filename="cybercase-report-{report_id}.md"'
    assert response.text == "# HTTP Incident Report\nRendered markdown preview."

    # Test PDF export
    response_pdf = client.get(f"/api/v1/reports/{report_id}/export?format=pdf")
    assert response_pdf.status_code == 200
    assert response_pdf.headers["Content-Disposition"] == f'attachment; filename="cybercase-report-{report_id}.pdf"'
    assert response_pdf.content.startswith(b"%PDF")

    # Test DOCX unsupported
    response_docx = client.get(f"/api/v1/reports/{report_id}/export?format=docx")
    assert response_docx.status_code == 501
    assert "DOCX export is not implemented yet" in response_docx.json()["detail"]

    # Test invalid format
    response_invalid = client.get(f"/api/v1/reports/{report_id}/export?format=invalid")
    assert response_invalid.status_code == 400

