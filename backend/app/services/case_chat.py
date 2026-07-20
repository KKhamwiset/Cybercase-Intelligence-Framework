"""Durable case-chat orchestration.

Database locks are held only while claiming or finalising a turn.  The remote
RAG call deliberately happens after the pending claim is committed, so a slow
model cannot hold a Postgres row lock or block ordinary case edits.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import CaseRecord
from app.models.case_chat import CaseChatState, CaseChatTurn
from app.schemas.case_chat import (
    CaseChatContextSummary,
    CaseChatAttackCandidate,
    CaseChatMessageRequest,
    CaseChatMessageResponse,
    CaseReportReadiness,
    CaseChatTurnView,
    CaseChatWorkspaceView,
)
from app.schemas.rag import MitreTableRow
from app.services.case_context import CaseContextService
from app.services.rag_client import RagServiceClient


PENDING_TIMEOUT = timedelta(minutes=10)


class CaseChatService:
    def __init__(
        self,
        *,
        db: AsyncSession,
        client: RagServiceClient | None = None,
        context_service: type[CaseContextService] = CaseContextService,
    ) -> None:
        self.db = db
        self.client = client or RagServiceClient()
        self.context_service = context_service

    def ensure_case_snapshot(self, case: CaseRecord) -> bool:
        """Fill a missing legacy snapshot without treating the case as edited."""
        snapshot_hash = self.context_service.hash_for_case(case)
        current_hash = getattr(case, "case_snapshot_hash", None) or ""
        current_version = getattr(case, "case_version", None) or 0
        if not current_hash or current_version < 1:
            case.case_snapshot_hash = snapshot_hash
            case.case_version = 1
            return True
        return False

    def update_case_snapshot(self, case: CaseRecord, previous_hash: str | None) -> bool:
        """Advance a case only when fields sent to RAG actually changed."""
        next_hash = self.context_service.hash_for_case(case)
        known_hash = previous_hash or getattr(case, "case_snapshot_hash", None) or ""
        current_version = getattr(case, "case_version", None) or 0
        if not known_hash or current_version < 1:
            case.case_version = 1
            case.case_snapshot_hash = next_hash
            return True
        case.case_snapshot_hash = next_hash
        if known_hash != next_hash:
            case.case_version = current_version + 1
            return True
        return False

    @staticmethod
    def _fingerprint(request: CaseChatMessageRequest) -> str:
        raw = json.dumps(
            {"action": request.action, "message": request.message},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _turn_type(action: str) -> str:
        return "analysis" if action in {"analyze", "refresh_analysis"} else action

    @staticmethod
    def _build_analysis_outputs(
        *,
        rag_response: dict[str, object],
        analysis_run_id: str,
        case_id: str,
        case_version: int,
        case_snapshot_hash: str,
        retrieval_context_id: str | None,
        generated_at: datetime,
    ) -> dict[str, object]:
        """Validate and persist only structured RAG outputs.

        The RAG contract currently exposes a structured MITRE table but not
        structured gaps or recommendations. Free text is intentionally not
        parsed into synthetic output records.
        """
        raw_rows = rag_response.get("mitre_table") or []
        if not isinstance(raw_rows, list):
            raise HTTPException(status_code=422, detail="RAG mitre_table must be a list")

        mappings: list[dict[str, object]] = []
        for index, raw_row in enumerate(raw_rows, start=1):
            row = MitreTableRow.model_validate(raw_row)
            source_references = [
                reference
                for reference in (
                    retrieval_context_id,
                    row.mitre_url,
                    f"{row.source}:{row.technique_id or row.name}",
                )
                if reference
            ]
            mappings.append(
                {
                    "item_id": row.technique_id or f"RAG-MAP-{index:03d}",
                    "title": row.name,
                    "description": row.description,
                    "source_type": "rag",
                    "analysis_run_id": analysis_run_id,
                    "case_id": case_id,
                    "case_version": case_version,
                    "case_snapshot_hash": case_snapshot_hash,
                    "generated_at": generated_at.isoformat(),
                    "source_references": source_references,
                    "review_status": "unreviewed",
                    "status": "candidate",
                    "details": row.model_dump(mode="json"),
                }
            )

        return {
            "analysis_run_id": analysis_run_id,
            "case_id": case_id,
            "case_version": case_version,
            "case_snapshot_hash": case_snapshot_hash,
            "generated_at": generated_at.isoformat(),
            "retrieval_context_id": retrieval_context_id,
            "evidence": [],
            "gaps": [],
            "attack_mappings": mappings,
            "recommendations": [],
        }

    @staticmethod
    def _visible_message(request: CaseChatMessageRequest) -> str:
        if request.action == "analyze":
            return "Analyze saved case"
        if request.action == "refresh_analysis":
            return "Refresh analysis"
        return request.message

    @staticmethod
    def _context_summary(case: CaseRecord) -> CaseChatContextSummary:
        data = case.data or {}
        attack_candidates = sorted(
            [
                item
                for item in (data.get("attack_mappings") or [])
                if isinstance(item, dict)
                and isinstance(item.get("metadata"), dict)
                and item["metadata"].get("source_type") == "system_rule"
                and item["metadata"].get("status", "candidate") == "candidate"
                and not item["metadata"].get("analyst_verified", False)
            ],
            key=lambda item: (
                str(item.get("mapping_id") or ""),
                str(item.get("technique_id") or ""),
                str(item.get("technique_name") or ""),
            ),
        )
        return CaseChatContextSummary(
            title=case.title,
            incident_summary=str(data.get("incident_summary") or ""),
            case_version=case.case_version,
            case_snapshot_hash=case.case_snapshot_hash,
            evidence_count=sum(
                1
                for item in (data.get("evidence_items") or [])
                if isinstance(item, dict)
                and item.get("source_type") in {"analyst_input", "user_input", "log", "document"}
            ),
            gap_count=0,
            attack_mapping_count=len(attack_candidates),
            gaps=[],
            attack_candidates=[
                CaseChatAttackCandidate(
                    mapping_id=str(item.get("mapping_id") or ""),
                    technique_id=str(item.get("technique_id") or ""),
                    technique_name=str(item.get("technique_name") or ""),
                    tactic=item.get("tactic"),
                    status=str((item.get("metadata") or {}).get("status") or "unknown"),
                )
                for item in attack_candidates
            ],
            updated_at=case.updated_at,
        )

    @staticmethod
    def _turn_view(turn: CaseChatTurn) -> CaseChatTurnView:
        return CaseChatTurnView(
            turn_id=turn.turn_id,
            role=turn.role,
            content=turn.content,
            turn_type=turn.turn_type,
            turn_status=turn.turn_status,
            case_version=turn.case_version,
            case_snapshot_hash=turn.case_snapshot_hash,
            created_at=turn.created_at,
        )

    @staticmethod
    def _is_report_eligible(case: CaseRecord, state: CaseChatState) -> bool:
        return bool(
            state.status == "completed"
            and not state.requires_followup
            and state.latest_retrieval_context_id
            and state.analysis_case_version == case.case_version
            and state.analysis_snapshot_hash == case.case_snapshot_hash
        )

    @staticmethod
    def _report_readiness(case: CaseRecord, state: CaseChatState) -> CaseReportReadiness:
        common = {
            "case_id": case.case_id,
            "current_case_version": case.case_version,
            "current_case_snapshot_hash": case.case_snapshot_hash,
            "latest_analysis_turn_id": state.latest_analysis_turn_id,
        }
        analysis_is_current = (
            state.analysis_case_version == case.case_version
            and state.analysis_snapshot_hash == case.case_snapshot_hash
        )
        if state.status == "stale" or (
            state.analysis_case_version is not None and not analysis_is_current
        ):
            return CaseReportReadiness(
                **common,
                analysis_status="stale",
                report_eligible=False,
                reason="analysis_stale",
            )
        if state.status == "pending" or state.requires_followup:
            return CaseReportReadiness(
                **common,
                analysis_status="pending",
                report_eligible=False,
                reason="analysis_pending",
            )
        if state.status == "failed":
            return CaseReportReadiness(
                **common,
                analysis_status="failed",
                report_eligible=False,
                reason="analysis_failed",
            )
        if state.status == "expired":
            return CaseReportReadiness(
                **common,
                analysis_status="expired",
                report_eligible=False,
                reason="context_expired",
            )
        if state.status == "completed" and analysis_is_current:
            if not state.latest_retrieval_context_id:
                return CaseReportReadiness(
                    **common,
                    analysis_status="expired",
                    report_eligible=False,
                    reason="context_expired",
                )
            return CaseReportReadiness(
                **common,
                analysis_status="completed",
                report_eligible=True,
                reason="ready",
                latest_retrieval_context_id=state.latest_retrieval_context_id,
            )
        return CaseReportReadiness(
            **common,
            analysis_status="missing",
            report_eligible=False,
            reason="analysis_required",
        )

    async def _load_case(self, case_id: str, *, for_update: bool = False) -> CaseRecord:
        stmt = select(CaseRecord).where(CaseRecord.case_id == case_id)
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.db.execute(stmt)
        case = result.scalars().first()
        if case is None:
            raise HTTPException(status_code=404, detail="Case not found")
        return case

    async def _get_or_create_state(
        self, case: CaseRecord, *, for_update: bool = False
    ) -> CaseChatState:
        stmt = select(CaseChatState).where(CaseChatState.case_id == case.case_id)
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.db.execute(stmt)
        state = result.scalars().first()
        if state is not None:
            return state

        # The unique primary key and ON CONFLICT make first-chat creation safe
        # across API workers; there is no in-process-only lock.
        stmt = insert(CaseChatState).values(
            case_id=case.case_id,
            case_version=case.case_version,
            case_snapshot_hash=case.case_snapshot_hash,
            status="idle",
        ).on_conflict_do_nothing(index_elements=["case_id"])
        await self.db.execute(stmt)
        select_stmt = select(CaseChatState).where(CaseChatState.case_id == case.case_id)
        if for_update:
            select_stmt = select_stmt.with_for_update()
        result = await self.db.execute(select_stmt)
        state = result.scalars().first()
        if state is None:  # pragma: no cover - defensive, database constraint guarantees this
            raise HTTPException(status_code=503, detail="Case chat state could not be initialized")
        return state

    def _sync_state_to_case(self, case: CaseRecord, state: CaseChatState) -> None:
        state.case_version = case.case_version
        state.case_snapshot_hash = case.case_snapshot_hash
        if (
            state.analysis_case_version is not None
            and (
                state.analysis_case_version != case.case_version
                or state.analysis_snapshot_hash != case.case_snapshot_hash
            )
        ):
            state.status = "stale"
            state.requires_followup = False
            state.active_session_id = None
            state.latest_retrieval_context_id = None

    async def _expire_pending_if_needed(self, state: CaseChatState) -> bool:
        started = state.pending_started_at
        if state.status != "pending" or started is None:
            return False
        now = datetime.now(timezone.utc)
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        if now - started <= PENDING_TIMEOUT:
            return False
        result = await self.db.execute(
            select(CaseChatTurn)
            .where(
                CaseChatTurn.case_id == state.case_id,
                CaseChatTurn.idempotency_key == state.pending_idempotency_key,
            )
            .with_for_update()
        )
        turn = result.scalars().first()
        if turn and turn.turn_status == "pending":
            turn.turn_status = "failed"
        state.status = "failed"
        state.pending_idempotency_key = None
        state.pending_started_at = None
        return True

    async def _workspace(self, case: CaseRecord, state: CaseChatState) -> CaseChatWorkspaceView:
        result = await self.db.execute(
            select(CaseChatTurn)
            .where(CaseChatTurn.case_id == case.case_id)
            .order_by(CaseChatTurn.created_at.asc(), CaseChatTurn.turn_id.asc())
        )
        turns = result.scalars().all()
        return CaseChatWorkspaceView(
            case_id=case.case_id,
            context=self._context_summary(case),
            turns=[self._turn_view(turn) for turn in turns],
            status=state.status,
            requires_followup=state.requires_followup,
            active_session_id=state.active_session_id,
            latest_retrieval_context_id=state.latest_retrieval_context_id,
            analysis_case_version=state.analysis_case_version,
            analysis_snapshot_hash=state.analysis_snapshot_hash,
            report_eligible=self._is_report_eligible(case, state),
        )

    async def get_workspace(self, case_id: str) -> CaseChatWorkspaceView:
        """Read only persisted chat state; this method must never call RAG.

        Legacy hash/state maintenance below is idempotent database maintenance,
        kept as a defensive fallback after migration-time backfill.  Repeated
        GETs do not create an analysis or contact the RAG service.
        """
        case = await self._load_case(case_id, for_update=True)
        changed = self.ensure_case_snapshot(case)
        state = await self._get_or_create_state(case, for_update=True)
        self._sync_state_to_case(case, state)
        changed = await self._expire_pending_if_needed(state) or changed
        # GET never contacts RAG. Always end this short database transaction
        # promptly, even when maintenance was unnecessary, so SELECT FOR UPDATE
        # cannot remain held until dependency cleanup.
        await self.db.commit()
        return await self._workspace(case, state)

    async def get_report_readiness(self, case_id: str) -> CaseReportReadiness:
        """Return backend-owned report eligibility without starting retrieval."""
        case = await self._load_case(case_id, for_update=True)
        self.ensure_case_snapshot(case)
        state = await self._get_or_create_state(case, for_update=True)
        self._sync_state_to_case(case, state)
        await self._expire_pending_if_needed(state)
        readiness = self._report_readiness(case, state)
        await self.db.commit()

        context_id = readiness.latest_retrieval_context_id
        if not readiness.report_eligible or not context_id:
            return readiness

        try:
            snapshot = await self.client.get_json(f"/retrieval-contexts/{context_id}")
            if not snapshot or "context" not in snapshot:
                raise HTTPException(status_code=404, detail="Retrieval context not found")
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
            return await self._mark_readiness_context_expired(case_id, context_id)
        return readiness

    async def _mark_readiness_context_expired(
        self, case_id: str, context_id: str
    ) -> CaseReportReadiness:
        case = await self._load_case(case_id, for_update=True)
        state = await self._get_or_create_state(case, for_update=True)
        if (
            state.status == "completed"
            and state.latest_retrieval_context_id == context_id
            and state.analysis_case_version == case.case_version
            and state.analysis_snapshot_hash == case.case_snapshot_hash
        ):
            state.status = "expired"
            state.latest_retrieval_context_id = None
            state.active_session_id = None
            state.requires_followup = False
        readiness = self._report_readiness(case, state)
        await self.db.commit()
        return readiness

    async def invalidate_for_case_update(self, case: CaseRecord) -> None:
        """Invalidate only existing chat state after canonical case data changes."""
        result = await self.db.execute(
            select(CaseChatState)
            .where(CaseChatState.case_id == case.case_id)
            .with_for_update()
        )
        state = result.scalars().first()
        # A few lightweight route tests provide a deliberately generic fake
        # session that returns the case record for every SELECT.  Production
        # SQLAlchemy returns CaseChatState; avoid treating an unrelated record
        # as persisted chat state.
        if not isinstance(state, CaseChatState):
            return
        state.case_version = case.case_version
        state.case_snapshot_hash = case.case_snapshot_hash
        if state.analysis_case_version is not None:
            state.status = "stale"
            state.active_session_id = None
            state.requires_followup = False
            state.latest_retrieval_context_id = None
            state.pending_idempotency_key = None
            state.pending_started_at = None
        elif state.status != "pending":
            state.status = "idle"

    async def _idempotent_response(
        self, case: CaseRecord, state: CaseChatState, turn: CaseChatTurn
    ) -> CaseChatMessageResponse:
        assistant_message = None
        assistant_conditions = [
            CaseChatTurn.case_id == case.case_id,
            CaseChatTurn.role == "assistant",
            CaseChatTurn.turn_type == turn.turn_type,
            CaseChatTurn.case_version == turn.case_version,
        ]
        # Server defaults are normally returned by Postgres, but an action can
        # be replayed before a lightweight adapter has hydrated created_at.
        if turn.created_at is not None:
            assistant_conditions.append(CaseChatTurn.created_at >= turn.created_at)
        result = await self.db.execute(
            select(CaseChatTurn)
            .where(*assistant_conditions)
            .order_by(CaseChatTurn.created_at.desc(), CaseChatTurn.turn_id.desc())
            .limit(1)
        )
        assistant = result.scalars().first()
        if assistant and turn.turn_status != "pending":
            assistant_message = assistant.content
        return CaseChatMessageResponse(
            status=state.status,
            turn_status=turn.turn_status,
            turn_type=turn.turn_type,
            message="Existing chat action returned.",
            assistant_message=assistant_message,
            session_id=state.active_session_id,
            retrieval_context_id=state.latest_retrieval_context_id,
            case_version=case.case_version,
            case_snapshot_hash=case.case_snapshot_hash,
            report_eligible=self._is_report_eligible(case, state),
            requires_followup=state.requires_followup,
            idempotent=True,
        )

    async def send_message(
        self,
        case_id: str,
        request: CaseChatMessageRequest,
        *,
        idempotency_key: str,
    ) -> CaseChatMessageResponse:
        if not idempotency_key.strip():
            raise HTTPException(status_code=400, detail="Idempotency-Key is required")
        fingerprint = self._fingerprint(request)
        turn_type = self._turn_type(request.action)

        # Claim and commit the pending action before the RAG call.  The lock is
        # released by commit below; no DB lock spans a network request.
        case = await self._load_case(case_id, for_update=True)
        self.ensure_case_snapshot(case)
        state = await self._get_or_create_state(case, for_update=True)
        await self._expire_pending_if_needed(state)
        self._sync_state_to_case(case, state)
        existing_result = await self.db.execute(
            select(CaseChatTurn)
            .where(
                CaseChatTurn.case_id == case_id,
                CaseChatTurn.idempotency_key == idempotency_key,
            )
            .with_for_update()
        )
        existing = existing_result.scalars().first()
        if existing:
            if existing.payload_fingerprint != fingerprint:
                raise HTTPException(status_code=409, detail="Idempotency-Key was used with a different payload")
            await self.db.commit()
            return await self._idempotent_response(case, state, existing)
        if state.status == "pending":
            await self.db.commit()
            return CaseChatMessageResponse(
                status="pending",
                turn_status="pending",
                turn_type=turn_type,
                message="Another case analysis is already in progress.",
                case_version=case.case_version,
                case_snapshot_hash=case.case_snapshot_hash,
            )
        if state.requires_followup and request.action != "followup":
            await self.db.commit()
            raise HTTPException(
                status_code=409,
                detail="Complete the active analysis follow-up before starting another action.",
            )
        if request.action == "analyze" and self._is_report_eligible(case, state):
            await self.db.commit()
            raise HTTPException(
                status_code=409,
                detail=(
                    "A current analysis already exists. Use refresh_analysis to rerun it intentionally."
                ),
            )
        if request.action == "followup" and (
            not state.requires_followup or not state.active_session_id
        ):
            raise HTTPException(status_code=409, detail="No active case-chat follow-up is available")

        captured_version = case.case_version
        captured_hash = case.case_snapshot_hash
        user_turn = CaseChatTurn(
            turn_id=f"CCT-{uuid4().hex}",
            case_id=case_id,
            role="user",
            content=self._visible_message(request),
            turn_type=turn_type,
            turn_status="pending",
            case_version=captured_version,
            case_snapshot_hash=captured_hash,
            idempotency_key=idempotency_key,
            payload_fingerprint=fingerprint,
        )
        self.db.add(user_turn)
        state.status = "pending"
        state.pending_idempotency_key = idempotency_key
        state.pending_started_at = datetime.now(timezone.utc)
        state.case_version = captured_version
        state.case_snapshot_hash = captured_hash
        await self.db.commit()

        try:
            if request.action == "followup":
                rag_response = await self.client.post_json(
                    "/resume", {"session_id": state.active_session_id, "answer": request.message}
                )
            else:
                payload = self.context_service.build_payload_for_case(case)
                prompt = self.context_service.render_rag_prompt(
                    payload, action=request.action, visible_message=request.message
                )
                rag_response = await self.client.post_json("/query", {"query": prompt, "use_agent": True})
        except HTTPException as exc:
            is_expired = request.action == "followup" and exc.status_code == 404
            return await self._finalize_failure(
                case_id, user_turn.turn_id, idempotency_key, exc, expired=is_expired
            )
        except Exception as exc:  # pragma: no cover - client normally raises HTTPException
            return await self._finalize_failure(case_id, user_turn.turn_id, idempotency_key, exc)

        return await self._finalize_success(
            case_id,
            user_turn.turn_id,
            idempotency_key,
            turn_type,
            captured_version,
            captured_hash,
            rag_response,
        )

    async def _finalize_failure(
        self,
        case_id: str,
        turn_id: str,
        idempotency_key: str,
        error: Exception,
        *,
        expired: bool = False,
    ) -> CaseChatMessageResponse:
        case = await self._load_case(case_id, for_update=True)
        self.ensure_case_snapshot(case)
        state = await self._get_or_create_state(case, for_update=True)
        result = await self.db.execute(
            select(CaseChatTurn).where(CaseChatTurn.turn_id == turn_id).with_for_update()
        )
        turn = result.scalars().first()
        if turn is None:
            raise HTTPException(status_code=409, detail="Case chat action no longer exists")
        owns_pending_action = (
            state.status == "pending" and state.pending_idempotency_key == idempotency_key
        )
        turn.turn_status = "expired" if expired else "failed"
        if not owns_pending_action:
            # A timed-out action may finish after a newer action claimed the
            # state. Persist its outcome without clearing the newer lock.
            await self.db.commit()
            return CaseChatMessageResponse(
                status=state.status,
                turn_status=turn.turn_status,
                turn_type=turn.turn_type,
                message="The earlier case-chat action finished after a newer action began.",
                case_version=case.case_version,
                case_snapshot_hash=case.case_snapshot_hash,
                report_eligible=self._is_report_eligible(case, state),
                requires_followup=state.requires_followup,
            )
        question_failed = turn.turn_type == "question"
        analysis_markers_are_current = bool(
            question_failed
            and state.latest_analysis_turn_id
            and state.analysis_case_version == case.case_version
            and state.analysis_snapshot_hash == case.case_snapshot_hash
        )
        current_analysis_survives = bool(
            analysis_markers_are_current
            and state.latest_retrieval_context_id
        )
        if question_failed:
            state.status = (
                "completed"
                if current_analysis_survives
                else "expired"
                if analysis_markers_are_current
                else "stale"
                if state.analysis_case_version is not None
                else "idle"
            )
            state.active_session_id = None
            state.requires_followup = False
        else:
            state.status = "expired" if expired else "failed"
            state.active_session_id = None if expired else state.active_session_id
            state.requires_followup = False if expired else state.requires_followup
            state.latest_retrieval_context_id = (
                None if expired else state.latest_retrieval_context_id
            )
        state.pending_idempotency_key = None
        state.pending_started_at = None
        state.case_version = case.case_version
        state.case_snapshot_hash = case.case_snapshot_hash
        await self.db.commit()
        message = (
            "The question failed, but the current analysis remains available."
            if current_analysis_survives
            else "The question could not be completed."
            if question_failed
            else "RAG session expired. Refresh analysis to continue."
            if expired
            else "Case analysis failed. Refresh analysis to retry."
        )
        return CaseChatMessageResponse(
            status=state.status,
            turn_status=turn.turn_status,
            turn_type=turn.turn_type,
            message=message,
            case_version=case.case_version,
            case_snapshot_hash=case.case_snapshot_hash,
            report_eligible=self._is_report_eligible(case, state),
        )

    async def _finalize_success(
        self,
        case_id: str,
        turn_id: str,
        idempotency_key: str,
        turn_type: str,
        captured_version: int,
        captured_hash: str,
        rag_response: dict[str, object],
    ) -> CaseChatMessageResponse:
        case = await self._load_case(case_id, for_update=True)
        self.ensure_case_snapshot(case)
        state = await self._get_or_create_state(case, for_update=True)
        result = await self.db.execute(
            select(CaseChatTurn).where(CaseChatTurn.turn_id == turn_id).with_for_update()
        )
        turn = result.scalars().first()
        if turn is None:
            raise HTTPException(status_code=409, detail="Case chat action no longer exists")
        owns_pending_action = (
            state.status == "pending" and state.pending_idempotency_key == idempotency_key
        )
        answer = str(rag_response.get("answer") or rag_response.get("followup_question") or "")
        followup = str(rag_response.get("followup_question") or "")
        rag_status = str(rag_response.get("status") or "completed")
        session_id = str(rag_response.get("session_id") or "") or None
        retrieval_context_id = str(rag_response.get("retrieval_context_id") or "") or None
        completes_analysis = turn_type == "analysis" or (
            turn_type == "followup" and state.requires_followup and bool(state.active_session_id)
        )
        stale = (
            not owns_pending_action
            or case.case_version != captured_version
            or case.case_snapshot_hash != captured_hash
        )
        result_status = "stale" if stale else "completed"
        turn.turn_status = result_status
        assistant_turn_id = f"CCT-{uuid4().hex}"
        generated_at = datetime.now(timezone.utc)
        analysis_outputs: dict[str, object] = {}
        if not stale and completes_analysis and rag_status != "followup":
            try:
                analysis_outputs = self._build_analysis_outputs(
                    rag_response=rag_response,
                    analysis_run_id=assistant_turn_id,
                    case_id=case_id,
                    case_version=captured_version,
                    case_snapshot_hash=captured_hash,
                    retrieval_context_id=retrieval_context_id,
                    generated_at=generated_at,
                )
            except (HTTPException, ValidationError):
                turn.turn_status = "failed"
                state.status = "failed"
                state.requires_followup = False
                state.active_session_id = None
                state.latest_retrieval_context_id = None
                state.pending_idempotency_key = None
                state.pending_started_at = None
                await self.db.commit()
                return CaseChatMessageResponse(
                    status="failed",
                    turn_status="failed",
                    turn_type=turn_type,
                    message="RAG returned invalid structured analysis output.",
                    case_version=case.case_version,
                    case_snapshot_hash=case.case_snapshot_hash,
                    report_eligible=False,
                )
        assistant_turn = CaseChatTurn(
            turn_id=assistant_turn_id,
            case_id=case_id,
            role="assistant",
            content=answer or "The RAG service completed without a visible response.",
            turn_type=turn_type,
            turn_status=result_status,
            case_version=captured_version,
            case_snapshot_hash=captured_hash,
            rag_session_id=session_id,
            retrieval_context_id=retrieval_context_id,
            analysis_outputs_json=analysis_outputs,
        )
        self.db.add(assistant_turn)
        if owns_pending_action:
            state.case_version = case.case_version
            state.case_snapshot_hash = case.case_snapshot_hash
            state.pending_idempotency_key = None
            state.pending_started_at = None
        if not owns_pending_action:
            # Keep the newer pending/completed state untouched. The old result
            # remains visible as a stale historical turn only.
            pass
        elif stale:
            state.status = "stale"
            state.requires_followup = False
            state.active_session_id = None
            state.latest_retrieval_context_id = None
        elif completes_analysis:
            state.status = "completed"
            state.requires_followup = rag_status == "followup"
            state.active_session_id = session_id if state.requires_followup else None
            state.analysis_case_version = captured_version
            state.analysis_snapshot_hash = captured_hash
            state.latest_analysis_turn_id = None if state.requires_followup else assistant_turn.turn_id
            state.latest_retrieval_context_id = None if state.requires_followup else retrieval_context_id
        else:
            # Questions are chat history, not analysis runs. Preserve any prior
            # completed analysis markers and never make a question report-eligible.
            state.status = "completed"
            state.requires_followup = False
            state.active_session_id = None
        await self.db.commit()
        return CaseChatMessageResponse(
            status=state.status,
            turn_status=result_status,
            turn_type=turn_type,
            message=(
                "Analysis completed against an older case version. Refresh analysis before reporting."
                if stale and completes_analysis
                else "The case-chat response used an older case version."
                if stale
                else "Case analysis requires follow-up."
                if completes_analysis and rag_status == "followup"
                else "Case analysis completed."
                if completes_analysis
                else "Case chat response completed."
            ),
            assistant_message=assistant_turn.content,
            followup_question=followup or None,
            session_id=state.active_session_id,
            retrieval_context_id=state.latest_retrieval_context_id,
            case_version=case.case_version,
            case_snapshot_hash=case.case_snapshot_hash,
            report_eligible=self._is_report_eligible(case, state),
            requires_followup=state.requires_followup,
        )


__all__ = ["CaseChatService", "PENDING_TIMEOUT"]
