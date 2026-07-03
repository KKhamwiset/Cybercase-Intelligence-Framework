from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.case import CaseRecord
from app.schemas.report import CaseCreate, CaseListItem, CaseUpdate, ReportViewModel, StructuredCase
from app.services.case_outputs import apply_case_intake_outputs
from app.services.report_generator import (
    DeterministicReportGenerator,
    structured_case_from_record_data,
)

router = APIRouter(prefix="/cases", tags=["cases"])


async def _load_case_record(case_id: str, db: AsyncSession) -> CaseRecord:
    result = await db.execute(select(CaseRecord).where(CaseRecord.case_id == case_id))
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
    )
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
    case = await _load_case_record(case_id, db)
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
    await db.commit()
    await db.refresh(case)
    return _structured_case_from_record(case)


@router.get("/{case_id}/report", response_model=ReportViewModel)
async def get_case_report(
    case_id: str,
    db: AsyncSession = Depends(get_db),
) -> ReportViewModel:
    case = await _load_case_record(case_id, db)
    return _report_from_record(case)


@router.post("/{case_id}/report/refresh", response_model=ReportViewModel)
async def refresh_case_report(
    case_id: str,
    db: AsyncSession = Depends(get_db),
) -> ReportViewModel:
    case = await _load_case_record(case_id, db)
    return _report_from_record(case)
