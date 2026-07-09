from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.case import CaseRecord
from app.schemas.cases import CaseCreate, CaseListItem, CaseUpdate, StructuredCase
from app.schemas.case_chat import (
    CaseChatMessageRequest,
    CaseChatMessageResponse,
    CaseChatWorkspaceView,
    CaseReportReadiness,
)
from app.schemas.report import ReportViewModel, ReportWorkflowResponse, GenerateCaseReportRequest, ReportResumeRequest
from app.services.case_outputs import apply_case_intake_outputs
from app.services.case_chat import CaseChatService
from app.services.case_context import CaseContextService
from app.services.report_generator import (
    DeterministicReportGenerator,
    structured_case_from_record_data,
)
from app.services.report_workflow import ReportWorkflowService
from app.dependencies import get_report_workflow_service

router = APIRouter(prefix="/cases", tags=["cases"])


async def _load_case_record(
    case_id: str, db: AsyncSession, *, for_update: bool = False
) -> CaseRecord:
    stmt = select(CaseRecord).where(CaseRecord.case_id == case_id)
    if for_update:
        stmt = stmt.with_for_update()
    result = await db.execute(stmt)
    case = result.scalars().first()
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


def _report_from_record(case: CaseRecord) -> ReportViewModel:
    structured_case = structured_case_from_record_data(
        case_id=case.case_id,
        title=case.title,
        status=case.status,
        severity=case.severity,
        data=case.data,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )
    return DeterministicReportGenerator().generate(structured_case)


def _structured_case_from_record(case: CaseRecord) -> StructuredCase:
    return structured_case_from_record_data(
        case_id=case.case_id,
        title=case.title,
        status=case.status,
        severity=case.severity,
        data=case.data,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


def _new_case_id() -> str:
    return f"CASE-{uuid4().hex[:12].upper()}"


def _record_payload(case_id: str, request: CaseCreate) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    payload = StructuredCase(
        case_id=case_id,
        title=request.title,
        case_type=request.case_type,
        status=request.status,
        severity=request.severity,
        incident_summary=request.incident_summary,
        created_at=now,
        updated_at=now,
    ).model_dump(mode="json")
    if request.incident_summary.strip():
        payload = apply_case_intake_outputs(payload, force=True)
    return payload


@router.post("", response_model=StructuredCase, status_code=201)
async def create_case(
    request: CaseCreate,
    db: AsyncSession = Depends(get_db),
) -> StructuredCase:
    case_id = _new_case_id()
    payload = _record_payload(case_id, request)
    case = CaseRecord(
        case_id=case_id,
        title=request.title,
        status=request.status,
        severity=request.severity,
        data=payload,
        case_version=1,
    )
    case.case_snapshot_hash = CaseContextService.hash_for_case(case)
    db.add(case)
    await db.commit()
    await db.refresh(case)
    return _structured_case_from_record(case)


@router.get("", response_model=list[CaseListItem])
async def list_cases(db: AsyncSession = Depends(get_db)) -> list[CaseListItem]:
    result = await db.execute(select(CaseRecord).order_by(CaseRecord.updated_at.desc()))
    cases = result.scalars().all()
    return [
        CaseListItem(
            case_id=case.case_id,
            title=case.title,
            status=case.status,
            severity=case.severity,
            updated_at=case.updated_at,
        )
        for case in cases
    ]


@router.get("/{case_id}", response_model=StructuredCase)
async def get_case(
    case_id: str,
    db: AsyncSession = Depends(get_db),
) -> StructuredCase:
    case = await _load_case_record(case_id, db)
    return _structured_case_from_record(case)


@router.patch("/{case_id}", response_model=StructuredCase)
async def update_case(
    case_id: str,
    request: CaseUpdate,
    db: AsyncSession = Depends(get_db),
) -> StructuredCase:
    case = await _load_case_record(case_id, db, for_update=True)
    previous_hash = case.case_snapshot_hash or ""
    updates = request.model_dump(exclude_unset=True, mode="json")
    payload = dict(case.data or {})
    payload.update(updates)
    payload["case_id"] = case.case_id
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    if "incident_summary" in updates:
        payload = apply_case_intake_outputs(payload, force=False)

    validated = StructuredCase(**payload)
    case.title = validated.title
    case.status = validated.status
    case.severity = validated.severity
    case.data = validated.model_dump(mode="json")
    changed = CaseChatService(db=db).update_case_snapshot(case, previous_hash)
    if changed:
        await CaseChatService(db=db).invalidate_for_case_update(case)
    await db.commit()
    await db.refresh(case)
    return _structured_case_from_record(case)


@router.get("/{case_id}/chat", response_model=CaseChatWorkspaceView)
async def get_case_chat(
    case_id: str,
    db: AsyncSession = Depends(get_db),
) -> CaseChatWorkspaceView:
    return await CaseChatService(db=db).get_workspace(case_id)


@router.post("/{case_id}/chat/messages", response_model=CaseChatMessageResponse)
async def post_case_chat_message(
    case_id: str,
    request: CaseChatMessageRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
) -> CaseChatMessageResponse:
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key is required")
    return await CaseChatService(db=db).send_message(
        case_id, request, idempotency_key=idempotency_key
    )


@router.get("/{case_id}/report/readiness", response_model=CaseReportReadiness)
async def get_case_report_readiness(
    case_id: str,
    db: AsyncSession = Depends(get_db),
) -> CaseReportReadiness:
    return await CaseChatService(db=db).get_report_readiness(case_id)


@router.post("/{case_id}/report", response_model=ReportWorkflowResponse)
async def generate_case_report(
    case_id: str,
    request: GenerateCaseReportRequest,
    service: ReportWorkflowService = Depends(get_report_workflow_service),
) -> ReportWorkflowResponse:
    return await service.generate_report(case_id, request)


@router.post("/{case_id}/report/resume", response_model=ReportWorkflowResponse)
async def resume_case_report(
    case_id: str,
    request: ReportResumeRequest,
    service: ReportWorkflowService = Depends(get_report_workflow_service),
) -> ReportWorkflowResponse:
    return await service.resume_report(case_id, request)


@router.get("/{case_id}/report", response_model=ReportWorkflowResponse)
async def get_case_report(
    case_id: str,
    service: ReportWorkflowService = Depends(get_report_workflow_service),
) -> ReportWorkflowResponse:
    return await service.get_latest_case_report(case_id)
