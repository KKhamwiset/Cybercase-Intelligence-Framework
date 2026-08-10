"""Server-owned report snapshots, persistence, and chat-scoped report routes."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.chat import ChatMessage, ChatThread
from app.models.report import ChatReport
from app.schemas.chat import ChatReportCreate, ChatReportRead, MitreTableRow
from app.schemas.chat.reports import StructuredReport
from app.services.extraction.llm_extraction import (
    ACCEPTED_BASELINE_EXTRACTION_PROMPT_VERSIONS,
    BASELINE_EXTRACTION_VERSION,
    EXTRACTION_METADATA_KEY,
    BaselineExtraction,
    ExtractionInput,
    build_extraction_input,
    validate_baseline_extraction,
)
from app.services.reports.report_generation import (
    ReportGenerationError,
    generate_report_payload,
    MITRE_ID_RE,
    AdmittedMitreRow,
    ReportInputSnapshot,
    ReportModelAdapter,
    ReportSourceMessage,
    ReportRunResult,
    run_report_generation,
    source_snapshot_hash,
    validate_structured_report,
)
from app.services.reports.report_pdf import render_chat_report_pdf


_EXTRACTION_FIELDS = (
    "version",
    "mode",
    "status",
    "case_summary",
    "entities",
    "relationships",
    "evidence",
    "timeline",
    "missing_information",
    "warnings",
)


class ReportServiceError(Exception):
    """Safe, user-actionable report service failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ReportGenerationConflict(ReportServiceError):
    """The selected thread cannot produce a report at this time."""


class ReportNotFound(ReportServiceError):
    """The requested thread or report does not exist."""


