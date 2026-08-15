
import json
import unittest
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.config import settings
from app.models.chat import ChatMessage, ChatThread
from app.models.report import ChatReport
from app.schemas.chat import ChatReportCreate
from app.services.extraction.llm_extraction import (
    BASELINE_EXTRACTION_PROMPT_VERSION,
)
from app.services.reports.report_generation import (
    AdmittedMitreRow,
    ReportModelResponse,
    ReportProviderFailure,
    run_report_generation,
)
from app.services.reports.report_prompt import (
    REPORT_PROMPT_VERSION,
    REPORT_SYSTEM_PROMPT,
)
from app.services.reports.report_service import (
    ChatReportService,
    ReportGenerationConflict,
    build_current_report_snapshot,
)


class FakeReportAdapter:
    def __init__(self, response: object) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    async def complete(self, **kwargs: object) -> ReportModelResponse | str:
        self.calls.append(kwargs)
        if isinstance(self.response, ReportModelResponse):
            return self.response
        return str(self.response)


class ProviderFailureReportAdapter:
    async def complete(self, **kwargs: object) -> ReportModelResponse:
        raise ReportProviderFailure(
            "report_output_limit",
            "The report model reached the configured output-token limit",
            input_tokens=123,
            output_tokens=4096,
        )


class _ScalarList:
    def __init__(self, values: list[object]) -> None:
        self.values = values

    def all(self) -> list[object]:
        return self.values


class _Result:
    def __init__(self, value: object = None, values: list[object] | None = None) -> None:
        self.value = value
        self.values = values or ([] if value is None else [value])

    def scalar_one_or_none(self) -> object:
        return self.value

    def scalar_one(self) -> object:
        return self.value

    def scalars(self) -> _ScalarList:
        return _ScalarList(self.values)


class _Transaction:
    async def __aenter__(self) -> "_Transaction":
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> bool:
        return False


class FakeReportDb:
    """Small async-session double for report persistence/idempotency tests."""

    def __init__(self, thread: ChatThread) -> None:
        self.thread = thread
        self.reports: list[ChatReport] = []

    def begin(self) -> _Transaction:
        return _Transaction()

    async def execute(self, statement: object) -> _Result:
        entity = None
        column_descriptions = getattr(statement, "column_descriptions", ())
        if column_descriptions:
            entity = column_descriptions[0].get("entity")
        if entity is ChatThread:
            return _Result(self.thread)
        if entity is ChatReport:
            statement_text = str(statement).casefold()
            if "max(" in statement_text:
                return _Result(max((report.version_number for report in self.reports), default=None))
            return _Result(self.reports[0] if self.reports else None)
        return _Result(values=list(self.reports))

    def add(self, report: ChatReport) -> None:
        self.reports.append(report)

    async def flush(self) -> None:
        report = self.reports[-1]
        if report.id is None:
            report.id = uuid4()
        if report.created_at is None:
            report.created_at = datetime.now(timezone.utc)

    async def refresh(self, report: ChatReport) -> None:
        return None


class ChatReportTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.original_settings = {
            "core_llm_provider": settings.core_llm_provider,
            "openrouter_cybercase": settings.openrouter_cybercase,
            "chat_report_enabled": settings.chat_report_enabled,
            "chat_report_timeout_seconds": settings.chat_report_timeout_seconds,
            "chat_report_max_input_chars": settings.chat_report_max_input_chars,
            "chat_report_max_raw_response_chars": settings.chat_report_max_raw_response_chars,
        }
        settings.core_llm_provider = "openrouter"
        settings.openrouter_cybercase = "test-openrouter-key"
        settings.chat_report_enabled = True
        settings.chat_report_timeout_seconds = 1.0
        settings.chat_report_max_input_chars = 80_000
        settings.chat_report_max_raw_response_chars = 24_000

    def tearDown(self) -> None:
        for name, value in self.original_settings.items():
            setattr(settings, name, value)

    def test_v2_prompt_declares_mitre_claim_contract(self) -> None:
        self.assertEqual(REPORT_PROMPT_VERSION, "chat_report_prompt_v2")
        self.assertIn(
            "Prompt version: chat_report_prompt_v2.",
            REPORT_SYSTEM_PROMPT,
        )
        self.assertIn(
            "If a statement relies on multiple\nevidence, timeline, or MITRE "
            "references, split it into separate claims",
            REPORT_SYSTEM_PROMPT,
        )
        self.assertIn(
            "Each claim's text may mention only the scalar evidence_id,\n"
            "timeline_event_id, and mitre_technique_id carried by that claim.",
            REPORT_SYSTEM_PROMPT,
        )

    async def test_report_input_excludes_terminal_assistant_prose(self) -> None:
        thread = _report_thread()
        snapshot = build_current_report_snapshot(thread)

        serialized = json.dumps(snapshot.model_dump(mode="json"))
        self.assertNotIn("Terminal assistant prose must not enter the report", serialized)
        self.assertEqual(snapshot.source_messages[0].message_id, thread.messages[0].id)
        self.assertEqual(snapshot.mitre_rows[0].technique_id, "T1059.001")

    async def test_successful_report_is_single_pass_and_provenance_bound(self) -> None:
        thread = _report_thread()
        snapshot = build_current_report_snapshot(thread)
        adapter = FakeReportAdapter(
            ReportModelResponse(
                text=json.dumps(_report_payload()),
                input_tokens=31,
                output_tokens=42,
            )
        )

        result = await run_report_generation(snapshot, adapter=adapter)

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.provider, "openrouter")
        self.assertEqual(result.model, "qwen/qwen3.8-27b")
        self.assertIsNotNone(result.report)
        self.assertEqual(len(adapter.calls), 1)
        self.assertEqual(result.input_tokens, 31)
        self.assertEqual(result.output_tokens, 42)
        self.assertEqual(result.prompt_version, REPORT_PROMPT_VERSION)
        self.assertEqual(
            adapter.calls[0]["system_prompt"],
            REPORT_SYSTEM_PROMPT,
        )
        self.assertEqual(
            adapter.calls[0]["input_payload"]["source_messages"][0]["source_type"],
            "user_case_statement",
        )
        self.assertEqual(
            adapter.calls[0]["max_output_tokens"],
            settings.chat_report_max_output_tokens,
        )
        self.assertNotIn(
            "Terminal assistant prose must not enter the report",
            json.dumps(adapter.calls[0]["input_payload"]),
        )

    async def test_invalid_claim_reference_fails_without_repair_call(self) -> None:
        thread = _report_thread()
        snapshot = build_current_report_snapshot(thread)
        payload = _report_payload()
        payload["claims"][0]["evidence_id"] = "E-404"
        adapter = FakeReportAdapter(json.dumps(payload))

        result = await run_report_generation(snapshot, adapter=adapter)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.failure_code, "report_validation_failed")
        self.assertEqual(len(adapter.calls), 1)

    async def test_claim_prose_id_not_carried_by_branch_fails_without_retry(
        self,
    ) -> None:
        snapshot = build_current_report_snapshot(_report_thread())
        payload = _report_payload()
        payload["claims"][0]["text"] = (
            "The E-001 candidate was reported and resembles T1059.001."
        )
        adapter = FakeReportAdapter(json.dumps(payload))

        result = await run_report_generation(snapshot, adapter=adapter)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.failure_code, "report_validation_failed")
        self.assertIn(
            "claim prose contains an unreferenced MITRE ID",
            result.validation_errors,
        )
        self.assertEqual(len(adapter.calls), 1)

    async def test_missing_mitre_claim_reference_fails_without_repair_call(
        self,
    ) -> None:
        snapshot = build_current_report_snapshot(_report_thread())
        snapshot.mitre_rows.append(
            AdmittedMitreRow(
                technique_id="T1059.002",
                name="AppleScript",
                entity_type="technique",
                source="vector",
                relevance="retrieved_only",
            )
        )
        payload = _report_payload()
        payload["claims"][1]["text"] = (
            "The E-001 candidate is compatible with T1059.002 as a mapping "
            "candidate."
        )
        adapter = FakeReportAdapter(json.dumps(payload))

        result = await run_report_generation(snapshot, adapter=adapter)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.failure_code, "report_validation_failed")
        self.assertIn(
            "claim prose contains an unreferenced MITRE ID",
            result.validation_errors,
        )
        self.assertEqual(len(adapter.calls), 1)

    async def test_mirrored_mitre_claim_reference_is_accepted(self) -> None:
        snapshot = build_current_report_snapshot(_report_thread())
        adapter = FakeReportAdapter(json.dumps(_report_payload()))

        result = await run_report_generation(snapshot, adapter=adapter)

        self.assertEqual(result.status, "completed")
        self.assertEqual(len(adapter.calls), 1)
        assert result.report is not None
        self.assertEqual(
            result.report.claims[1].mitre_technique_ids,
            ["T1059.001"],
        )

    async def test_v2_prompt_leak_is_rejected(self) -> None:
        snapshot = build_current_report_snapshot(_report_thread())
        payload = _report_payload()
        payload["claims"][0]["text"] = "Prompt version: chat_report_prompt_v2."
        adapter = FakeReportAdapter(json.dumps(payload))

        result = await run_report_generation(snapshot, adapter=adapter)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.failure_code, "report_validation_failed")
        self.assertEqual(len(adapter.calls), 1)

    async def test_provider_failure_preserves_usage_metadata(self) -> None:
        snapshot = build_current_report_snapshot(_report_thread())

        result = await run_report_generation(
            snapshot,
            adapter=ProviderFailureReportAdapter(),
        )

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.failure_code, "report_output_limit")
        self.assertEqual(result.input_tokens, 123)
        self.assertEqual(result.output_tokens, 4096)

    async def test_report_service_persists_history_and_replays_same_idempotency_key(
        self,
    ) -> None:
        thread = _report_thread()
        db = FakeReportDb(thread)
        adapter = FakeReportAdapter(json.dumps(_report_payload()))
        service = ChatReportService(db, adapter=adapter)
        request = ChatReportCreate(idempotency_key="request-1")

        first = await service.generate_report(thread.id, request)
        second = await service.generate_report(thread.id, request)

        self.assertEqual(first.report_id, second.report_id)
        self.assertEqual(first.version_number, 1)
        self.assertEqual(second.version_number, 1)
        self.assertEqual(
            first.decoding_settings["max_output_tokens"],
            settings.chat_report_max_output_tokens,
        )
        self.assertEqual(len(db.reports), 1)
        self.assertEqual(len(adapter.calls), 1)

    async def test_validated_report_can_be_exported_as_pdf(self) -> None:
        thread = _report_thread()
        db = FakeReportDb(thread)
        service = ChatReportService(
            db,
            adapter=FakeReportAdapter(json.dumps(_report_payload())),
        )
        report = await service.generate_report(
            thread.id,
            ChatReportCreate(idempotency_key="pdf-request"),
        )

        content, filename = await service.get_report_pdf(thread.id, report.report_id)

        self.assertTrue(content.startswith(b"%PDF-"))
        self.assertEqual(filename, f"cybercase-report-v1-{report.report_id}.pdf")

    async def test_pdf_export_rejects_tampered_structured_report(self) -> None:
        thread = _report_thread()
        db = FakeReportDb(thread)
        service = ChatReportService(
            db,
            adapter=FakeReportAdapter(json.dumps(_report_payload())),
        )
        report = await service.generate_report(
            thread.id,
            ChatReportCreate(idempotency_key="tampered-pdf-request"),
        )
        assert db.reports[0].structured_report is not None
        db.reports[0].structured_report["claims"][0]["evidence_ids"] = ["E-404"]

        with self.assertRaises(ReportGenerationConflict) as context:
            await service.get_report_pdf(thread.id, report.report_id)

        self.assertEqual(context.exception.code, "report_pdf_requires_validated_report")

    def test_stale_or_failed_extraction_is_rejected(self) -> None:
        thread = _report_thread()
        terminal = thread.messages[-1]
        assert isinstance(terminal.metadata_json, dict)
        extraction = terminal.metadata_json["chat_extraction"]
        assert isinstance(extraction, dict)
        extraction["validation_status"] = "failed"

        with self.assertRaises(ReportGenerationConflict) as context:
            build_current_report_snapshot(thread)

        self.assertEqual(context.exception.code, "report_extraction_not_validated")


