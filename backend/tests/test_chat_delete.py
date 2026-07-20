import unittest
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from fastapi import HTTPException

from app.models.chat import ChatThread
from app.services.chat.chat_management import ChatService


class ChatDeleteServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_delete_thread_locks_and_deletes_parent(self) -> None:
        thread = ChatThread(id=uuid4(), title="Delete me")
        result = Mock()
        result.scalar_one_or_none.return_value = thread
        db = Mock()
        db.execute = AsyncMock(return_value=result)
        db.delete = AsyncMock()
        db.commit = AsyncMock()

        await ChatService(db).delete_thread(thread.id)

        statement = db.execute.await_args.args[0]
        self.assertIn("FOR UPDATE", str(statement))
        db.delete.assert_awaited_once_with(thread)
        db.commit.assert_awaited_once_with()

    async def test_delete_missing_thread_returns_404(self) -> None:
        result = Mock()
        result.scalar_one_or_none.return_value = None
        db = Mock()
        db.execute = AsyncMock(return_value=result)
        db.delete = AsyncMock()
        db.commit = AsyncMock()

        with self.assertRaises(HTTPException) as raised:
            await ChatService(db).delete_thread(uuid4())

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(raised.exception.detail, "Chat thread not found")
        db.delete.assert_not_awaited()
        db.commit.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