def build_current_report_snapshot(thread: ChatThread) -> ReportInputSnapshot:
    """Build the only report input admitted by the current chat state.

    The server derives provenance from persisted rows. Assistant content is used
    only to find the terminal answer and its structured metadata; it is never
    copied into the report model input.
    """

    ordered_messages = sorted(thread.messages, key=lambda message: message.ordinal)
    if not ordered_messages:
        raise ReportGenerationConflict(
            "report_empty_thread",
            "Send and complete a chat message before generating a report.",
        )

    if thread.status != "idle":
        code_by_status = {
            "processing": "report_chat_processing",
            "awaiting_followup": "report_followup_pending",
            "failed": "report_chat_failed",
        }
        raise ReportGenerationConflict(
            code_by_status.get(thread.status, "report_thread_not_ready"),
            {
                "processing": "Wait for the chat response to finish before generating a report.",
                "awaiting_followup": "Answer the pending clarification before generating a report.",
                "failed": "Resolve the failed chat response before generating a report.",
            }.get(thread.status, "The chat is not ready for report generation."),
        )

    latest_assistant = next(
        (
            message
            for message in reversed(ordered_messages)
            if message.role == "assistant"
        ),
        None,
    )
    if latest_assistant is None or not _is_terminal_assistant(latest_assistant):
        raise ReportGenerationConflict(
            "report_terminal_answer_missing",
            "Complete a terminal assistant answer before generating a report.",
        )

    metadata = _metadata_dict(latest_assistant.metadata_json)
    extraction_metadata = metadata.get(EXTRACTION_METADATA_KEY)
    if not isinstance(extraction_metadata, dict):
        raise ReportGenerationConflict(
            "report_extraction_missing",
            "A validated baseline extraction is required before generating a report.",
        )
    if (
        extraction_metadata.get("version") != BASELINE_EXTRACTION_VERSION
        or extraction_metadata.get("mode") != "single_pass_llm"
        or extraction_metadata.get("prompt_version")
        not in ACCEPTED_BASELINE_EXTRACTION_PROMPT_VERSIONS
        or extraction_metadata.get("status") != "candidate"
        or extraction_metadata.get("validation_status") != "validated"
    ):
        raise ReportGenerationConflict(
            "report_extraction_not_validated",
            "The latest baseline extraction is missing or failed validation.",
        )

    source_ids = _source_message_ids(extraction_metadata)
    messages_by_id = {message.id: message for message in ordered_messages}
    source_messages = [messages_by_id.get(message_id) for message_id in source_ids]
    if any(message is None or message.role != "user" for message in source_messages):
        raise ReportGenerationConflict(
            "report_extraction_stale",
            "The persisted extraction no longer matches the chat messages.",
        )

    root_message = source_messages[0]
    assert root_message is not None
    try:
        extraction_input = build_extraction_input(
            thread_id=thread.id,
            messages=ordered_messages,
            root_ordinal=root_message.ordinal,
        )
    except (TypeError, ValueError) as exc:
        raise ReportGenerationConflict(
            "report_extraction_stale",
            "The persisted extraction no longer matches the chat messages.",
        ) from exc

    expected_source_ids = [message.message_id for message in extraction_input.messages]
    if expected_source_ids != source_ids:
        raise ReportGenerationConflict(
            "report_extraction_stale",
            "The latest extraction does not cover the current case messages.",
        )

    try:
        extraction = BaselineExtraction.model_validate(
            {
                field_name: extraction_metadata[field_name]
                for field_name in _EXTRACTION_FIELDS
                if field_name in extraction_metadata
            }
        )
        validate_baseline_extraction(extraction, extraction_input)
    except Exception as exc:
        raise ReportGenerationConflict(
            "report_extraction_not_validated",
            "The latest baseline extraction is missing or failed validation.",
        ) from exc

    report_source_messages = [
        ReportSourceMessage(
            message_id=message.message_id,
            ordinal=message.ordinal,
            source_type=message.source_type,
            content=message.content,
        )
        for message in extraction_input.messages
    ]
    mitre_rows = _admitted_mitre_rows(metadata.get("mitre_table"))
    if len(mitre_rows) > 64:
        raise ReportGenerationConflict(
            "report_mitre_rows_too_many",
            "The persisted MITRE mapping contains too many rows for one report.",
        )

    extraction_id = latest_assistant.id
    return ReportInputSnapshot(
        thread_id=thread.id,
        thread_title=thread.title or "New chat",
        extraction_id=extraction_id,
        extraction_version=BASELINE_EXTRACTION_VERSION,
        source_messages=report_source_messages,
        extraction=extraction,
        mitre_rows=mitre_rows,
        metadata={
            "extraction_prompt_version": extraction_metadata.get("prompt_version"),
            "extraction_provider": extraction_metadata.get("provider"),
            "extraction_model": extraction_metadata.get("model"),
            "source_message_ids": [str(message_id) for message_id in source_ids],
            "mitre_source_message_id": str(extraction_id),
        },
    )