def _report_thread() -> ChatThread:
    thread_id = uuid4()
    root = ChatMessage(
        id=uuid4(),
        thread_id=thread_id,
        ordinal=1,
        role="user",
        content="A reported PowerShell event occurred on host-7.",
        metadata_json={},
    )
    terminal = ChatMessage(
        id=uuid4(),
        thread_id=thread_id,
        ordinal=2,
        role="assistant",
        content="Terminal assistant prose must not enter the report.",
        retrieval_context_id="context-1",
        metadata_json={
            "mitre_table": [
                {
                    "technique_id": "T1059.001",
                    "name": "PowerShell",
                    "entity_type": "technique",
                    "tactic": "Execution",
                    "score": 0.9,
                    "source": "vector",
                    "relevance": "cited_in_answer",
                    "description": "PowerShell execution mapping.",
                    "mitre_url": "https://attack.mitre.org/techniques/T1059/001/",
                },
                {"technique_id": "not-a-mitre-id", "name": "Ignore me"},
            ],
            "chat_extraction": {
                "version": "baseline_extraction_v1",
                "mode": "single_pass_llm",
                "status": "candidate",
                "case_summary": "A reported PowerShell event occurred.",
                "entities": [],
                "evidence": [
                    {
                        "evidence_id": "E-001",
                        "title": "PowerShell event",
                        "description": "A PowerShell event was reported.",
                        "artifact_type": "command_line",
                        "status": "reported",
                        "confidence": "medium",
                        "source_type": "user_reported",
                        "source_message_ids": [str(root.id)],
                    }
                ],
                "timeline": [
                    {
                        "event_id": "T-001",
                        "timestamp": None,
                        "timestamp_text": "Time unknown",
                        "event": "The event was reported.",
                        "actors": [],
                        "evidence_ids": ["E-001"],
                        "status": "unknown",
                        "confidence": "unknown",
                        "source_message_ids": [str(root.id)],
                    }
                ],
                "missing_information": [],
                "warnings": [],
                "prompt_version": BASELINE_EXTRACTION_PROMPT_VERSION,
                "provider": "anthropic",
                "model": "claude-haiku-4-5-20251001",
                "validation_status": "validated",
                "source_message_ids": [str(root.id)],
                "raw_response": None,
            },
        },
    )
    thread = ChatThread(
        id=thread_id,
        title="PowerShell investigation",
        status="idle",
        next_message_ordinal=3,
    )
    thread.messages = [root, terminal]
    return thread


