import json
import unittest

import httpx

from app.schemas.rag import QueryResponse
from app.services.chat.chat_worker import map_rag_response
from app.services.chat.rag_client import RagCallFailure, request_rag


class ChatRagClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_query_payload_and_completed_mapping(self) -> None:
        captured_payload: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured_payload.update(json.loads(request.content))
            return httpx.Response(
                200,
                json={"status": "completed", "answer": "done"},
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            response = await request_rag(
                "query", "inspect this", None, client=client
            )

        self.assertEqual(
            captured_payload,
            {"query": "inspect this", "use_agent": True},
        )
        self.assertEqual(map_rag_response(response).content, "done")

    async def test_resume_404_is_expired_session(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/resume")
            return httpx.Response(404, json={"detail": "missing"})

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            with self.assertRaises(RagCallFailure) as raised:
                await request_rag(
                    "resume", "answer", "session-1", client=client
                )

        self.assertEqual(raised.exception.code, "rag_session_expired")
        self.assertEqual(
            raised.exception.message,
            "Failed to recover follow-up session",
        )


class ChatRagResponseMappingTests(unittest.TestCase):
    def test_followup_mapping(self) -> None:
        outcome = map_rag_response(
            QueryResponse(
                status="followup",
                followup_question="Which host?",
                session_id="session-2",
            )
        )
        self.assertEqual(outcome.content, "Which host?")
        self.assertEqual(outcome.thread_status, "awaiting_followup")
        self.assertEqual(outcome.active_rag_session_id, "session-2")

    def test_blank_completed_response_is_invalid(self) -> None:
        with self.assertRaises(RagCallFailure) as raised:
            map_rag_response(QueryResponse(status="completed", answer=" "))
        self.assertEqual(raised.exception.code, "rag_invalid_response")


if __name__ == "__main__":
    unittest.main()