class ChatReportService:
    """Persist immutable report attempts scoped to one chat thread."""

    def __init__(
        self,
        db: AsyncSession,
        *,
        adapter: ReportModelAdapter | None = None,
    ) -> None:
        self.db = db
        self.adapter = adapter

    async def generate_report(
        self,
        thread_id: UUID,
        request: ChatReportCreate,
    ) -> ChatReportRead:
        if not settings.chat_report_enabled:
            raise ReportGenerationConflict(
                "report_generation_disabled",
                "Report generation is disabled by the backend configuration.",
            )

        async with self.db.begin():
            thread_result = await self.db.execute(
                select(ChatThread)
                .options(selectinload(ChatThread.messages))
                .where(ChatThread.id == thread_id)
                .with_for_update()
            )
            thread = thread_result.scalar_one_or_none()
            if thread is None:
                raise ReportNotFound("chat_thread_not_found", "Chat thread not found")

            snapshot = build_current_report_snapshot(thread)
            snapshot_hash = source_snapshot_hash(snapshot)
            idempotency_key = request.idempotency_key or snapshot_hash

            existing_result = await self.db.execute(
                select(ChatReport)
                .where(
                    ChatReport.thread_id == thread_id,
                    ChatReport.idempotency_key == idempotency_key,
                )
                .with_for_update()
            )
            existing = existing_result.scalar_one_or_none()
            if existing is not None:
                if existing.source_snapshot_hash != snapshot_hash:
                    raise ReportGenerationConflict(
                        "report_idempotency_conflict",
                        "The idempotency key is already associated with another report snapshot.",
                    )
                return serialize_chat_report(existing)

            version_result = await self.db.execute(
                select(func.max(ChatReport.version_number)).where(
                    ChatReport.thread_id == thread_id
                )
            )
            latest_version = version_result.scalar_one() or 0
            run_result = await run_report_generation(
                snapshot,
                adapter=self.adapter,
            )
            now = datetime.now(timezone.utc)
            report = ChatReport(
                thread_id=thread_id,
                version_number=latest_version + 1,
                idempotency_key=idempotency_key,
                source_snapshot_json=snapshot.model_dump(mode="json"),
                source_snapshot_hash=snapshot_hash,
                extraction_message_id=snapshot.extraction_id,
                extraction_version=snapshot.extraction_version,
                prompt_version=run_result.prompt_version,
                provider=run_result.provider,
                model=run_result.model,
                decoding_settings={
                    "temperature": settings.chat_report_temperature,
                    "max_output_tokens": settings.chat_report_max_output_tokens,
                },
                status=run_result.status,
                validation_status=(
                    "validated" if run_result.status == "completed" else "failed"
                ),
                validation_errors_json=list(run_result.validation_errors),
                structured_report=(
                    run_result.report.model_dump(mode="json")
                    if run_result.report is not None
                    else None
                ),
                failure_code=run_result.failure_code,
                failure_message=run_result.failure_message,
                finished_at=now,
                latency_ms=run_result.latency_ms,
                input_tokens=run_result.input_tokens,
                output_tokens=run_result.output_tokens,
            )
            self.db.add(report)
            await self.db.flush()
            await self.db.refresh(report)
            return serialize_chat_report(report)

    async def list_reports(self, thread_id: UUID) -> list[ChatReportRead]:
        await self._ensure_thread(thread_id)
        result = await self.db.execute(
            select(ChatReport)
            .where(ChatReport.thread_id == thread_id)
            .order_by(ChatReport.version_number.desc(), ChatReport.created_at.desc())
        )
        return [serialize_chat_report(report) for report in result.scalars().all()]

    async def get_report(
        self,
        thread_id: UUID,
        report_id: UUID,
    ) -> ChatReportRead:
        result = await self.db.execute(
            select(ChatReport).where(
                ChatReport.thread_id == thread_id,
                ChatReport.id == report_id,
            )
        )
        report = result.scalar_one_or_none()
        if report is None:
            raise ReportNotFound("chat_report_not_found", "Chat report not found")
        return serialize_chat_report(report)

    async def get_report_pdf(
        self,
        thread_id: UUID,
        report_id: UUID,
    ) -> tuple[bytes, str]:
        result = await self.db.execute(
            select(ChatReport)
            .options(selectinload(ChatReport.thread))
            .where(
                ChatReport.thread_id == thread_id,
                ChatReport.id == report_id,
            )
        )
        report = result.scalar_one_or_none()
        if report is None:
            raise ReportNotFound("chat_report_not_found", "Chat report not found")
        if (
            report.status != "completed"
            or report.validation_status != "validated"
            or not isinstance(report.structured_report, dict)
        ):
            raise ReportGenerationConflict(
                "report_pdf_requires_validated_report",
                "Only a completed and validated report can be exported as a PDF.",
            )

        try:
            snapshot = ReportInputSnapshot.model_validate(report.source_snapshot_json)
            structured_report = StructuredReport.model_validate(report.structured_report)
            evidence_ids = {item.evidence_id for item in snapshot.extraction.evidence}
            timeline_ids = {item.event_id for item in snapshot.extraction.timeline}
            validate_structured_report(
                structured_report,
                incident_ids=evidence_ids | timeline_ids,
                mitre_ids={row.technique_id for row in snapshot.mitre_rows},
                evidence_ids=evidence_ids,
                timeline_ids=timeline_ids,
            )
        except Exception as exc:
            raise ReportGenerationConflict(
                "report_pdf_requires_validated_report",
                "The persisted report failed validation and cannot be exported as a PDF.",
            ) from exc

        serialized = serialize_chat_report(report)
        if serialized.report is None:
            raise ReportGenerationConflict(
                "report_pdf_requires_validated_report",
                "Only a completed and validated report can be exported as a PDF.",
            )
        thread_title = getattr(report.thread, "title", None) or "New chat"
        content = await asyncio.to_thread(
            render_chat_report_pdf,
            serialized,
            thread_title=thread_title,
        )
        filename = f"cybercase-report-v{report.version_number}-{report.id}.pdf"
        return content, filename

    async def _ensure_thread(self, thread_id: UUID) -> None:
        result = await self.db.execute(
            select(ChatThread.id).where(ChatThread.id == thread_id)
        )
        if result.scalar_one_or_none() is None:
            raise ReportNotFound("chat_thread_not_found", "Chat thread not found")


