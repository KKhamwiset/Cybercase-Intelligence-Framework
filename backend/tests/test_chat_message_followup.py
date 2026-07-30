import unittest
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from app.config import settings
from app.models.chat import ChatMessage, ChatRun, ChatThread
from app.schemas.chat import ChatMessageCreate
from app.services.chat.chat_message import ChatMessageService


class _Transaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None


class ChatMessageFollowUpTests(unittest.IsolatedAsyncioTestCase):
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

        thread_result = Mock()
        thread_result.scalar_one_or_none.return_value = thread
        no_run_result = Mock()
        no_run_result.scalar_one_or_none.return_value = None
        history_result = Mock()
        history_result.scalars.return_value.all.return_value = [
            clarification,
            original,
        ]

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

        message, run = await ChatMessageService(db).create_message_and_run(
            thread_id,
            ChatMessageCreate(
                content="host-7",
                idempotency_key="followup-key",
            ),
        )

        history_statement = db.execute.await_args_list[3].args[0]
        self.assertIn("LIMIT", str(history_statement))
        self.assertEqual(run.operation, "query")
        self.assertIsNone(run.input_rag_session_id)
        self.assertIsNone(thread.active_rag_session_id)
        self.assertEqual(thread.status, "processing")
        self.assertEqual(message.ordinal, 3)
        self.assertTrue(run.request_payload["skip_followup_policy"])
        rag_query = run.request_payload["rag_query"]
        self.assertIsInstance(rag_query, str)
        self.assertLessEqual(
            len(rag_query),
            settings.chat_followup_combined_query_max_chars,
        )
        self.assertIn(original.content, rag_query)
        self.assertIn(clarification.content, rag_query)
        self.assertIn("host-7", rag_query)


if __name__ == "__main__":
    unittest.main()
