from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import CaseRecord
from app.models.case_chat import CaseChatState, CaseChatTurn
from app.schemas.cases import (
    CaseAnalysisOutputState,
    CaseHistoricalOutputBucket,
    CaseHistoricalOutputBuckets,
    CaseOutputBucket,
    CaseOutputBuckets,
    CaseOutputItem,
    CaseOutputsResponse,
)


_OUTPUT_KEYS = ("evidence", "gaps", "attack_mappings", "recommendations")


class CaseOutputSummaryService:
    """Build the authoritative, lifecycle-aware case output projection."""

    def __init__(self, *, db: AsyncSession) -> None:
        self.db = db

    async def get_outputs(self, case_id: str) -> CaseOutputsResponse:
        case_result = await self.db.execute(
            select(CaseRecord).where(CaseRecord.case_id == case_id)
        )
        case = case_result.scalars().first()
        if case is None:
            raise HTTPException(status_code=404, detail="Case not found")

        state_result = await self.db.execute(
            select(CaseChatState).where(CaseChatState.case_id == case_id)
        )
        state = state_result.scalars().first()
        if not isinstance(state, CaseChatState):
            state = None

        latest_turn: CaseChatTurn | None = None
        if state is not None and state.latest_analysis_turn_id:
            turn_result = await self.db.execute(
                select(CaseChatTurn).where(
                    CaseChatTurn.turn_id == state.latest_analysis_turn_id,
                    CaseChatTurn.case_id == case_id,
                )
            )
            candidate = turn_result.scalars().first()
            if isinstance(candidate, CaseChatTurn):
                latest_turn = candidate

        analysis, current_turn = self._analysis_state(case, state, latest_turn)
        history_provenance_valid = bool(
            latest_turn is not None and self._outputs_match_turn_provenance(latest_turn)
        )
        if current_turn is not None and not self._outputs_have_valid_provenance(case, current_turn):
            # A completed chat turn does not authorize malformed output
            # provenance. Keep analysis-derived current counts at zero.
            analysis = CaseAnalysisOutputState(
                status="stale",
                analyzed_case_version=current_turn.case_version,
                analyzed_snapshot_hash=current_turn.case_snapshot_hash,
            )
            current_turn = None
        current: dict[str, list[CaseOutputItem]] = {
            key: [] for key in _OUTPUT_KEYS
        }
        historical: dict[str, list[CaseOutputItem]] = {
            key: [] for key in _OUTPUT_KEYS
        }

        self._add_analyst_intake(case, current, historical)
        self._add_deterministic_candidates(
            case,
            current,
            historical,
            show_current=analysis.status != "completed",
        )
        self._add_legacy_history(case, historical)

        if current_turn is not None:
            self._add_turn_outputs(current_turn, current)
        elif latest_turn is not None:
            self._add_turn_outputs(
                latest_turn,
                historical,
                trusted_provenance=history_provenance_valid,
            )

        return CaseOutputsResponse(
            case_id=case.case_id,
            case_version=case.case_version,
            analysis=analysis,
            outputs=CaseOutputBuckets(
                **{
                    key: CaseOutputBucket(
                        current_count=len(items),
                        items=items,
                        source_types=sorted({item.source_type for item in items}),
                    )
                    for key, items in current.items()
                }
            ),
            historical_outputs=CaseHistoricalOutputBuckets(
                **{
                    key: CaseHistoricalOutputBucket(
                        historical_count=len(items), items=items
                    )
                    for key, items in historical.items()
                }
            ),
        )

    @staticmethod
    def _analysis_state(
        case: CaseRecord,
        state: CaseChatState | None,
        turn: CaseChatTurn | None,
    ) -> tuple[CaseAnalysisOutputState, CaseChatTurn | None]:
        if state is None or state.status == "idle":
            return CaseAnalysisOutputState(status="not_started"), None
        if state.status == "pending" or state.requires_followup:
            return CaseAnalysisOutputState(
                status="pending",
                analyzed_case_version=state.analysis_case_version,
                analyzed_snapshot_hash=state.analysis_snapshot_hash,
            ), None
        if state.status in {"failed", "expired"}:
            return CaseAnalysisOutputState(
                status=state.status,
                analyzed_case_version=state.analysis_case_version,
                analyzed_snapshot_hash=state.analysis_snapshot_hash,
            ), None

        state_is_current = (
            state.analysis_case_version == case.case_version
            and state.analysis_snapshot_hash == case.case_snapshot_hash
        )
        if state.status == "stale" or (
            state.analysis_case_version is not None and not state_is_current
        ):
            return CaseAnalysisOutputState(
                status="stale",
                analyzed_case_version=state.analysis_case_version,
                analyzed_snapshot_hash=state.analysis_snapshot_hash,
            ), None
        if not state.latest_analysis_turn_id:
            return CaseAnalysisOutputState(status="not_started"), None
        if not state.latest_retrieval_context_id:
            return CaseAnalysisOutputState(
                status="expired",
                analyzed_case_version=state.analysis_case_version,
                analyzed_snapshot_hash=state.analysis_snapshot_hash,
            ), None

        turn_is_current = bool(
            turn is not None
            and turn.role == "assistant"
            and turn.turn_type in {"analysis", "followup"}
            and turn.turn_status == "completed"
            and turn.turn_id == state.latest_analysis_turn_id
            and turn.case_id == case.case_id
            and turn.case_version == case.case_version
            and turn.case_snapshot_hash == case.case_snapshot_hash
            and turn.retrieval_context_id == state.latest_retrieval_context_id
            and state_is_current
        )
        if not turn_is_current:
            return CaseAnalysisOutputState(
                status="stale",
                analyzed_case_version=state.analysis_case_version,
                analyzed_snapshot_hash=state.analysis_snapshot_hash,
            ), None
        return (
            CaseAnalysisOutputState(
                status="completed",
                analysis_run_id=turn.turn_id,
                analyzed_case_version=turn.case_version,
                analyzed_snapshot_hash=turn.case_snapshot_hash,
            ),
            turn,
        )

    @staticmethod
    def _item(
        *,
        item_id: str,
        title: str,
        description: str,
        source_type: str,
        case_version: int,
        analysis_run_id: str | None = None,
        generated_at: datetime | str | None = None,
        source_references: Iterable[str] = (),
        review_status: str = "unreviewed",
        status: str = "unknown",
        details: dict[str, Any] | None = None,
    ) -> CaseOutputItem:
        return CaseOutputItem(
            item_id=item_id,
            title=title,
            description=description,
            source_type=source_type,
            analysis_run_id=analysis_run_id,
            case_version=case_version,
            generated_at=generated_at,
            source_references=[item for item in source_references if item],
            review_status=review_status,
            status=status,
            details=details or {},
        )

    def _add_analyst_intake(
        self,
        case: CaseRecord,
        current: dict[str, list[CaseOutputItem]],
        historical: dict[str, list[CaseOutputItem]],
    ) -> None:
        data = case.data or {}
        narrative = str(data.get("incident_summary") or "").strip()
        if narrative:
            current["evidence"].append(
                self._item(
                    item_id="INTAKE-NARRATIVE",
                    title="Analyst-provided intake narrative",
                    description=narrative,
                    source_type="analyst_input",
                    case_version=case.case_version,
                    source_references=["incident_summary"],
                    status="unknown",
                )
            )

        for index, raw in enumerate(data.get("evidence_items") or [], start=1):
            if not isinstance(raw, dict):
                continue
            source_type = str(raw.get("source_type") or "")
            is_synthetic_narrative = raw.get("intake_derived") and (
                str(raw.get("title") or "").strip()
                == "Analyst-provided incident narrative"
            )
            if is_synthetic_narrative:
                continue
            target = (
                current
                if source_type in {"analyst_input", "user_input", "log", "document"}
                else historical
            )
            mapped_source = source_type if target is current else "legacy_unverified"
            target["evidence"].append(
                self._item(
                    item_id=str(raw.get("evidence_id") or f"LEGACY-E-{index:03d}"),
                    title=str(raw.get("title") or "Analyst evidence"),
                    description=str(raw.get("description") or ""),
                    source_type=mapped_source,
                    case_version=case.case_version if target is current else 0,
                    source_references=[str(raw.get("evidence_id") or "")],
                    status=str(raw.get("status") or "unknown"),
                    details=raw,
                )
            )

    def _add_deterministic_candidates(
        self,
        case: CaseRecord,
        current: dict[str, list[CaseOutputItem]],
        historical: dict[str, list[CaseOutputItem]],
        *,
        show_current: bool,
    ) -> None:
        for index, raw in enumerate((case.data or {}).get("attack_mappings") or [], start=1):
            if not isinstance(raw, dict):
                continue
            metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
            is_candidate = (
                metadata.get("source_type") == "system_rule"
                and metadata.get("status", "candidate") == "candidate"
                and not metadata.get("analyst_verified", False)
            )
            target = current if is_candidate and show_current else historical
            target["attack_mappings"].append(
                self._item(
                    item_id=str(raw.get("mapping_id") or f"LEGACY-MAP-{index:03d}"),
                    title=str(raw.get("technique_name") or raw.get("technique_id") or "ATT&CK mapping"),
                    description=str(raw.get("rationale") or ""),
                    source_type="system_rule" if is_candidate else "legacy_unverified",
                    case_version=case.case_version if is_candidate else 0,
                    source_references=[str(item) for item in metadata.get("evidence_ids") or []],
                    status="candidate" if is_candidate else str(metadata.get("status") or "unknown"),
                    details=raw,
                )
            )

    def _add_legacy_history(
        self,
        case: CaseRecord,
        historical: dict[str, list[CaseOutputItem]],
    ) -> None:
        data = case.data or {}
        for index, raw in enumerate(data.get("gaps") or [], start=1):
            text = str(raw).strip()
            if text:
                historical["gaps"].append(
                    self._item(
                        item_id=f"LEGACY-GAP-{index:03d}",
                        title=text,
                        description=text,
                        source_type="legacy_unverified",
                        case_version=0,
                        status="unknown",
                    )
                )
        for index, raw in enumerate(data.get("recommendations") or [], start=1):
            if isinstance(raw, dict):
                title = str(raw.get("title") or "Legacy recommendation")
                description = str(raw.get("description") or "")
                item_id = str(raw.get("action_id") or f"LEGACY-REC-{index:03d}")
                details = raw
            else:
                title = description = str(raw).strip()
                item_id = f"LEGACY-REC-{index:03d}"
                details = {}
            if title:
                historical["recommendations"].append(
                    self._item(
                        item_id=item_id,
                        title=title,
                        description=description,
                        source_type="legacy_unverified",
                        case_version=0,
                        status="unknown",
                        details=details,
                    )
                )

    @staticmethod
    def _outputs_have_valid_provenance(case: CaseRecord, turn: CaseChatTurn) -> bool:
        return bool(
            turn.case_id == case.case_id
            and turn.case_version == case.case_version
            and turn.case_snapshot_hash == case.case_snapshot_hash
            and CaseOutputSummaryService._outputs_match_turn_provenance(turn)
        )

    @staticmethod
    def _outputs_match_turn_provenance(turn: CaseChatTurn) -> bool:
        payload = turn.analysis_outputs_json or {}
        if not payload:
            return True
        if any(
            (
                payload.get("analysis_run_id") != turn.turn_id,
                payload.get("case_id") != turn.case_id,
                payload.get("case_version") != turn.case_version,
                payload.get("case_snapshot_hash") != turn.case_snapshot_hash,
                payload.get("retrieval_context_id") != turn.retrieval_context_id,
            )
        ):
            return False
        for key in _OUTPUT_KEYS:
            items = payload.get(key, [])
            if not isinstance(items, list):
                return False
            for item in items:
                if not isinstance(item, dict) or any(
                    (
                        item.get("source_type") != "rag",
                        item.get("analysis_run_id") != turn.turn_id,
                        item.get("case_id") != turn.case_id,
                        item.get("case_version") != turn.case_version,
                        item.get("case_snapshot_hash") != turn.case_snapshot_hash,
                    )
                ):
                    return False
        return True

    def _add_turn_outputs(
        self,
        turn: CaseChatTurn,
        target: dict[str, list[CaseOutputItem]],
        *,
        trusted_provenance: bool = True,
    ) -> None:
        payload = turn.analysis_outputs_json or {}
        for key in _OUTPUT_KEYS:
            for index, raw in enumerate(payload.get(key) or [], start=1):
                if not isinstance(raw, dict):
                    continue
                details = raw.get("details") if isinstance(raw.get("details"), dict) else {}
                source_type = str(raw.get("source_type") or "legacy_unverified")
                if source_type not in {
                    "rag",
                    "system_rule",
                    "analyst_input",
                    "user_input",
                    "log",
                    "document",
                    "manual_edit",
                    "legacy_unverified",
                }:
                    source_type = "legacy_unverified"
                if not trusted_provenance:
                    source_type = "legacy_unverified"
                target[key].append(
                    self._item(
                        item_id=str(raw.get("item_id") or f"{key}-{index:03d}"),
                        title=str(raw.get("title") or "Analysis output"),
                        description=str(raw.get("description") or ""),
                        source_type=source_type,
                        analysis_run_id=(
                            str(raw.get("analysis_run_id") or "") or None
                            if trusted_provenance
                            else None
                        ),
                        case_version=(
                            int(raw.get("case_version") or turn.case_version)
                            if trusted_provenance
                            else 0
                        ),
                        generated_at=raw.get("generated_at") if trusted_provenance else None,
                        source_references=(
                            [str(item) for item in raw.get("source_references") or []]
                            if trusted_provenance
                            else []
                        ),
                        review_status=(
                            str(raw.get("review_status") or "unreviewed")
                            if trusted_provenance
                            else "unreviewed"
                        ),
                        status=(
                            str(raw.get("status") or "unknown")
                            if trusted_provenance
                            else "unknown"
                        ),
                        details=details,
                    )
                )


__all__ = ["CaseOutputSummaryService"]