def serialize_chat_report(report: ChatReport) -> ChatReportRead:
    structured_report: StructuredReport | None = None
    if isinstance(report.structured_report, dict):
        structured_report = StructuredReport.model_validate(report.structured_report)
    validation_errors = report.validation_errors_json
    if not isinstance(validation_errors, list):
        validation_errors = []
    return ChatReportRead(
        report_id=report.id,
        thread_id=report.thread_id,
        version_number=report.version_number,
        idempotency_key=report.idempotency_key,
        source_snapshot_hash=report.source_snapshot_hash,
        extraction_id=report.extraction_message_id,
        extraction_version=report.extraction_version,
        prompt_version=report.prompt_version,
        provider=report.provider,
        model=report.model,
        decoding_settings=dict(report.decoding_settings or {}),
        persistence_status=report.status,
        validation_status=report.validation_status,
        report=structured_report,
        validation_errors=[str(error) for error in validation_errors],
        failure_code=report.failure_code,
        failure_message=report.failure_message,
        created_at=report.created_at,
        finished_at=report.finished_at,
        latency_ms=report.latency_ms,
        input_tokens=report.input_tokens,
        output_tokens=report.output_tokens,
    )


def _is_terminal_assistant(message: ChatMessage) -> bool:
    if message.role != "assistant":
        return False
    if message.retrieval_context_id is not None:
        return True
    return "mitre_table" in _metadata_dict(message.metadata_json)


def _metadata_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _source_message_ids(metadata: dict[str, Any]) -> list[UUID]:
    raw_ids = metadata.get("source_message_ids")
    if not isinstance(raw_ids, list) or not raw_ids:
        raise ReportGenerationConflict(
            "report_extraction_stale",
            "The persisted extraction has no valid source messages.",
        )
    source_ids: list[UUID] = []
    for raw_id in raw_ids:
        try:
            source_ids.append(UUID(str(raw_id)))
        except (TypeError, ValueError) as exc:
            raise ReportGenerationConflict(
                "report_extraction_stale",
                "The persisted extraction has invalid source message IDs.",
            ) from exc
    if len(set(source_ids)) != len(source_ids):
        raise ReportGenerationConflict(
            "report_extraction_stale",
            "The persisted extraction has duplicate source message IDs.",
        )
    return source_ids


def _admitted_mitre_rows(value: object) -> list[AdmittedMitreRow]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ReportGenerationConflict(
            "report_mitre_metadata_invalid",
            "The persisted MITRE mapping is invalid.",
        )

    rows: list[AdmittedMitreRow] = []
    seen_ids: set[str] = set()
    for raw_row in value:
        try:
            row = MitreTableRow.model_validate(raw_row)
        except Exception:
            continue
        if not MITRE_ID_RE.fullmatch(row.technique_id):
            continue
        if row.technique_id in seen_ids:
            continue
        try:
            admitted = AdmittedMitreRow.model_validate(row.model_dump(mode="json"))
        except Exception:
            continue
        rows.append(admitted)
        seen_ids.add(admitted.technique_id)
    return rows


ReportService = ChatReportService


__all__ = [
    "ChatReportService",
    "ReportService",
    "ReportGenerationConflict",
    "ReportNotFound",
    "ReportServiceError",
    "build_current_report_snapshot",
    "serialize_chat_report",
]
