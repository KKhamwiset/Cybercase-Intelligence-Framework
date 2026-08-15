import unittest
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from app.models.case_state import CaseStateVersion
from app.models.chat import ChatMessage, ChatRun, ChatThread
from app.models.rag_context import RagContext
from app.services.chat.chat_worker import (
    AssistantOutcome,
    ChatRunWorker,
    RagContextPayload,
)
from app.services.extraction.llm_extraction import BaselineExtraction


class _Transaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_: object) -> None:
        return None


class CaseStateVersionPersistenceTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _thread(*, current_version_id=None) -> ChatThread:
        return ChatThread(
            id=uuid4(),
            title="Incident",
            status="processing",
            active_rag_session_id=None,
            current_case_state_version_id=current_version_id,
            next_message_ordinal=2,
        )

    @staticmethod
    def _run(thread: ChatThread) -> ChatRun:
        return ChatRun(
            id=uuid4(),
            thread_id=thread.id,
            request_message_id=uuid4(),
            operation="query",
            status="running",
            input_rag_session_id=None,
            idempotency_key="case-state-v1",
            request_fingerprint="a" * 64,
            request_payload={"content": "incident"},
            attempt_count=1,
            lease_owner="worker-1",
        )

    @staticmethod
    def _validated_state() -> dict[str, object]:
        extraction = BaselineExtraction(
            version="baseline_extraction_v1",
            mode="single_pass_llm",
            status="candidate",
            case_summary="A validated incident summary.",
        )
        return extraction.model_dump(mode="json")

    @staticmethod
    def _assistant_outcome(
        *,
        validated_case_state_json: dict[str, object] | None,
        metadata_json: dict[str, object] | None = None,
        rag_context_payload: RagContextPayload | None = None,
    ) -> AssistantOutcome:
        return AssistantOutcome(
            content="Terminal answer",
            retrieval_context_id="retrieval-1",
            metadata_json=metadata_json or {"mitre_table": []},
            thread_status="idle",
            active_rag_session_id=None,
            validated_case_state_json=validated_case_state_json,
            rag_context_payload=rag_context_payload,
        )

    @staticmethod
    def _worker(thread: ChatThread, run: ChatRun) -> tuple[ChatRunWorker, Mock]:
        db = Mock()
        db.begin.return_value = _Transaction()
        db.add = Mock()
        db.flush = AsyncMock()
        worker = ChatRunWorker(db)
        worker._lock_run_thread = AsyncMock(return_value=thread)
        worker._lock_owned_running_run = AsyncMock(return_value=run)
        return worker, db

    async def test_successful_initial_extraction_creates_v1_and_points_thread(
        self,
    ) -> None:
        thread = self._thread()
        run = self._run(thread)
        worker, db = self._worker(thread, run)
        validated_state = self._validated_state()
        outcome = self._assistant_outcome(
            validated_case_state_json=validated_state,
            metadata_json={
                "chat_extraction": {
                    "status": "candidate",
                    "provider": "openrouter",
                    "raw_response": "not case state",
                }
            },
            rag_context_payload=RagContextPayload(
                retrieval_context_id="retrieval-1",
                context="bounded durable MITRE context",
                mitre_table=(
                    {
                        "technique_id": "T1059.001",
                        "name": "PowerShell",
                    },
                ),
            ),
        )

        completed = await worker.complete_run(run.id, "worker-1", outcome)

        self.assertTrue(completed)
        added = [call.args[0] for call in db.add.call_args_list]
        versions = [item for item in added if isinstance(item, CaseStateVersion)]
        contexts = [item for item in added if isinstance(item, RagContext)]
        messages = [item for item in added if isinstance(item, ChatMessage)]
        self.assertEqual(len(versions), 1)
        self.assertEqual(len(contexts), 1)
        self.assertEqual(len(messages), 1)
        version = versions[0]
        rag_context = contexts[0]
        self.assertEqual(version.thread_id, thread.id)
        self.assertEqual(version.version, 1)
        self.assertIsNone(version.parent_version_id)
        self.assertEqual(version.trigger_message_id, run.request_message_id)
        self.assertEqual(version.delta_json, {})
        self.assertEqual(version.state_json, validated_state)
        self.assertNotIn("provider", version.state_json)
        self.assertNotIn("raw_response", version.state_json)
        self.assertEqual(thread.current_case_state_version_id, version.id)
        self.assertEqual(rag_context.retrieval_context_id, "retrieval-1")
        self.assertEqual(rag_context.thread_id, thread.id)
        self.assertEqual(rag_context.case_state_version_id, version.id)
        self.assertEqual(rag_context.context, "bounded durable MITRE context")
        self.assertEqual(
            rag_context.mitre_table,
            [{"technique_id": "T1059.001", "name": "PowerShell"}],
        )
        self.assertFalse(hasattr(rag_context, "answer"))
        self.assertFalse(hasattr(rag_context, "rag_answer"))
        self.assertEqual(messages[0].metadata_json, outcome.metadata_json)
        self.assertEqual(db.flush.await_count, 2)

    async def test_failed_extraction_without_structured_state_creates_no_version(
        self,
    ) -> None:
        thread = self._thread()
        run = self._run(thread)
        worker, db = self._worker(thread, run)
        outcome = self._assistant_outcome(
            validated_case_state_json=None,
            metadata_json={
                "chat_extraction": {
                    "status": "failed",
                    "failure_code": "extraction_invalid_json",
                }
            },
        )

        completed = await worker.complete_run(run.id, "worker-1", outcome)

        self.assertTrue(completed)
        added = [call.args[0] for call in db.add.call_args_list]
        self.assertFalse(any(isinstance(item, CaseStateVersion) for item in added))
        self.assertFalse(any(isinstance(item, RagContext) for item in added))
        self.assertEqual(len([item for item in added if isinstance(item, ChatMessage)]), 1)
        self.assertIsNone(thread.current_case_state_version_id)
        self.assertEqual(db.flush.await_count, 1)

    async def test_case_state_without_rag_context_is_rejected(self) -> None:
        existing_version_id = uuid4()
        thread = self._thread(current_version_id=existing_version_id)
        run = self._run(thread)
        worker, db = self._worker(thread, run)

        with self.assertRaisesRegex(
            ValueError,
            "must persist Case State and durable RAG context together",
        ):
            await worker.complete_run(
                run.id,
                "worker-1",
                self._assistant_outcome(
                    validated_case_state_json=self._validated_state()
                ),
            )

        db.add.assert_not_called()
        self.assertEqual(thread.current_case_state_version_id, existing_version_id)
        db.flush.assert_not_awaited()

    async def test_ask_outcome_never_creates_or_moves_case_state_version(self) -> None:
        existing_version_id = uuid4()
        thread = self._thread(current_version_id=existing_version_id)
        run = self._run(thread)
        worker, db = self._worker(thread, run)
        outcome = AssistantOutcome(
            content="Reasoned answer from the persisted context",
            retrieval_context_id="retrieval-1",
            metadata_json={
                "mitre_table": [],
                "chat_action": {
                    "action": "ask",
                    "state_mutated": False,
                    "case_state_version_created": False,
                    "rag_invoked": False,
                },
            },
            thread_status="answered",
            active_rag_session_id=None,
            validated_case_state_json=None,
        )

        completed = await worker.complete_run(run.id, "worker-1", outcome)

        self.assertTrue(completed)
        added = [call.args[0] for call in db.add.call_args_list]
        self.assertFalse(any(isinstance(item, CaseStateVersion) for item in added))
        self.assertFalse(any(isinstance(item, RagContext) for item in added))
        self.assertEqual(thread.current_case_state_version_id, existing_version_id)

    async def test_replayed_completed_run_cannot_duplicate_persistence(self) -> None:
        thread = self._thread()
        run = self._run(thread)
        worker, db = self._worker(thread, run)
        worker._lock_owned_running_run = AsyncMock(return_value=None)
        outcome = self._assistant_outcome(
            validated_case_state_json=self._validated_state(),
            rag_context_payload=RagContextPayload(
                retrieval_context_id="retrieval-1",
                context="bounded durable MITRE context",
                mitre_table=(),
            ),
        )

        completed = await worker.complete_run(run.id, "worker-1", outcome)

        self.assertFalse(completed)
        db.add.assert_not_called()
        db.flush.assert_not_awaited()
        self.assertIsNone(thread.current_case_state_version_id)


if __name__ == "__main__":
    unittest.main()
