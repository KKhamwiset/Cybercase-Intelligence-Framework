from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import CaseRecord
from app.models.case_chat import CaseChatState, CaseChatTurn
from app.models.report import ReportRecord, ReportSessionRecord
from app.schemas.report import (
    CaseFactPack,
    CyberCaseReport,
    GenerateCaseReportRequest,
    GenerateReportRequest,
    ReportCompletedResponse,
    ReportErrorResponse,
    ReportFollowUpResponse,
    ReportInputSnapshot,
    ReportResumeRequest,
    ReviewStatusUpdate,
    EvidenceReference,
    REPORT_EDITABLE_FIELDS,
    ReportEditMetadata,
    ReportRegistryItem,
    ReportUpdate,
)
from app.services.rag_client import RagServiceClient
from app.services.case_context import CaseContextService
from app.services.reporting.generator import ReportGenerator
from app.services.reporting.thanoy_client import get_legal_advice

logger = logging.getLogger("app.report")

ReportWorkflowResult = ReportCompletedResponse | ReportFollowUpResponse | ReportErrorResponse

REPORT_CONTEXT_WAIT_MESSAGE = (
    "Report generation could not complete because RAG retrieval context "
    "was unavailable. Please retry from the case report page."
)
REPORT_CLAIM_STATE_KEY = "_report_claim_state"
REPORT_CLAIM_QUESTION_KEY = "_report_claim_question"
REPORT_CLAIM_LEASE = timedelta(minutes=15)


@dataclass(frozen=True)
class ValidatedAnalysisContext:
    retrieval_context_id: str
    analysis_run_id: str
    case_version: int
    case_snapshot_hash: str


def _report_source_type(source_type: str) -> str:
    if source_type in {
        "user_input",
        "uploaded_file",
        "log",
        "rag_source",
        "mitre_source",
        "legal_source",
    }:
        return source_type
    if source_type == "document":
        return "uploaded_file"
    if source_type == "rag":
        return "rag_source"
    return "user_input"


def build_evidence_registry_from_case(case: CaseRecord) -> list[EvidenceReference]:
    registry = []
    used_ids: set[str] = set()
    incident_summary = case.data.get("incident_summary", "")
    if incident_summary.strip():
        registry.append(
            EvidenceReference(
                evidence_id="E-001",
                source_type="user_input",
                source_name="Submitted case text",
                excerpt=incident_summary.strip()[:1200],
            )
        )
        used_ids.add("E-001")
    
    next_id = 2
    for item in case.data.get("evidence_items", []):
        ev_id = item.get("evidence_id")
        if not ev_id:
            ev_id = f"E-{next_id:03d}"
            next_id += 1

        while ev_id in used_ids:
            ev_id = f"E-{next_id:03d}"
            next_id += 1
        used_ids.add(ev_id)
            
        registry.append(
            EvidenceReference(
                evidence_id=ev_id,
                source_type=_report_source_type(item.get("source_type", "user_input")),
                source_name=item.get("title", "Evidence item"),
                excerpt=item.get("description", "")[:1200],
            )
        )
    return registry


