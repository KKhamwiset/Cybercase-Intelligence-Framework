import hashlib
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from fastapi import HTTPException

from app.config import settings
from app.models.chat import ChatMessage, ChatRun, ChatThread
from app.schemas.chat import ChatMessageCreate
from app.services.chat.chat_message import (
    ChatMessageService,
    reconstruct_clarification_chain,
)
from app.services.chat.chat_worker import ChatRunWorker


class _Transaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None


class ChatMessageFollowUpTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _message_service_db(
        thread: ChatThread,
        history: list[ChatMessage],
    ) -> Mock:
        thread_result = Mock()
        thread_result.scalar_one_or_none.return_value = thread
        no_run_result = Mock()
        no_run_result.scalar_one_or_none.return_value = None
        history_result = Mock()
        history_result.scalars.return_value.all.return_value = history

        db = Mock()
        db.begin.return_value = _Transaction()
        db.execute = AsyncMock(
            side_effect=[
                thread_result,
                no_run_result,
                no_run_result,
                history_result,
            ]
        )
        added: list[object] = []
        db.add.side_effect = added.append

        async def flush() -> None:
            for item in added:
                if isinstance(item, (ChatMessage, ChatRun)) and item.id is None:
                    item.id = uuid4()

        db.flush = AsyncMock(side_effect=flush)
        db.refresh = AsyncMock()
        return db

    @staticmethod
    def _failure_db(thread: ChatThread, run: ChatRun) -> Mock:
        thread_id_result = Mock()
        thread_id_result.scalar_one_or_none.return_value = thread.id
        thread_result = Mock()
        thread_result.scalar_one_or_none.return_value = thread
        run_result = Mock()
        run_result.scalar_one_or_none.return_value = run

        db = Mock()
        db.begin.return_value = _Transaction()
        db.execute = AsyncMock(
            side_effect=[thread_id_result, thread_result, run_result]
        )
        db.flush = AsyncMock()
        return db

    async def test_legacy_awaiting_thread_recovers_with_bounded_query(self) -> None:
        thread_id = uuid4()
        thread = ChatThread(
            id=thread_id,
            title="Saved chat",
            status="awaiting_followup",
            active_rag_session_id="legacy-session",
            next_message_ordinal=3,
        )
        original = ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            ordinal=1,
            role="user",
            content="Investigate the suspicious PowerShell event.",
            metadata_json={},
        )
        clarification = ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            ordinal=2,
            role="assistant",
            content="Which affected host produced this event?",
            metadata_json={},
        )

        db = self._message_service_db(thread, [original, clarification])

        message, run = await ChatMessageService(db).create_message_and_run(
            thread_id,
            ChatMessageCreate(
                content="host-7",
                idempotency_key="followup-key",
            ),
        )

        history_statement = db.execute.await_args_list[3].args[0]
        self.assertIn("ORDER BY chat_messages.ordinal", str(history_statement))
        self.assertEqual(run.operation, "query")
        self.assertIsNone(run.input_rag_session_id)
        self.assertIsNone(thread.active_rag_session_id)
        self.assertEqual(thread.status, "processing")
        self.assertEqual(message.ordinal, 3)
        self.assertNotIn("skip_followup_policy", run.request_payload)
        self.assertEqual(run.request_payload["followup_root_ordinal"], 1)
        self.assertEqual(run.request_payload["followup_round"], 1)
        rag_query = run.request_payload["rag_query"]
        self.assertIsInstance(rag_query, str)
        self.assertLessEqual(
            len(rag_query),
            settings.chat_followup_combined_query_max_chars,
        )
        self.assertIn(original.content, rag_query)
        self.assertIn(clarification.content, rag_query)
        self.assertIn("host-7", rag_query)

    async def test_later_query_preserves_all_ordered_clarifications(self) -> None:
        thread_id = uuid4()
        thread = ChatThread(
            id=thread_id,
            title="Saved chat",
            status="awaiting_followup",
            next_message_ordinal=5,
        )
        original = ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            ordinal=1,
            role="user",
            content="Investigate the suspicious PowerShell event.",
            metadata_json={},
        )
        question_one = ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            ordinal=2,
            role="assistant",
            content="Which affected host produced this event?",
            metadata_json={
                "chat_followup": {
                    "kind": "clarification",
                    "source_run_id": str(uuid4()),
                    "root_ordinal": 1,
                    "round": 1,
                }
            },
        )
        answer_one = ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            ordinal=3,
            role="user",
            content="host-7",
            metadata_json={},
        )
        question_two = ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            ordinal=4,
            role="assistant",
            content="When was it first observed?",
            metadata_json={
                "chat_followup": {
                    "kind": "clarification",
                    "source_run_id": str(uuid4()),
                    "root_ordinal": 1,
                    "round": 2,
                }
            },
        )
        db = self._message_service_db(
            thread,
            [original, question_one, answer_one, question_two],
        )

        _, run = await ChatMessageService(db).create_message_and_run(
            thread_id,
            ChatMessageCreate(
                content="09:32 UTC",
                idempotency_key="followup-round-2",
            ),
        )

        self.assertEqual(run.request_payload["followup_root_ordinal"], 1)
        self.assertEqual(run.request_payload["followup_round"], 2)
        rag_query = run.request_payload["rag_query"]
        self.assertLessEqual(
            len(rag_query),
            settings.chat_followup_combined_query_max_chars,
        )
        expected_order = [
            original.content,
            question_one.content,
            answer_one.content,
            question_two.content,
            "09:32 UTC",
        ]
        positions = [rag_query.index(value) for value in expected_order]
        self.assertEqual(positions, sorted(positions))

    async def test_failed_idempotent_followup_requeues_same_run_without_duplicate(
        self,
    ) -> None:
        now = datetime.now(timezone.utc)
        thread_id = uuid4()
        thread = ChatThread(
            id=thread_id,
            title="Saved chat",
            status="awaiting_followup",
            next_message_ordinal=4,
        )
        answer = ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            ordinal=3,
            role="user",
            content="host-7",
            metadata_json={},
        )
        request_payload = {
            "content": answer.content,
            "rag_query": "bounded clarified query",
            "followup_root_ordinal": 1,
            "followup_round": 1,
        }
        run = ChatRun(
            id=uuid4(),
            thread_id=thread_id,
            request_message_id=answer.id,
            operation="query",
            status="failed",
            input_rag_session_id=None,
            idempotency_key="retry-key",
            request_fingerprint=hashlib.sha256(
                answer.content.encode("utf-8")
            ).hexdigest(),
            request_payload=request_payload,
            attempt_count=1,
            lease_owner="stale-worker",
            lease_expires_at=now - timedelta(minutes=1),
            error_code="rag_unavailable",
            error_message="RAG service unavailable",
            started_at=now - timedelta(minutes=2),
            finished_at=now - timedelta(minutes=1),
        )
        thread_result = Mock()
        thread_result.scalar_one_or_none.return_value = thread
        run_result = Mock()
        run_result.scalar_one_or_none.return_value = run
        no_active_run_result = Mock()
        no_active_run_result.scalar_one_or_none.return_value = None
        latest_run_result = Mock()
        latest_run_result.scalar_one_or_none.return_value = run.id
        db = Mock()
        db.begin.return_value = _Transaction()
        db.execute = AsyncMock(
            side_effect=[
                thread_result,
                run_result,
                no_active_run_result,
                latest_run_result,
            ]
        )
        db.get = AsyncMock(return_value=answer)
        db.flush = AsyncMock()

        returned_message, returned_run = (
            await ChatMessageService(db).create_message_and_run(
                thread_id,
                ChatMessageCreate(
                    content=answer.content,
                    idempotency_key="retry-key",
                ),
            )
        )

        self.assertIs(returned_message, answer)
        self.assertIs(returned_run, run)
        self.assertEqual(run.status, "queued")
        self.assertIsNone(run.error_code)
        self.assertIsNone(run.error_message)
        self.assertIsNone(run.started_at)
        self.assertIsNone(run.finished_at)
        self.assertIsNone(run.lease_owner)
        self.assertIsNone(run.lease_expires_at)
        self.assertEqual(thread.status, "processing")
        self.assertEqual(thread.next_message_ordinal, 4)
        self.assertEqual(run.request_payload, request_payload)
        self.assertEqual(run.request_payload["followup_root_ordinal"], 1)
        self.assertEqual(run.request_payload["followup_round"], 1)
        db.add.assert_not_called()
        db.flush.assert_awaited_once()
        latest_run_statement = db.execute.await_args_list[3].args[0]
        latest_run_sql = str(latest_run_statement)
        self.assertIn("JOIN chat_messages", latest_run_sql)
        self.assertIn(
            "ORDER BY chat_messages.ordinal DESC, "
            "chat_runs.created_at DESC, chat_runs.id DESC",
            latest_run_sql,
        )

    async def test_failed_idempotent_retry_rejects_an_active_run(self) -> None:
        thread_id = uuid4()
        failed_answer = ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            ordinal=3,
            role="user",
            content="host-7",
            metadata_json={},
        )
        failed_run = ChatRun(
            id=uuid4(),
            thread_id=thread_id,
            request_message_id=failed_answer.id,
            operation="query",
            status="failed",
            input_rag_session_id=None,
            idempotency_key="failed-key",
            request_fingerprint=hashlib.sha256(
                failed_answer.content.encode("utf-8")
            ).hexdigest(),
            request_payload={"content": failed_answer.content},
            attempt_count=1,
        )
        active_run = ChatRun(
            id=uuid4(),
            thread_id=thread_id,
            request_message_id=uuid4(),
            operation="query",
            status="queued",
            input_rag_session_id=None,
            idempotency_key="active-key",
            request_fingerprint="5" * 64,
            request_payload={"content": "edited answer"},
            attempt_count=0,
        )
        thread = ChatThread(
            id=thread_id,
            title="Saved chat",
            status="processing",
            next_message_ordinal=5,
        )
        thread_result = Mock()
        thread_result.scalar_one_or_none.return_value = thread
        failed_run_result = Mock()
        failed_run_result.scalar_one_or_none.return_value = failed_run
        active_run_result = Mock()
        active_run_result.scalar_one_or_none.return_value = active_run
        db = Mock()
        db.begin.return_value = _Transaction()
        db.execute = AsyncMock(
            side_effect=[
                thread_result,
                failed_run_result,
                active_run_result,
            ]
        )
        db.get = AsyncMock(return_value=failed_answer)
        db.flush = AsyncMock()

        with self.assertRaises(HTTPException) as raised:
            await ChatMessageService(db).create_message_and_run(
                thread_id,
                ChatMessageCreate(
                    content=failed_answer.content,
                    idempotency_key="failed-key",
                ),
            )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(
            raised.exception.detail,
            "Chat thread already has an active run",
        )
        self.assertEqual(failed_run.status, "failed")
        self.assertEqual(failed_run.attempt_count, 1)
        db.flush.assert_not_awaited()

    async def test_failed_idempotent_retry_rejects_a_stale_request(self) -> None:
        thread_id = uuid4()
        failed_answer = ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            ordinal=3,
            role="user",
            content="host-7",
            metadata_json={},
        )
        failed_run = ChatRun(
            id=uuid4(),
            thread_id=thread_id,
            request_message_id=failed_answer.id,
            operation="query",
            status="failed",
            input_rag_session_id=None,
            idempotency_key="failed-key",
            request_fingerprint=hashlib.sha256(
                failed_answer.content.encode("utf-8")
            ).hexdigest(),
            request_payload={"content": failed_answer.content},
            attempt_count=1,
        )
        later_run_id = uuid4()
        thread = ChatThread(
            id=thread_id,
            title="Saved chat",
            status="awaiting_followup",
            next_message_ordinal=5,
        )
        thread_result = Mock()
        thread_result.scalar_one_or_none.return_value = thread
        failed_run_result = Mock()
        failed_run_result.scalar_one_or_none.return_value = failed_run
        no_active_run_result = Mock()
        no_active_run_result.scalar_one_or_none.return_value = None
        latest_run_result = Mock()
        latest_run_result.scalar_one_or_none.return_value = later_run_id
        db = Mock()
        db.begin.return_value = _Transaction()
        db.execute = AsyncMock(
            side_effect=[
                thread_result,
                failed_run_result,
                no_active_run_result,
                latest_run_result,
            ]
        )
        db.get = AsyncMock(return_value=failed_answer)
        db.flush = AsyncMock()

        with self.assertRaises(HTTPException) as raised:
            await ChatMessageService(db).create_message_and_run(
                thread_id,
                ChatMessageCreate(
                    content=failed_answer.content,
                    idempotency_key="failed-key",
                ),
            )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(
            raised.exception.detail,
            "Failed chat run is no longer the latest request",
        )
        self.assertEqual(failed_run.status, "failed")
        self.assertEqual(failed_run.attempt_count, 1)
        db.flush.assert_not_awaited()

    async def test_edited_failed_clarification_retry_uses_new_answer(self) -> None:
        thread_id = uuid4()
        thread = ChatThread(
            id=thread_id,
            title="Saved chat",
            status="awaiting_followup",
            next_message_ordinal=4,
        )
        original = ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            ordinal=1,
            role="user",
            content="Investigate the suspicious PowerShell event.",
            metadata_json={},
        )
        question = ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            ordinal=2,
            role="assistant",
            content="Which affected host produced this event?",
            metadata_json={
                "chat_followup": {
                    "kind": "clarification",
                    "source_run_id": str(uuid4()),
                    "root_ordinal": 1,
                    "round": 1,
                }
            },
        )
        failed_answer = ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            ordinal=3,
            role="user",
            content="old-host",
            metadata_json={},
        )
        db = self._message_service_db(
            thread,
            [original, question, failed_answer],
        )

        _, run = await ChatMessageService(db).create_message_and_run(
            thread_id,
            ChatMessageCreate(
                content="edited-host",
                idempotency_key="edited-retry",
            ),
        )

        rag_query = run.request_payload["rag_query"]
        self.assertIsInstance(rag_query, str)
        self.assertIn("edited-host", rag_query)
        self.assertNotIn("old-host", rag_query)
        self.assertEqual(run.request_payload["followup_round"], 1)

    async def test_failed_followup_run_restores_awaiting_status(self) -> None:
        thread_id = uuid4()
        thread = ChatThread(
            id=thread_id,
            title="Saved chat",
            status="processing",
            next_message_ordinal=4,
        )
        run = ChatRun(
            id=uuid4(),
            thread_id=thread_id,
            request_message_id=uuid4(),
            operation="query",
            status="running",
            input_rag_session_id=None,
            idempotency_key="followup-failure",
            request_fingerprint="3" * 64,
            request_payload={
                "content": "host-7",
                "rag_query": "bounded clarified query",
                "followup_root_ordinal": 1,
                "followup_round": 1,
            },
            attempt_count=1,
            lease_owner="worker-1",
        )
        db = self._failure_db(thread, run)

        failed = await ChatRunWorker(db).fail_run(
            run.id,
            "worker-1",
            "rag_unavailable",
            "RAG service unavailable",
        )

        self.assertTrue(failed)
        self.assertEqual(thread.status, "awaiting_followup")
        self.assertEqual(run.status, "failed")

    async def test_failed_root_run_remains_failed(self) -> None:
        thread_id = uuid4()
        thread = ChatThread(
            id=thread_id,
            title="Saved chat",
            status="processing",
            next_message_ordinal=2,
        )
        run = ChatRun(
            id=uuid4(),
            thread_id=thread_id,
            request_message_id=uuid4(),
            operation="query",
            status="running",
            input_rag_session_id=None,
            idempotency_key="root-failure",
            request_fingerprint="4" * 64,
            request_payload={
                "content": "Investigate this event",
                "rag_query": "Investigate this event",
                "followup_root_ordinal": 1,
                "followup_round": 0,
            },
            attempt_count=1,
            lease_owner="worker-2",
        )
        db = self._failure_db(thread, run)

        failed = await ChatRunWorker(db).fail_run(
            run.id,
            "worker-2",
            "rag_unavailable",
            "RAG service unavailable",
        )

        self.assertTrue(failed)
        self.assertEqual(thread.status, "failed")
        self.assertEqual(run.status, "failed")

    async def test_legacy_queued_followup_payload_is_reconstructed(self) -> None:
        thread_id = uuid4()
        original = ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            ordinal=1,
            role="user",
            content="Investigate this event",
            metadata_json={},
        )
        question = ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            ordinal=2,
            role="assistant",
            content="Which host?",
            metadata_json={},
        )
        answer = ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            ordinal=3,
            role="user",
            content="host-7",
            metadata_json={},
        )
        run = ChatRun(
            id=uuid4(),
            thread_id=thread_id,
            request_message_id=answer.id,
            operation="query",
            status="queued",
            input_rag_session_id=None,
            idempotency_key="legacy",
            request_fingerprint="0" * 64,
            request_payload={
                "content": answer.content,
                "rag_query": "legacy bounded query",
                "skip_followup_policy": True,
            },
            attempt_count=0,
        )
        run_result = Mock()
        run_result.scalar_one_or_none.return_value = run
        history_result = Mock()
        history_result.scalars.return_value.all.return_value = [
            original,
            question,
            answer,
        ]
        db = Mock()
        db.begin.return_value = _Transaction()
        db.execute = AsyncMock(side_effect=[run_result, history_result])
        db.flush = AsyncMock()

        claimed = await ChatRunWorker(db).claim_run(run.id, "worker-1")

        self.assertIsNotNone(claimed)
        assert claimed is not None
        self.assertEqual(claimed.original_user_content, original.content)
        self.assertEqual(claimed.followup_root_ordinal, 1)
        self.assertEqual(
            [
                (exchange.question, exchange.answer)
                for exchange in claimed.clarification_exchanges
            ],
            [(question.content, answer.content)],
        )

    async def test_worker_uses_latest_edited_clarification_attempt(self) -> None:
        thread_id = uuid4()
        original = ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            ordinal=1,
            role="user",
            content="Investigate this event",
            metadata_json={},
        )
        question_one = ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            ordinal=2,
            role="assistant",
            content="Which host?",
            metadata_json={},
        )
        answer_one = ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            ordinal=3,
            role="user",
            content="host-7",
            metadata_json={},
        )
        question_two = ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            ordinal=4,
            role="assistant",
            content="When was it first observed?",
            metadata_json={},
        )
        failed_answer = ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            ordinal=5,
            role="user",
            content="old timestamp",
            metadata_json={},
        )
        edited_answer = ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            ordinal=6,
            role="user",
            content="09:32 UTC",
            metadata_json={},
        )
        run = ChatRun(
            id=uuid4(),
            thread_id=thread_id,
            request_message_id=edited_answer.id,
            operation="query",
            status="queued",
            input_rag_session_id=None,
            idempotency_key="edited-worker-retry",
            request_fingerprint="6" * 64,
            request_payload={
                "content": edited_answer.content,
                "rag_query": "bounded query with 09:32 UTC",
                "followup_root_ordinal": 1,
                "followup_round": 2,
            },
            attempt_count=0,
        )
        run_result = Mock()
        run_result.scalar_one_or_none.return_value = run
        history_result = Mock()
        history_result.scalars.return_value.all.return_value = [
            original,
            question_one,
            answer_one,
            question_two,
            failed_answer,
            edited_answer,
        ]
        db = Mock()
        db.begin.return_value = _Transaction()
        db.execute = AsyncMock(side_effect=[run_result, history_result])
        db.flush = AsyncMock()

        claimed = await ChatRunWorker(db).claim_run(run.id, "worker-edited")

        self.assertIsNotNone(claimed)
        assert claimed is not None
        self.assertEqual(
            [
                (exchange.question, exchange.answer)
                for exchange in claimed.clarification_exchanges
            ],
            [
                (question_one.content, answer_one.content),
                (question_two.content, edited_answer.content),
            ],
        )

    async def test_legacy_normal_queued_user_starts_a_new_policy_root(self) -> None:
        thread_id = uuid4()
        old_user = ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            ordinal=1,
            role="user",
            content="Explain the previous event",
            metadata_json={},
        )
        old_final_answer = ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            ordinal=2,
            role="assistant",
            content="The previous event was fully explained.",
            metadata_json={},
        )
        new_user = ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            ordinal=3,
            role="user",
            content="Investigate a different incident",
            metadata_json={},
        )
        run = ChatRun(
            id=uuid4(),
            thread_id=thread_id,
            request_message_id=new_user.id,
            operation="query",
            status="queued",
            input_rag_session_id=None,
            idempotency_key="legacy-normal",
            request_fingerprint="1" * 64,
            request_payload={
                "content": new_user.content,
                "rag_query": new_user.content,
                "skip_followup_policy": False,
            },
            attempt_count=0,
        )
        run_result = Mock()
        run_result.scalar_one_or_none.return_value = run
        request_message_result = Mock()
        request_message_result.scalar_one_or_none.return_value = new_user
        request_message_result.scalars.return_value.all.return_value = [
            old_user,
            old_final_answer,
            new_user,
        ]
        db = Mock()
        db.begin.return_value = _Transaction()
        db.execute = AsyncMock(
            side_effect=[run_result, request_message_result]
        )
        db.flush = AsyncMock()

        claimed = await ChatRunWorker(db).claim_run(run.id, "worker-2")

        self.assertIsNotNone(claimed)
        assert claimed is not None
        self.assertEqual(claimed.original_user_content, new_user.content)
        self.assertEqual(claimed.followup_root_ordinal, new_user.ordinal)
        self.assertEqual(claimed.clarification_exchanges, ())
        request_statement = db.execute.await_args_list[1].args[0]
        self.assertNotIn("ORDER BY", str(request_statement))

    async def test_new_round_zero_payload_uses_root_fast_path(self) -> None:
        thread_id = uuid4()
        run = ChatRun(
            id=uuid4(),
            thread_id=thread_id,
            request_message_id=uuid4(),
            operation="query",
            status="queued",
            input_rag_session_id=None,
            idempotency_key="new-round-zero",
            request_fingerprint="2" * 64,
            request_payload={
                "content": "Investigate this new incident",
                "rag_query": "Investigate this new incident",
                "followup_root_ordinal": 7,
                "followup_round": 0,
            },
            attempt_count=0,
        )
        run_result = Mock()
        run_result.scalar_one_or_none.return_value = run
        db = Mock()
        db.begin.return_value = _Transaction()
        db.execute = AsyncMock(return_value=run_result)
        db.flush = AsyncMock()

        claimed = await ChatRunWorker(db).claim_run(run.id, "worker-3")

        self.assertIsNotNone(claimed)
        assert claimed is not None
        self.assertEqual(
            claimed.original_user_content,
            "Investigate this new incident",
        )
        self.assertEqual(claimed.followup_root_ordinal, 7)
        self.assertEqual(claimed.clarification_exchanges, ())
        self.assertEqual(db.execute.await_count, 1)

    def test_reconstruction_ignores_terminal_assistant_after_marked_question(self) -> None:
        thread_id = uuid4()
        original = ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            ordinal=1,
            role="user",
            content="Investigate this event",
            metadata_json={},
        )
        question = ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            ordinal=2,
            role="assistant",
            content="Which host was affected?",
            metadata_json={
                "chat_followup": {
                    "kind": "clarification",
                    "root_ordinal": 1,
                    "round": 1,
                }
            },
        )
        answer = ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            ordinal=3,
            role="user",
            content="host-7",
            metadata_json={},
        )
        terminal = ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            ordinal=4,
            role="assistant",
            content="The analysis is complete.",
            retrieval_context_id="retrieval-1",
            metadata_json={"mitre_table": []},
        )

        chain = reconstruct_clarification_chain(
            [terminal, answer, original, question],
            root_ordinal=1,
        )

        self.assertIsNotNone(chain)
        assert chain is not None
        self.assertEqual(chain.original_user_content, original.content)
        self.assertEqual(
            [
                (exchange.question, exchange.answer)
                for exchange in chain.exchanges
            ],
            [(question.content, answer.content)],
        )


if __name__ == "__main__":
    unittest.main()
