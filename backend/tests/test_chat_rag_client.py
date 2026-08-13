import json
import unittest

import httpx

from app.schemas.chat.rag import QueryResponse
from app.services.chat.chat_worker import map_rag_response
from app.services.chat.rag_client import RagCallFailure, request_rag


class ChatRagClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_query_payload_and_completed_mapping(self) -> None:
        captured_payload: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/query")
            captured_payload.update(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "status": "completed",
                    "retrieval_context_id": "retrieval-1",
                    "context": "bounded MITRE context",
                    "mitre_table": [],
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            response = await request_rag("inspect this", client=client)

        self.assertEqual(
            captured_payload,
            {"query": "inspect this", "use_agent": True},
        )
        self.assertEqual(
            map_rag_response(response),
            {
                "retrieved_context": "bounded MITRE context",
                "retrieval_context_id": "retrieval-1",
                "mitre_table": [],
                "previous_analysis": None,
            },
        )

    async def test_answer_fields_are_rejected(self) -> None:
        for forbidden_field in ("answer", "rag_answer"):
            with self.subTest(forbidden_field=forbidden_field):
                def handler(request: httpx.Request) -> httpx.Response:
                    return httpx.Response(
                        200,
                        json={
                            "status": "completed",
                            "retrieval_context_id": None,
                            "context": "",
                            "mitre_table": [],
                            forbidden_field: "must not cross this boundary",
                        },
                    )

                async with httpx.AsyncClient(
                    transport=httpx.MockTransport(handler)
                ) as client:
                    with self.assertRaises(RagCallFailure) as raised:
                        await request_rag("inspect this", client=client)
                self.assertEqual(raised.exception.code, "rag_invalid_response")

    async def test_non_completed_response_is_rejected(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/query")
            return httpx.Response(
                200,
                json={
                    "status": "followup",
                    "followup_question": "Which host?",
                    "session_id": "session-1",
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            with self.assertRaises(RagCallFailure) as raised:
                await request_rag("inspect this", client=client)

        self.assertEqual(raised.exception.code, "rag_invalid_response")
        self.assertEqual(
            raised.exception.message,
            "RAG service returned an invalid response",
        )


class ChatRagResponseMappingTests(unittest.TestCase):
    def test_completed_mitre_rows_are_json_safe_and_preserve_fields(self) -> None:
        mitre_row = {
            "technique_id": "T1059.001",
            "name": "PowerShell",
            "entity_type": "attack-pattern",
            "tactic": "execution",
            "score": 0.98,
            "source": "vector",
            "relevance": "cited_in_answer",
            "description": "PowerShell execution",
            "mitre_url": "https://attack.mitre.org/techniques/T1059/001/",
        }

        outcome = map_rag_response(
            QueryResponse(
                status="completed",
                retrieval_context_id="retrieval-1",
                context="PowerShell retrieval context",
                mitre_table=[mitre_row],
            )
        )

        self.assertEqual(outcome["mitre_table"], [mitre_row])
        self.assertEqual(
            json.loads(json.dumps(outcome)),
            outcome,
        )

    def test_empty_no_hit_context_and_empty_id_sentinel_are_valid(self) -> None:
        response = QueryResponse.model_validate(
            {
                "status": "completed",
                "retrieval_context_id": "",
                "context": "",
                "mitre_table": [],
            }
        )
        self.assertIsNone(response.retrieval_context_id)
        self.assertEqual(map_rag_response(response)["retrieved_context"], "")


if __name__ == "__main__":
    unittest.main()
