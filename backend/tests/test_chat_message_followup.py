import unittest
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from app.config import settings
from app.models.chat import ChatMessage, ChatRun, ChatThread
from app.schemas.chat import ChatMessageCreate
from app.services.chat.chat_message import ChatMessageService
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


if __name__ == "__main__":
    unittest.main()