def _report_payload() -> dict[str, object]:
    section_ids = (
        "executive_summary",
        "case_background_scope",
        "evidence_findings",
        "individuals_accounts_systems_roles",
        "chronological_timeline",
        "technical_analysis_mitre",
        "conclusions_limitations_next_steps",
    )
    headings = (
        "Executive Summary",
        "Case Background and Scope",
        "Evidence Findings",
        "Individuals, Accounts, Systems, and Reported Roles",
        "Chronological Timeline",
        "Technical Analysis and MITRE ATT&CK Mapping",
        "Conclusions, Limitations, and Recommended Next Investigative Steps",
    )
    return {
        "report_version": "baseline_report_v1",
        "status": "provisional_unverified",
        "title": "Provisional report",
        "sections": [
            {
                "section_id": section_id,
                "heading": heading,
                "paragraphs": ["The report is provisional and unverified."],
                "items": [],
            }
            for section_id, heading in zip(section_ids, headings)
        ],
        "claims": [
            {
                "claim_id": "C-001",
                "section_id": "evidence_findings",
                "text": "The E-001 candidate was reported by the user.",
                "claim_kind": "incident_evidence",
                "support_type": "user_reported",
                "evidence_id": "E-001",
            },
            {
                "claim_id": "C-002",
                "section_id": "technical_analysis_mitre",
                "text": "The E-001 candidate is compatible with T1059.001 as a mapping candidate.",
                "claim_kind": "mitre_evidence",
                "support_type": "mitre_mapping_candidate",
                "evidence_id": "E-001",
                "mitre_technique_id": "T1059.001",
            },
        ],
        "limitations": ["The candidates require forensic verification."],
    }


if __name__ == "__main__":
    unittest.main()
