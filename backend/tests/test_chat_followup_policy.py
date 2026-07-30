import json
import unittest
from uuid import uuid4

import httpx

from app.config import settings
from app.schemas.rag import QueryResponse
from app.services.chat.followup_policy import (
    AnthropicFollowUpPolicy,
    FollowUpDecision,
    build_clarified_query,
)
from app.services.chat.chat_worker import resolve_followup_outcome


class _AskPolicy:
    calls = 0

    async def decide(
        self,
        *,
        user_content: str,
        rag_answer: str,
    ) -> FollowUpDecision:
        self.calls += 1
        return FollowUpDecision(
            action="ask_followup",
            question="Which affected host produced this event?",
        )


class _FailingPolicy:
    async def decide(
        self,
        *,
        user_content: str,
        rag_answer: str,
    ) -> FollowUpDecision:
        raise TimeoutError("policy timed out")


class FollowUpPolicyHttpTests(unittest.IsolatedAsyncioTestCase):
    async def test_structured_policy_uses_bounded_untrusted_content(self) -> None:
        original_key = settings.anthropic_api_key
        settings.anthropic_api_key = "test-key"
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured.update(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "stop_reason": "end_turn",
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {
                                    "action": "ask_followup",
                                    "question": "Which host was affected?",
                                }
                            ),
                        }
                    ],
                },
            )

        try:
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as client:
                decision = await AnthropicFollowUpPolicy().decide(
                    user_content="u" * (
                        settings.chat_followup_policy_max_user_chars + 10
                    ),
                    rag_answer="a" * (
                        settings.chat_followup_policy_max_answer_chars + 10
                    ),
                    client=client,
                )
        finally:
            settings.anthropic_api_key = original_key

        self.assertEqual(decision.action, "ask_followup")
        self.assertEqual(decision.question, "Which host was affected?")
        self.assertIn("untrusted data", str(captured["system"]))
        user_payload = captured["messages"]
        assert isinstance(user_payload, list)
        message_content = user_payload[0]["content"]
        supplied = json.loads(message_content.split("\n", 1)[1])
        self.assertEqual(
            len(supplied["original_user_content"]),
            settings.chat_followup_policy_max_user_chars,
        )
        self.assertEqual(
            len(supplied["rag_answer"]),
            settings.chat_followup_policy_max_answer_chars,
        )


class FollowUpOutcomeTests(unittest.IsolatedAsyncioTestCase):
    async def test_policy_question_becomes_only_assistant_outcome(self) -> None:
        source_run_id = uuid4()
        outcome = await resolve_followup_outcome(
            QueryResponse(status="completed", answer="Partial answer"),
            original_user_content="Investigate this event",
            skip_followup_policy=False,
            source_run_id=source_run_id,
            policy=_AskPolicy(),
        )

        self.assertEqual(
            outcome.content,
            "Which affected host produced this event?",
        )
        self.assertEqual(outcome.thread_status, "awaiting_followup")
        self.assertIsNone(outcome.active_rag_session_id)
        self.assertIsNone(outcome.retrieval_context_id)
        self.assertEqual(
            outcome.metadata_json["chat_followup"]["source_run_id"],
            str(source_run_id),
        )

    async def test_policy_error_fails_open_to_rag_answer(self) -> None:
        source_run_id = uuid4()
        with self.assertLogs("app.chat", level="WARNING") as captured:
            outcome = await resolve_followup_outcome(
                QueryResponse(status="completed", answer="Useful RAG answer"),
                original_user_content="Investigate this event",
                skip_followup_policy=False,
                source_run_id=source_run_id,
                policy=_FailingPolicy(),
            )

        self.assertEqual(outcome.content, "Useful RAG answer")
        self.assertEqual(outcome.thread_status, "idle")
        self.assertEqual(
            captured.output,
            [
                "WARNING:app.chat:Chat follow-up policy failed open "
                f"source_run_id={source_run_id} exception_type=TimeoutError"
            ],
        )

    async def test_policy_is_skipped_after_one_clarification(self) -> None:
        policy = _AskPolicy()
        outcome = await resolve_followup_outcome(
            QueryResponse(status="completed", answer="Clarified answer"),
            original_user_content="host-7",
            skip_followup_policy=True,
            source_run_id=uuid4(),
            policy=policy,
        )

        self.assertEqual(policy.calls, 0)
        self.assertEqual(outcome.content, "Clarified answer")
        self.assertEqual(outcome.thread_status, "idle")


class ClarifiedQueryTests(unittest.TestCase):
    def test_question_validation_supports_languages_without_question_mark(self) -> None:
        decision = FollowUpDecision(
            action="ask_followup",
            question="เหตุการณ์นี้เกิดขึ้นบนโฮสต์ใด",
        )

        self.assertEqual(
            decision.question,
            "เหตุการณ์นี้เกิดขึ้นบนโฮสต์ใด",
        )

    def test_combined_query_is_bounded_and_contains_all_turns(self) -> None:
        query = build_clarified_query(
            original_user_content="ORIGINAL " + ("o" * 20_000),
            clarification_question="Which host?",
            current_answer="CURRENT host-7",
        )

        self.assertLessEqual(
            len(query),
            settings.chat_followup_combined_query_max_chars,
        )
        self.assertIn("Original user request:", query)
        self.assertIn("Assistant clarification:\nWhich host?", query)
        self.assertIn("User clarification answer:\nCURRENT host-7", query)


if __name__ == "__main__":
    unittest.main()
