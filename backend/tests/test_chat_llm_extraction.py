import asyncio
import json
import unittest
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from app.config import settings
from app.schemas.chat.rag import QueryResponse
from app.services.chat.chat_worker import (
    AssistantOutcome,
    ClaimedChatRun,
    attach_llm_extraction,
    process_chat_run,
)
from app.services.chat.followup_policy import FollowUpDecision
from app.services.chat.llm_extraction import (
    BaselineExtraction,
    ExtractionInput,
    ExtractionModelResponse,
    ExtractionSourceMessage,
    ExtractionValidationError,
    build_extraction_input,
    run_baseline_extraction,
    validate_baseline_extraction,
)
from app.models.chat import ChatMessage


class FakeExtractionAdapter:
    def __init__(
        self,
        response: object,
        *,
        delay_seconds: float = 0.0,
    ) -> None:
        self.response = response
        self.delay_seconds = delay_seconds
        self.calls: list[dict[str, object]] = []

    async def complete(
        self,
        *,
        system_prompt: str,
        input_payload: dict[str, object],
        model: str,
        max_output_tokens: int,
    ) -> ExtractionModelResponse | str:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "input_payload": input_payload,
                "model": model,
                "max_output_tokens": max_output_tokens,
            }
        )
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        if isinstance(self.response, ExtractionModelResponse):
            return self.response
        return str(self.response)


class AnswerPolicy:
    async def decide(self, **_: object) -> FollowUpDecision:
        return FollowUpDecision(
            action="proceed",
            question="",
            reason_code="sufficient_case_context",
        )


class SessionContext:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None


class ChatLlmExtractionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.original_settings = {
            "chat_extraction_enabled": settings.chat_extraction_enabled,
            "chat_extraction_timeout_seconds": settings.chat_extraction_timeout_seconds,
            "chat_extraction_max_input_chars": settings.chat_extraction_max_input_chars,
        }
        settings.chat_extraction_enabled = True
        settings.chat_extraction_timeout_seconds = 1.0
        settings.chat_extraction_max_input_chars = 20_000

    def tearDown(self) -> None:
        for name, value in self.original_settings.items():
            setattr(settings, name, value)

    @staticmethod
    def _input() -> ExtractionInput:
        return ExtractionInput(
            thread_id=uuid4(),
            messages=[
                ExtractionSourceMessage(
                    message_id=uuid4(),
                    ordinal=1,
                    source_type="user_case_statement",
                    content="A phishing email led to a suspicious Microsoft 365 sign-in.",
                ),
                ExtractionSourceMessage(
                    message_id=uuid4(),
                    ordinal=3,
                    source_type="clarification_answer",
                    content="The sign-in was reported from an unexpected location at 10:20.",
                ),
            ],
        )

    @staticmethod
    def _success_payload(extraction_input: ExtractionInput) -> dict[str, object]:
        root_id = str(extraction_input.messages[0].message_id)
        answer_id = str(extraction_input.messages[1].message_id)
        return {
            "version": "baseline_extraction_v1",
            "mode": "single_pass_llm",
            "status": "candidate",
            "case_summary": "A phishing email and suspicious sign-in were reported.",
            "entities": [
                {
                    "entity_id": "ENT-001",
                    "name": "Microsoft 365 account",
                    "entity_type": "account",
                    "reported_role": "compromised account",
                    "confidence": "high",
                    "source_message_ids": [root_id],
                }
            ],
            "evidence": [
                {
                    "evidence_id": "E-001",
                    "title": "Suspicious sign-in record",
                    "description": "A sign-in from an unexpected location was reported.",
                    "artifact_type": "identity_log",
                    "status": "reported",
                    "confidence": "medium",
                    "source_type": "user_reported",
                    "source_message_ids": [answer_id],
                }
            ],
            "timeline": [
                {
                    "event_id": "T-001",
                    "timestamp": "2026-07-18T10:20:00",
                    "timestamp_text": "18 July 2026 at approximately 10:20",
                    "event": "The suspicious sign-in was reported.",
                    "actors": ["employee"],
                    "evidence_ids": ["E-001"],
                    "status": "reported",
                    "confidence": "high",
                    "source_message_ids": [answer_id],
                }
            ],
            "missing_information": [],
            "warnings": [],
        }

    async def test_successful_phishing_extraction_is_typed_and_provenance_bound(
        self,
    ) -> None:
        extraction_input = self._input()
        adapter = FakeExtractionAdapter(
            ExtractionModelResponse(
                text=json.dumps(self._success_payload(extraction_input)),
                input_tokens=31,
                output_tokens=42,
            )
        )

        result = await run_baseline_extraction(extraction_input, adapter=adapter)

        self.assertEqual(result.status, "candidate")
        self.assertIsInstance(result.extraction, BaselineExtraction)
        assert result.extraction is not None
        self.assertEqual(result.extraction.evidence[0].evidence_id, "E-001")
        self.assertEqual(result.input_tokens, 31)
        self.assertEqual(result.output_tokens, 42)
        json.dumps(result.metadata(extraction_input))
        self.assertEqual(len(adapter.calls), 1)
        source_messages = adapter.calls[0]["input_payload"]["messages"]
        self.assertEqual(
            [item["source_type"] for item in source_messages],
            ["user_case_statement", "clarification_answer"],
        )

    async def test_explicit_unknown_facts_remain_unknown(self) -> None:
        extraction_input = self._input()
        payload = self._success_payload(extraction_input)
        payload["timeline"] = [
            {
                "event_id": "T-001",
                "timestamp": None,
                "timestamp_text": "The exact time is unknown.",
                "event": "A suspicious sign-in was reported.",
                "actors": [],
                "evidence_ids": [],
                "status": "unknown",
                "confidence": "unknown",
                "source_message_ids": [
                    str(extraction_input.messages[0].message_id)
                ],
            }
        ]
        payload["missing_information"] = [
            {
                "missing_id": "M-001",
                "description": "Whether email messages were downloaded is unknown.",
                "importance": "material",
                "source_message_ids": [
                    str(extraction_input.messages[0].message_id)
                ],
            }
        ]

        result = await run_baseline_extraction(
            extraction_input,
            adapter=FakeExtractionAdapter(json.dumps(payload)),
        )

        self.assertEqual(result.status, "candidate")
        assert result.extraction is not None
        self.assertIsNone(result.extraction.timeline[0].timestamp)
        self.assertEqual(result.extraction.timeline[0].status, "unknown")
        self.assertIn("unknown", result.extraction.missing_information[0].description)

    def test_assistant_and_rag_content_are_excluded_from_input(self) -> None:
        thread_id = uuid4()
        root = ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            ordinal=1,
            role="user",
            content="Investigate the reported phishing event.",
            metadata_json={},
        )
        question = ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            ordinal=2,
            role="assistant",
            content="Which host was affected?",
            metadata_json={"chat_followup": {"kind": "clarification"}},
        )
        answer = ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            ordinal=3,
            role="user",
            content="host-7",
            metadata_json={},
        )
        rag_answer = ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            ordinal=4,
            role="assistant",
            content="MITRE says this is T1566.",
            retrieval_context_id="retrieval-1",
            metadata_json={"mitre_table": []},
        )

        packet = build_extraction_input(
            thread_id=thread_id,
            messages=[root, question, answer, rag_answer],
            root_ordinal=1,
        )

        self.assertEqual(
            [message.message_id for message in packet.messages],
            [root.id, answer.id],
        )
        self.assertNotIn(question.content, json.dumps(packet.model_dump(mode="json")))
        self.assertNotIn(rag_answer.content, json.dumps(packet.model_dump(mode="json")))

    def test_invalid_source_message_reference_is_rejected(self) -> None:
        extraction_input = self._input()
        payload = self._success_payload(extraction_input)
        payload["entities"][0]["source_message_ids"] = [str(uuid4())]

        with self.assertRaises(ExtractionValidationError):
            validate_baseline_extraction(payload, extraction_input)

    def test_invalid_evidence_reference_is_rejected(self) -> None:
        extraction_input = self._input()
        payload = self._success_payload(extraction_input)
        payload["timeline"][0]["evidence_ids"] = ["E-404"]

        with self.assertRaises(ExtractionValidationError):
            validate_baseline_extraction(payload, extraction_input)

    async def test_malformed_model_json_is_an_explicit_failure(self) -> None:
        result = await run_baseline_extraction(
            self._input(),
            adapter=FakeExtractionAdapter("not json"),
        )

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.failure_code, "extraction_invalid_json")
        self.assertIsNone(result.extraction)

    async def test_timeout_is_an_explicit_failure(self) -> None:
        settings.chat_extraction_timeout_seconds = 0.01
        result = await run_baseline_extraction(
            self._input(),
            adapter=FakeExtractionAdapter("{}", delay_seconds=0.05),
        )

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.failure_code, "extraction_timeout")

    async def test_terminal_answer_persists_extraction_metadata_and_followup_does_not_call(
        self,
    ) -> None:
        extraction_input = self._input()
        adapter = FakeExtractionAdapter(
            json.dumps(self._success_payload(extraction_input))
        )
        claimed = ClaimedChatRun(
            id=uuid4(),
            operation="query",
            input_rag_session_id=None,
            content="incident",
            rag_query="incident",
            original_user_content="incident",
            clarification_exchanges=(),
            followup_root_ordinal=1,
            extraction_input=extraction_input,
        )
        terminal = AssistantOutcome(
            content="The terminal answer.",
            retrieval_context_id="retrieval-1",
            metadata_json={"mitre_table": []},
            thread_status="idle",
            active_rag_session_id=None,
        )
        awaiting = AssistantOutcome(
            content="Which host was affected?",
            retrieval_context_id=None,
            metadata_json={"chat_followup": {"kind": "clarification"}},
            thread_status="awaiting_followup",
            active_rag_session_id=None,
        )

        enriched = await attach_llm_extraction(terminal, claimed, adapter=adapter)
        unchanged = await attach_llm_extraction(awaiting, claimed, adapter=adapter)

        self.assertEqual(len(adapter.calls), 1)
        self.assertEqual(
            enriched.metadata_json["chat_extraction"]["status"],
            "candidate",
        )
        self.assertEqual(unchanged, awaiting)

    async def test_extraction_failure_metadata_does_not_replace_terminal_answer(
        self,
    ) -> None:
        extraction_input = self._input()
        claimed = ClaimedChatRun(
            id=uuid4(),
            operation="query",
            input_rag_session_id=None,
            content="incident",
            rag_query="incident",
            original_user_content="incident",
            clarification_exchanges=(),
            followup_root_ordinal=1,
            extraction_input=extraction_input,
        )
        terminal = AssistantOutcome(
            content="The terminal answer.",
            retrieval_context_id="retrieval-1",
            metadata_json={"mitre_table": []},
            thread_status="idle",
            active_rag_session_id=None,
        )

        enriched = await attach_llm_extraction(
            terminal,
            claimed,
            adapter=FakeExtractionAdapter("not json"),
        )

        self.assertEqual(enriched.content, terminal.content)
        self.assertEqual(
            enriched.metadata_json["chat_extraction"]["status"],
            "failed",
        )
        self.assertEqual(
            enriched.metadata_json["chat_extraction"]["failure_code"],
            "extraction_invalid_json",
        )

    async def test_process_chat_run_persists_extraction_on_terminal_rag_answer(self) -> None:
        extraction_input = self._input()
        claimed = ClaimedChatRun(
            id=uuid4(),
            operation="query",
            input_rag_session_id=None,
            content="incident",
            rag_query="incident",
            original_user_content="incident",
            clarification_exchanges=(),
            followup_root_ordinal=1,
            extraction_input=extraction_input,
        )
        worker = Mock()
        worker.claim_run = AsyncMock(return_value=claimed)
        worker.complete_run = AsyncMock(return_value=True)
        adapter = FakeExtractionAdapter(
            json.dumps(self._success_payload(extraction_input))
        )

        async def rag_call(_: str) -> QueryResponse:
            return QueryResponse(status="completed", answer="terminal answer")

        with (
            patch(
                "app.services.chat.chat_worker.async_session",
                return_value=SessionContext(),
            ),
            patch(
                "app.services.chat.chat_worker.ChatRunWorker",
                return_value=worker,
            ),
        ):
            await process_chat_run(
                claimed.id,
                policy=AnswerPolicy(),
                rag_call=rag_call,
                extraction_adapter=adapter,
            )

        persisted_outcome = worker.complete_run.await_args.args[2]
        self.assertEqual(persisted_outcome.content, "terminal answer")
        self.assertEqual(
            persisted_outcome.metadata_json["chat_extraction"]["status"],
            "candidate",
        )
        self.assertEqual(len(adapter.calls), 1)