class ReportWorkflowService:
    def __init__(
        self,
        report_gen: ReportGenerator | None = None,
        client: RagServiceClient | None = None,
        db: AsyncSession | None = None,
    ) -> None:
        self.report_gen = report_gen
        self.client = client or RagServiceClient()
        self.db = db

    async def generate_report(
        self, case_id: str, request: GenerateCaseReportRequest
    ) -> ReportWorkflowResult:
        if not self.report_gen:
            raise HTTPException(status_code=503, detail="Report Generator not available")

        # Claim generation while holding the parent case lock. Every report
        # mutation uses the same case -> session -> report lock order.
        stmt = (
            select(CaseRecord)
            .where(CaseRecord.case_id == case_id)
            .with_for_update()
        )
        result = await self.db.execute(stmt)
        case = result.scalars().first()
        if not isinstance(case, CaseRecord):
            raise HTTPException(status_code=404, detail="Case not found")
        await self._reject_active_report_session(case_id, for_update=True)

        # A case-originated report is allowed only from the current durable
        # case-chat analysis.  Do not trust a browser-provided context ID and
        # never fall back to automatic retrieval here.
        analysis_context_or_error = await self._validated_case_chat_context(case, request)
        if isinstance(analysis_context_or_error, ReportErrorResponse):
            await self.db.rollback()
            return analysis_context_or_error
        analysis_context = analysis_context_or_error
        retrieval_context_id = analysis_context.retrieval_context_id

        # Build canonical report input from case data before releasing the lock.
        query = case.data.get("incident_summary", "")
        if not query.strip():
            query = f"Incident investigation for case {case_id}"

        # Include prior follow-up answers so regeneration doesn't re-ask
        followup_answers = case.data.get("report_followup_answers", [])
        if followup_answers:
            followup_text = "\n\nPreviously provided follow-up answers:\n"
            for qa in followup_answers:
                followup_text += f"Q: {qa.get('question', '')}\nA: {qa.get('answer', '')}\n"
            query += followup_text

        evidence_registry = build_evidence_registry_from_case(case)
        internal_request = GenerateReportRequest(
            query=query,
            report_type=request.report_type,
            legal=request.legal,
            force_generate=request.force_generate,
            evidence_registry=evidence_registry,
            retrieval_context_id=retrieval_context_id,
        )
        claim_id = str(uuid.uuid4())
        claim_payload = internal_request.model_dump(mode="json")
        claim_payload[REPORT_CLAIM_STATE_KEY] = "generating"
        self.db.add(
            ReportSessionRecord(
                session_id=claim_id,
                case_id=case_id,
                request_payload_json=claim_payload,
                followup_question="",
            )
        )
        await self.db.commit()

        # The chat guard selected the only permitted context. A missing
        # context is an explicit expiry recovery state, never a fresh query.
        try:
            snapshot = await self.client.get_json(f"/retrieval-contexts/{retrieval_context_id}")
            if not snapshot or "context" not in snapshot:
                raise HTTPException(status_code=404, detail="Retrieval context not found")
        except HTTPException as exc:
            if exc.status_code == 404:
                await self._mark_context_expired(case.case_id)
            await self._release_report_claim(case_id, claim_id)
            return self._report_context_wait_response(internal_request)
        except Exception:
            await self._release_report_claim(case_id, claim_id)
            return self._report_context_wait_response(internal_request)

        try:
            preview_pack = self.report_gen.preview_case_fact_pack(
                internal_request.query,
                legal=internal_request.legal,
                evidence_registry=internal_request.evidence_registry,
            )
        except Exception:
            await self._release_report_claim(case_id, claim_id)
            raise
        if self._needs_report_followup(preview_pack) and not internal_request.force_generate:
            return await self._start_report_followup_db(
                case_id,
                claim_id,
                preview_pack,
            )

        return await self._complete_report_generation_db(
            case_id,
            internal_request,
            snapshot,
            analysis_context,
            claim_id,
        )

    async def _validated_case_chat_context(
        self, case: CaseRecord, request: GenerateCaseReportRequest
    ) -> ValidatedAnalysisContext | ReportErrorResponse:
        current_hash = CaseContextService.hash_for_case(case)
        # Recompute from persisted context as a defensive guard against an
        # out-of-band legacy update that failed to refresh the stored hash.
        case_hash = current_hash
        case_version = getattr(case, "case_version", None) or 1
        result = await self.db.execute(
            select(CaseChatState).where(CaseChatState.case_id == case.case_id)
        )
        state = result.scalars().first()
        if not isinstance(state, CaseChatState) or state.status == "idle":
            return ReportErrorResponse(
                status="analysis_required",
                error_code="analysis_required",
                message="Run and complete a current case chat analysis before generating a report.",
            )
        if (
            state.status == "stale"
            or (
                state.analysis_case_version is not None
                and (
                    state.analysis_case_version != case_version
                    or state.analysis_snapshot_hash != case_hash
                )
            )
        ):
            return ReportErrorResponse(
                status="analysis_stale",
                error_code="analysis_stale",
                message="The available analysis does not match the current case. Refresh analysis before reporting.",
            )
        if state.status == "pending" or state.requires_followup:
            return ReportErrorResponse(
                status="analysis_required",
                error_code="analysis_pending",
                message="Case analysis is still in progress. Wait for it to complete before reporting.",
            )
        if state.status == "failed":
            return ReportErrorResponse(
                status="analysis_required",
                error_code="analysis_failed",
                message="The latest case analysis failed. Refresh analysis before reporting.",
            )
        if state.status == "expired":
            return ReportErrorResponse(
                status="context_expired",
                error_code="context_expired",
                message="The case chat retrieval context expired. Refresh analysis before reporting.",
            )
        if state.analysis_case_version is None:
            return ReportErrorResponse(
                status="analysis_required",
                error_code="analysis_required",
                message="Run and complete a current case chat analysis before generating a report.",
            )
        context_id = state.latest_retrieval_context_id
        if not context_id:
            return ReportErrorResponse(
                status="context_expired",
                error_code="context_expired",
                message="The case chat retrieval context expired. Refresh analysis before reporting.",
            )
        if request.retrieval_context_id and request.retrieval_context_id != context_id:
            return ReportErrorResponse(
                status="analysis_stale",
                error_code="retrieval_context_mismatch",
                message="The supplied retrieval context is not the latest valid case chat analysis.",
            )
        analysis_run_id = state.latest_analysis_turn_id
        if not analysis_run_id:
            return ReportErrorResponse(
                status="analysis_required",
                error_code="analysis_run_missing",
                message="The completed analysis has no durable run provenance. Refresh analysis before reporting.",
            )
        turn_result = await self.db.execute(
            select(CaseChatTurn).where(
                CaseChatTurn.turn_id == analysis_run_id,
                CaseChatTurn.case_id == case.case_id,
                CaseChatTurn.role == "assistant",
                CaseChatTurn.turn_type.in_(("analysis", "followup")),
                CaseChatTurn.turn_status == "completed",
                CaseChatTurn.case_version == case_version,
                CaseChatTurn.case_snapshot_hash == case_hash,
                CaseChatTurn.retrieval_context_id == context_id,
            )
        )
        analysis_turn = turn_result.scalars().first()
        if not (
            isinstance(analysis_turn, CaseChatTurn)
            and analysis_turn.case_id == case.case_id
            and analysis_turn.role == "assistant"
            and analysis_turn.turn_type in {"analysis", "followup"}
            and analysis_turn.turn_status == "completed"
            and analysis_turn.case_version == case_version
            and analysis_turn.case_snapshot_hash == case_hash
            and analysis_turn.retrieval_context_id == context_id
        ):
            return ReportErrorResponse(
                status="analysis_required",
                error_code="analysis_run_invalid",
                message="The completed analysis run could not be validated. Refresh analysis before reporting.",
            )
        return ValidatedAnalysisContext(
            retrieval_context_id=context_id,
            analysis_run_id=analysis_run_id,
            case_version=case_version,
            case_snapshot_hash=case_hash,
        )

    async def _reject_active_report_session(
        self, case_id: str, *, for_update: bool = False
    ) -> None:
        stmt = (
            select(ReportSessionRecord)
            .where(ReportSessionRecord.case_id == case_id)
            .limit(1)
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.db.execute(stmt)
        active = result.scalars().first()
        if isinstance(active, ReportSessionRecord):
            if self._is_expired_generation_claim(active):
                # Generation/resume claims are committed before remote work so
                # concurrent mutations can be rejected. If the worker is
                # cancelled or the process dies, recover the durable claim
                # while still holding the parent case lock. Follow-up claims
                # are intentionally retained for the user to answer.
                await self.db.delete(active)
                await self.db.flush()
                active = None
        if isinstance(active, ReportSessionRecord):
            raise HTTPException(
                status_code=409,
                detail="A report generation or follow-up session is already active for this case.",
            )

    @staticmethod
    def _is_expired_generation_claim(session: ReportSessionRecord) -> bool:
        payload = session.request_payload_json or {}
        if payload.get(REPORT_CLAIM_STATE_KEY) not in {"generating", "resuming"}:
            return False
        timestamp = session.updated_at or session.created_at
        if timestamp is None:
            return False
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - timestamp > REPORT_CLAIM_LEASE

    async def _lock_case(self, case_id: str) -> CaseRecord:
        result = await self.db.execute(
            select(CaseRecord)
            .where(CaseRecord.case_id == case_id)
            .with_for_update()
        )
        case = result.scalars().first()
        if not isinstance(case, CaseRecord):
            raise HTTPException(status_code=404, detail="Case not found")
        return case

    async def _release_report_claim(
        self,
        case_id: str,
        claim_id: str,
        *,
        restore_question: str | None = None,
    ) -> None:
        case_result = await self.db.execute(
            select(CaseRecord)
            .where(CaseRecord.case_id == case_id)
            .with_for_update()
        )
        case = case_result.scalars().first()
        if not isinstance(case, CaseRecord):
            await self.db.rollback()
            return
        claim_result = await self.db.execute(
            select(ReportSessionRecord)
            .where(
                ReportSessionRecord.session_id == claim_id,
                ReportSessionRecord.case_id == case_id,
            )
            .with_for_update()
        )
        claim = claim_result.scalars().first()
        if isinstance(claim, ReportSessionRecord):
            if restore_question:
                payload = dict(claim.request_payload_json or {})
                payload[REPORT_CLAIM_STATE_KEY] = "followup"
                payload.pop(REPORT_CLAIM_QUESTION_KEY, None)
                claim.request_payload_json = payload
                claim.followup_question = restore_question
            else:
                await self.db.execute(
                    delete(ReportSessionRecord).where(
                        ReportSessionRecord.session_id == claim_id
                    )
                )
        await self.db.commit()

    async def _mark_context_expired(self, case_id: str) -> None:
        await self._lock_case(case_id)
        result = await self.db.execute(
            select(CaseChatState).where(CaseChatState.case_id == case_id).with_for_update()
        )
        state = result.scalars().first()
        if state is None:
            return
        state.status = "expired"
        state.latest_retrieval_context_id = None
        state.active_session_id = None
        state.requires_followup = False
        await self.db.commit()

    async def resume_report(
        self, case_id: str, request: ReportResumeRequest
    ) -> ReportWorkflowResult:
        # Resolve ownership without taking the session lock first, then use the
        # shared case -> session -> analysis lock order for the atomic claim.
        stmt = select(ReportSessionRecord).where(ReportSessionRecord.session_id == request.session_id)
        res = await self.db.execute(stmt)
        preliminary = res.scalars().first()
        if not isinstance(preliminary, ReportSessionRecord):
            raise HTTPException(status_code=404, detail="Report session not found")
        if preliminary.case_id != case_id:
            raise HTTPException(status_code=403, detail="Report session does not belong to this case")
        case = await self._lock_case(case_id)
        locked_result = await self.db.execute(
            select(ReportSessionRecord)
            .where(
                ReportSessionRecord.session_id == request.session_id,
                ReportSessionRecord.case_id == case_id,
            )
            .with_for_update()
        )
        session_record = locked_result.scalars().first()
        if not isinstance(session_record, ReportSessionRecord):
            raise HTTPException(status_code=404, detail="Report session not found")
        if not session_record.followup_question:
            raise HTTPException(
                status_code=409,
                detail="This report session is already being generated or resumed.",
            )
        followup_question = session_record.followup_question
        original = GenerateReportRequest.model_validate(session_record.request_payload_json)
        analysis_context_or_error = await self._validated_case_chat_context(
            case,
            GenerateCaseReportRequest(
                report_type=original.report_type,
                legal=original.legal,
                force_generate=True,
                retrieval_context_id=original.retrieval_context_id,
            ),
        )
        if isinstance(analysis_context_or_error, ReportErrorResponse):
            await self.db.execute(
                delete(ReportSessionRecord).where(
                    ReportSessionRecord.session_id == session_record.session_id
                )
            )
            await self.db.commit()
            return analysis_context_or_error
        analysis_context = analysis_context_or_error

        claim_payload = dict(session_record.request_payload_json or {})
        claim_payload[REPORT_CLAIM_STATE_KEY] = "resuming"
        claim_payload[REPORT_CLAIM_QUESTION_KEY] = followup_question
        session_record.request_payload_json = claim_payload
        session_record.followup_question = ""
        await self.db.commit()

        # 3. Merge answer into the query/incident_summary
        combined_query = original.query
        if request.answer.strip():
            combined_query = (
                f"{original.query}\n\n"
                "Follow-up answer supplied for preliminary report:\n"
                f"{request.answer.strip()}"
            )
        update_fields = {"query": combined_query, "force_generate": True}
        resumed_request = original.model_copy(update=update_fields)

        # 4. Reuse the existing retrieval context from the active session request payload
        new_retrieval_context_id = resumed_request.retrieval_context_id

        # 5. Fetch retrieval context snapshot
        try:
            snapshot = await self.client.get_json(f"/retrieval-contexts/{new_retrieval_context_id}")
        except Exception as exc:
            logger.error("Error retrieving context snapshot during resume: %s", exc)
            await self._release_report_claim(
                case_id,
                request.session_id,
                restore_question=followup_question,
            )
            return self._report_context_wait_response(resumed_request)

        # 6. Complete generation and delete session
        return await self._complete_report_generation_db(
            case_id,
            resumed_request,
            snapshot,
            analysis_context,
            request.session_id,
            followup_question=followup_question,
            followup_answer=request.answer.strip(),
        )

    async def _load_report(
        self, report_id: str, *, for_update: bool = False
    ) -> ReportRecord:
        stmt = select(ReportRecord).where(ReportRecord.report_id == report_id)
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.db.execute(stmt)
        report_record = result.scalars().first()
        if not isinstance(report_record, ReportRecord):
            raise HTTPException(status_code=404, detail="Report not found")
        return report_record

    async def _load_report_for_mutation(self, report_id: str) -> ReportRecord:
        preliminary = await self._load_report(report_id)
        await self._lock_case(preliminary.case_id)
        await self._reject_active_report_session(
            preliminary.case_id,
            for_update=True,
        )
        result = await self.db.execute(
            select(ReportRecord)
            .where(ReportRecord.report_id == report_id)
            .with_for_update()
        )
        report_record = result.scalars().first()
        if not isinstance(report_record, ReportRecord):
            raise HTTPException(status_code=404, detail="Report not found")
        return report_record

    @staticmethod
    def _report_metadata(report_record: ReportRecord) -> dict[str, Any]:
        payload = report_record.report_payload_json or {}
        metadata = payload.get("metadata") or {}
        return dict(metadata) if isinstance(metadata, dict) else {}

    def _materialized_report(self, report_record: ReportRecord) -> CyberCaseReport:
        """Apply analyst narrative edits without modifying generated source data."""
        payload = dict(report_record.report_payload_json or {})
        report = CyberCaseReport.model_validate(payload)
        metadata = self._report_metadata(report_record)
        raw_overlay = metadata.get("manual_overlay")
        overlay: dict[str, Any] = {}
        if isinstance(raw_overlay, dict) and raw_overlay:
            validated = ReportUpdate.model_validate(raw_overlay)
            overlay = validated.model_dump(exclude_unset=True, mode="json")

        report_dump = report.model_dump(mode="json")
        report_dump.update(overlay)
        # Review status is mutable registry metadata, not generated analysis.
        report_dump["review_status"] = report_record.review_status
        fact_pack = dict(report_dump["case_fact_pack"])
        fact_pack["review_status"] = report_record.review_status
        report_dump["case_fact_pack"] = fact_pack
        return CyberCaseReport.model_validate(report_dump)

    def _report_edit_metadata(self, report_record: ReportRecord) -> ReportEditMetadata:
        metadata = self._report_metadata(report_record)
        overlay = metadata.get("manual_overlay")
        if metadata.get("origin") != "manual_edit" or not isinstance(overlay, dict) or not overlay:
            return ReportEditMetadata()
        edited_fields = metadata.get("edited_fields")
        if not isinstance(edited_fields, list):
            edited_fields = sorted(overlay)
        return ReportEditMetadata(
            origin="manual_edit",
            edited_fields=[
                field
                for field in edited_fields
                if isinstance(field, str) and field in REPORT_EDITABLE_FIELDS
            ],
            edited_at=metadata.get("edited_at"),
        )

    def _completed_report_response(
        self, report_record: ReportRecord
    ) -> ReportCompletedResponse:
        if report_record.workflow_status != "completed":
            raise HTTPException(status_code=409, detail="Report generation is still pending")
        report = self._materialized_report(report_record)
        answer = (
            self.report_gen.render_report_markdown(report)
            if self.report_gen
            else report.executive_case_summary
        )
        metadata = self._report_metadata(report_record)
        return ReportCompletedResponse(
            status="completed",
            answer=answer,
            report_id=report.report_id,
            report=report,
            retrieval_context_id=metadata.get("retrieval_context_id"),
            edit_metadata=self._report_edit_metadata(report_record),
        )

    async def get_report(self, report_id: str) -> ReportWorkflowResult:
        report_record = await self._load_report(report_id)
        return self._completed_report_response(report_record)

    async def get_latest_case_report(self, case_id: str) -> ReportWorkflowResult:
        stmt = (
            select(ReportRecord)
            .where(ReportRecord.case_id == case_id)
            .order_by(ReportRecord.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        report_record = result.scalars().first()
        if not report_record:
            raise HTTPException(status_code=404, detail="No report found for this case")

        return self._completed_report_response(report_record)

    async def list_reports(self, case_id: str | None = None) -> list[ReportRegistryItem]:
        stmt = (
            select(ReportRecord, CaseRecord)
            .join(CaseRecord, ReportRecord.case_id == CaseRecord.case_id)
        )
        if case_id:
            stmt = stmt.where(ReportRecord.case_id == case_id)
        stmt = stmt.order_by(ReportRecord.created_at.desc())
        res = await self.db.execute(stmt)
        items = res.all()

        summaries: list[ReportRegistryItem] = []
        for report_record, case_record in items:
            report = self._materialized_report(report_record)
            exec_summary = report.executive_case_summary or ""
            short_summary = exec_summary[:200] + "..." if len(exec_summary) > 200 else exec_summary

            summaries.append(
                ReportRegistryItem(
                    report_id=report_record.report_id,
                    case_id=report_record.case_id,
                    case_title=case_record.title,
                    case_status=case_record.status,
                    severity=case_record.severity,
                    report_type=report_record.report_type,
                    workflow_status=report_record.workflow_status,
                    review_status=report_record.review_status,
                    created_at=(report_record.created_at or datetime.now(timezone.utc)).isoformat(),
                    updated_at=(report_record.updated_at or datetime.now(timezone.utc)).isoformat(),
                    executive_summary_preview=short_summary,
                    edit_metadata=self._report_edit_metadata(report_record),
                )
            )
        return summaries

    async def update_report(
        self,
        report_id: str,
        request: ReportUpdate,
    ) -> ReportWorkflowResult:
        report_record = await self._load_report_for_mutation(report_id)
        if report_record.workflow_status != "completed":
            raise HTTPException(status_code=409, detail="A pending report cannot be edited")

        payload = dict(report_record.report_payload_json or {})
        # Validate the immutable generated payload before accepting an overlay.
        generated_report = CyberCaseReport.model_validate(payload)
        metadata = self._report_metadata(report_record)
        current_overlay = metadata.get("manual_overlay")
        if current_overlay is None:
            current_overlay = {}
        if not isinstance(current_overlay, dict):
            raise HTTPException(status_code=409, detail="Stored report edit metadata is invalid")

        changes = request.model_dump(exclude_unset=True, mode="json")
        merged_overlay = {**current_overlay, **changes}
        validated_overlay = ReportUpdate.model_validate(merged_overlay).model_dump(
            exclude_unset=True,
            mode="json",
        )
        effective_payload = generated_report.model_dump(mode="json")
        effective_payload.update(validated_overlay)
        CyberCaseReport.model_validate(effective_payload)

        edited_at = datetime.now(timezone.utc).isoformat()
        history = metadata.get("edit_history")
        if not isinstance(history, list):
            history = []
        history.append(
            {
                "origin": "manual_edit",
                "edited_fields": sorted(changes),
                "edited_at": edited_at,
            }
        )
        metadata.update(
            {
                "origin": "manual_edit",
                "manual_overlay": validated_overlay,
                "edited_fields": sorted(validated_overlay),
                "edited_at": edited_at,
                "edit_history": history[-100:],
            }
        )
        payload["metadata"] = metadata
        report_record.report_payload_json = payload
        await self.db.commit()
        return self._completed_report_response(report_record)

    async def delete_report(self, report_id: str) -> None:
        report_record = await self._load_report_for_mutation(report_id)
        if report_record.workflow_status != "completed":
            raise HTTPException(status_code=409, detail="A pending report cannot be deleted")

        await self.db.delete(report_record)
        await self.db.commit()

    async def update_review_status(
        self,
        report_id: str,
        request: ReviewStatusUpdate,
    ) -> ReportWorkflowResult:
        report_record = await self._load_report_for_mutation(report_id)
        if report_record.workflow_status != "completed":
            raise HTTPException(status_code=409, detail="A pending report cannot be updated")
        report_record.review_status = request.review_status
        await self.db.commit()
        return self._completed_report_response(report_record)

    async def _start_report_followup_db(
        self,
        case_id: str,
        claim_id: str,
        case_fact_pack: CaseFactPack,
    ) -> ReportFollowUpResponse:
        await self._lock_case(case_id)
        result = await self.db.execute(
            select(ReportSessionRecord)
            .where(
                ReportSessionRecord.session_id == claim_id,
                ReportSessionRecord.case_id == case_id,
            )
            .with_for_update()
        )
        claim = result.scalars().first()
        if not isinstance(claim, ReportSessionRecord) or claim.followup_question:
            raise HTTPException(status_code=409, detail="Report generation claim is no longer active")

        followup_question = self._build_report_followup_question(case_fact_pack)
        payload = dict(claim.request_payload_json or {})
        payload[REPORT_CLAIM_STATE_KEY] = "followup"
        claim.request_payload_json = payload
        claim.followup_question = followup_question
        await self.db.commit()
        request = GenerateReportRequest.model_validate(payload)

        return ReportFollowUpResponse(
            status="followup",
            followup_question=followup_question,
            session_id=claim_id,
            completeness=case_fact_pack.completeness,
            missing_information=case_fact_pack.missing_information,
            retrieval_context_id=request.retrieval_context_id,
        )

    @staticmethod
    def _generation_became_stale() -> ReportErrorResponse:
        return ReportErrorResponse(
            status="analysis_stale",
            error_code="analysis_changed_during_report_generation",
            message=(
                "The case analysis changed while the report was being generated. "
                "No report was saved; retry from the current analysis."
            ),
        )

    async def _lock_validated_analysis(
        self,
        case_id: str,
        captured: ValidatedAnalysisContext,
        claim_id: str,
    ) -> tuple[CaseRecord, ReportSessionRecord] | ReportErrorResponse:
        case_result = await self.db.execute(
            select(CaseRecord)
            .where(CaseRecord.case_id == case_id)
            .with_for_update()
        )
        case = case_result.scalars().first()
        claim_result = await self.db.execute(
            select(ReportSessionRecord)
            .where(
                ReportSessionRecord.session_id == claim_id,
                ReportSessionRecord.case_id == case_id,
            )
            .with_for_update()
        )
        claim = claim_result.scalars().first()
        state_result = await self.db.execute(
            select(CaseChatState)
            .where(CaseChatState.case_id == case_id)
            .with_for_update()
        )
        state = state_result.scalars().first()
        turn_result = await self.db.execute(
            select(CaseChatTurn)
            .where(CaseChatTurn.turn_id == captured.analysis_run_id)
            .with_for_update()
        )
        turn = turn_result.scalars().first()

        valid = bool(
            isinstance(case, CaseRecord)
            and isinstance(claim, ReportSessionRecord)
            and isinstance(state, CaseChatState)
            and isinstance(turn, CaseChatTurn)
            and claim.followup_question == ""
            and case.case_version == captured.case_version
            and case.case_snapshot_hash == captured.case_snapshot_hash
            and CaseContextService.hash_for_case(case) == captured.case_snapshot_hash
            and state.status == "completed"
            and not state.requires_followup
            and state.analysis_case_version == captured.case_version
            and state.analysis_snapshot_hash == captured.case_snapshot_hash
            and state.latest_retrieval_context_id == captured.retrieval_context_id
            and state.latest_analysis_turn_id == captured.analysis_run_id
            and turn.case_id == case_id
            and turn.role == "assistant"
            and turn.turn_type in {"analysis", "followup"}
            and turn.turn_status == "completed"
            and turn.case_version == captured.case_version
            and turn.case_snapshot_hash == captured.case_snapshot_hash
            and turn.retrieval_context_id == captured.retrieval_context_id
        )
        if valid:
            return case, claim
        return self._generation_became_stale()

    async def _complete_report_generation_db(
        self,
        case_id: str,
        request: GenerateReportRequest,
        snapshot: dict[str, Any],
        analysis_context: ValidatedAnalysisContext,
        claim_id: str,
        *,
        followup_question: str | None = None,
        followup_answer: str = "",
    ) -> ReportWorkflowResult:
        if not self.report_gen:
            raise HTTPException(status_code=503, detail="Report Generator not available")

        try:
            logger.info("Formatting report locally from RAG context: %s", request.retrieval_context_id)
            input_snapshot = ReportInputSnapshot.model_validate(snapshot)

            report = self.report_gen.generate(
                request.query,
                input_snapshot.context,
                rag_result=input_snapshot.rag_result,
                mitre_table=input_snapshot.mitre_table,
                rag_answer=input_snapshot.answer,
                report_type=request.report_type,
                legal=request.legal,
                evidence_registry=request.evidence_registry,
                force_generate=request.force_generate,
            )
            if request.legal:
                await self._apply_thanoy_legal_advice(report)

            # Reacquire durable rows only after generation and compare every
            # captured provenance field before any report record is inserted.
            locked = await self._lock_validated_analysis(
                case_id,
                analysis_context,
                claim_id,
            )
            if isinstance(locked, ReportErrorResponse):
                await self.db.execute(
                    delete(ReportSessionRecord).where(
                        ReportSessionRecord.session_id == claim_id
                    )
                )
                await self.db.commit()
                return locked
            case, _claim = locked

            if followup_question is not None:
                case_payload = dict(case.data or {})
                answers = list(case_payload.get("report_followup_answers", []))
                answers.append(
                    {
                        "question": followup_question,
                        "answer": followup_answer,
                        "answered_at": datetime.now(timezone.utc).isoformat(),
                        "source": "report_followup",
                    }
                )
                case_payload["report_followup_answers"] = answers
                case_payload["updated_at"] = datetime.now(timezone.utc).isoformat()
                case.data = case_payload

            existing_report_result = await self.db.execute(
                select(ReportRecord)
                .where(ReportRecord.case_id == case_id)
                .order_by(
                    ReportRecord.created_at.desc(),
                    ReportRecord.updated_at.desc(),
                    ReportRecord.report_id.desc(),
                )
                .with_for_update()
            )
            report_record = existing_report_result.scalars().first()
            if isinstance(report_record, ReportRecord):
                # The report resource is case-owned. Preserve its public
                # identity while replacing the generated document in full.
                report.report_id = report_record.report_id

            report_dump = report.model_dump(mode="json")
            report_dump["metadata"] = {
                "origin": "generated",
                "edited_fields": [],
                "retrieval_context_id": analysis_context.retrieval_context_id,
                "analysis_run_id": analysis_context.analysis_run_id,
                "analysis_case_version": analysis_context.case_version,
                "analysis_snapshot_hash": analysis_context.case_snapshot_hash,
            }
            fact_pack_dump = report.case_fact_pack.model_dump(mode="json")

            if isinstance(report_record, ReportRecord):
                report_record.report_type = report.report_type
                report_record.workflow_status = "completed"
                report_record.review_status = report.review_status
                report_record.report_payload_json = report_dump
                report_record.case_fact_pack_json = fact_pack_dump
            else:
                report_record = ReportRecord(
                    report_id=report.report_id,
                    case_id=case_id,
                    report_type=report.report_type,
                    workflow_status="completed",
                    review_status=report.review_status,
                    report_payload_json=report_dump,
                    case_fact_pack_json=fact_pack_dump,
                )
                self.db.add(report_record)

            stmt = delete(ReportSessionRecord).where(
                ReportSessionRecord.session_id == claim_id
            )
            await self.db.execute(stmt)

            await self.db.commit()
            return self._completed_report_response(report_record)
        except ValueError as e:
            await self.db.rollback()
            await self._release_report_claim(
                case_id,
                claim_id,
                restore_question=followup_question,
            )
            raise HTTPException(status_code=422, detail=str(e))
        except HTTPException:
            await self.db.rollback()
            await self._release_report_claim(
                case_id,
                claim_id,
                restore_question=followup_question,
            )
            raise
        except Exception:
            await self.db.rollback()
            await self._release_report_claim(
                case_id,
                claim_id,
                restore_question=followup_question,
            )
            logger.exception("Error during report generation")
            raise HTTPException(
                status_code=500,
                detail="Report generation failed. Please retry.",
            )
        except BaseException:
            # Cancellation is not an Exception. Best-effort cleanup avoids
            # leaving a claim behind on cooperative task cancellation; the
            # bounded lease above remains the crash-recovery backstop.
            await self.db.rollback()
            await self._release_report_claim(
                case_id,
                claim_id,
                restore_question=followup_question,
            )
            raise

    def _needs_report_followup(self, case_fact_pack: CaseFactPack) -> bool:
        return case_fact_pack.completeness.status == "Incomplete - follow-up required"

    def _report_context_wait_response(self, request: GenerateReportRequest) -> ReportErrorResponse:
        return ReportErrorResponse(
            status="context_expired",
            error_code="retrieval_context_expired",
            message="Report generation could not complete because RAG retrieval context was unavailable. Please retry from the case report page.",
        )

    def _build_report_followup_question(self, case_fact_pack: CaseFactPack) -> str:
        if not case_fact_pack.missing_information:
            return "Could you provide any additional evidence or timeline details before report generation?"
        first_missing = case_fact_pack.missing_information[0]
        return (
            "The preliminary report is incomplete. Please provide the "
            f"{first_missing}, if known. You can answer 'unknown' if unavailable."
        )

    async def _apply_thanoy_legal_advice(self, report: CyberCaseReport) -> None:
        advice = await get_legal_advice(report.executive_case_summary)
        if not advice:
            return

        registry = report.case_fact_pack.evidence_registry
        legal_evidence_id = self._next_report_evidence_id(registry)
        registry.append(
            EvidenceReference(
                evidence_id=legal_evidence_id,
                source_type="legal_source",
                source_name="Thanoy legal AI response",
                excerpt=advice[:1200],
            )
        )

        existing = (
            report.legal_assessments[0]
            if report.legal_assessments
            else report.case_fact_pack.legal_assessments[0]
            if report.case_fact_pack.legal_assessments
            else None
        )
        if not existing:
            return

        case_evidence_id = self._primary_report_evidence_id(report)
        evidence_ids = [item for item in (case_evidence_id, legal_evidence_id) if item]
        assessment = existing.model_copy(
            update={
                "provision_reference": "Thanoy legal AI preliminary assessment",
                "preliminary_relevance": advice,
                "status": "inferred",
                "evidence_ids": evidence_ids,
            }
        )
        report.legal_assessments = [assessment]
        report.case_fact_pack.legal_assessments = [assessment]

    def _primary_report_evidence_id(self, report: CyberCaseReport) -> str:
        for evidence in report.case_fact_pack.evidence_registry:
            if evidence.source_type in {"user_input", "uploaded_file", "log"}:
                return evidence.evidence_id
        if report.case_fact_pack.evidence_registry:
            return report.case_fact_pack.evidence_registry[0].evidence_id
        return ""

    def _next_report_evidence_id(self, registry: list[EvidenceReference]) -> str:
        used = {item.evidence_id for item in registry}
        index = 1
        while f"E-{index:03d}" in used:
            index += 1
        return f"E-{index:03d}"


__all__ = [
    "ReportWorkflowResult",
    "ReportWorkflowService",
]
