import json
import unittest
from uuid import uuid4

import httpx

from app.config import settings
from app.schemas.rag import QueryResponse
from app.services.chat.followup_policy import (
    AnthropicFollowUpPolicy,
    ClarificationExchange,
    FollowUpDecision,
    build_clarified_query,
)
from app.services.chat.chat_worker import resolve_followup_outcome


class _AskPolicy:
    calls = 0

    async def decide(
        self,
        *,
        original_user_content: str,
        clarification_exchanges: tuple[ClarificationExchange, ...],
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
        original_user_content: str,
        clarification_exchanges: tuple[ClarificationExchange, ...],
        rag_answer: str,
    ) -> FollowUpDecision:
        raise TimeoutError("policy timed out")


class _AnswerPolicy:
    calls = 0

    async def decide(
        self,
        *,
        original_user_content: str,
        clarification_exchanges: tuple[ClarificationExchange, ...],
        rag_answer: str,
    ) -> FollowUpDecision:
        self.calls += 1
        return FollowUpDecision(action="answer", question="")


class _QuestionPolicy:
    def __init__(self, question: str):
        self.question = question
        self.calls: list[
            tuple[str, tuple[ClarificationExchange, ...], str]
        ] = []

    async def decide(
        self,
        *,
        original_user_content: str,
        clarification_exchanges: tuple[ClarificationExchange, ...],
        rag_answer: str,
    ) -> FollowUpDecision:
        self.calls.append(
            (
                original_user_content,
                tuple(clarification_exchanges),
                rag_answer,
            )
        )
        return FollowUpDecision(
            action="ask_followup",
            question=self.question,
        )


class FollowUpPolicyHttpTests(unittest.IsolatedAsyncioTestCase):
    async def test_structured_policy_uses_bounded_accumulated_context(self) -> None:
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
                    original_user_content=(
                        "ORIGINAL PREFIX "
                        + "u"
                        * (
                            settings.chat_followup_policy_max_user_chars
                            + 10
                        )
                    ),
                    clarification_exchanges=tuple(
                        ClarificationExchange(
                            question=f"Question {index} " + ("q" * 500),
                            answer=(
                                (
                                    "NEWEST ANSWER "
                                    if index == 3
                                    else f"Older answer {index} "
                                )
                                + ("x" * 5_000)
                            ),
                        )
                        for index in range(1, 4)
                    ),
                    rag_answer=(
                        "RAG PREFIX "
                        + "a"
                        * (
                            settings.chat_followup_policy_max_answer_chars
                            + 10
                        )
                    ),
                    client=client,
                )
        finally:
            settings.anthropic_api_key = original_key

        self.assertEqual(decision.action, "ask_followup")
        self.assertEqual(decision.question, "Which host was affected?")
        self.assertIn("untrusted data", str(captured["system"]))
        self.assertIn("accumulated incident context", str(captured["system"]))
        self.assertIn("Do not re-ask", str(captured["system"]))
        user_payload = captured["messages"]
        assert isinstance(user_payload, list)
        message_content = user_payload[0]["content"]
        assert isinstance(message_content, str)
        supplied = json.loads(message_content.split("\n", 1)[1])
        self.assertLessEqual(
            len(supplied["original_user_content"]),
            settings.chat_followup_policy_max_user_chars,
        )
        self.assertLessEqual(
            len(supplied["rag_answer"]),
            settings.chat_followup_policy_max_answer_chars,
        )
        self.assertTrue(
            supplied["original_user_content"].startswith("ORIGINAL PREFIX ")
        )
        self.assertTrue(supplied["rag_answer"].startswith("RAG PREFIX "))
        self.assertTrue(
            supplied["clarification_exchanges"][-1]["answer"].startswith(
                "NEWEST ANSWER "
            )
        )
        supplied_size = (
            len(supplied["original_user_content"])
            + len(supplied["rag_answer"])
            + sum(
                len(exchange["question"]) + len(exchange["answer"])
                for exchange in supplied["clarification_exchanges"]
            )
        )
        self.assertLessEqual(
            supplied_size,
            settings.chat_followup_combined_query_max_chars,
        )


class FollowUpOutcomeTests(unittest.IsolatedAsyncioTestCase):
    async def test_policy_question_becomes_only_assistant_outcome(self) -> None:
        source_run_id = uuid4()
        outcome = await resolve_followup_outcome(
            QueryResponse(status="completed", answer="Partial answer"),
            original_user_content="Investigate this event",
            clarification_exchanges=(),
            followup_root_ordinal=7,
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
        self.assertEqual(
            outcome.metadata_json["chat_followup"]["root_ordinal"],
            7,
        )
        self.assertEqual(
            outcome.metadata_json["chat_followup"]["round"],
            1,
        )

    async def test_second_insufficiency_asks_distinct_second_question(self) -> None:
        exchanges = (
            ClarificationExchange(
                question="Which host was affected?",
                answer="host-7",
            ),
        )
        policy = _QuestionPolicy("When was the event first observed?")
        outcome = await resolve_followup_outcome(
            QueryResponse(status="completed", answer="Still partial"),
            original_user_content="Investigate this event",
            clarification_exchanges=exchanges,
            followup_root_ordinal=3,
            source_run_id=uuid4(),
            policy=policy,
        )

        self.assertEqual(
            outcome.content,
            "When was the event first observed?",
        )
        self.assertEqual(outcome.thread_status, "awaiting_followup")
        self.assertEqual(
            outcome.metadata_json["chat_followup"]["round"],
            2,
        )
        self.assertEqual(
            policy.calls,
            [("Investigate this event", exchanges, "Still partial")],
        )

    async def test_query_rounds_progress_from_initial_to_second_to_terminal(self) -> None:
        source_run_id = uuid4()
        first = await resolve_followup_outcome(
            QueryResponse(status="completed", answer="Initial partial answer"),
            original_user_content="Investigate this event",
            clarification_exchanges=(),
            followup_root_ordinal=1,
            source_run_id=source_run_id,
            policy=_QuestionPolicy("Which host was affected?"),
        )
        first_exchange = ClarificationExchange(
            question=first.content,
            answer="host-7",
        )
        second = await resolve_followup_outcome(
            QueryResponse(status="completed", answer="Second partial answer"),
            original_user_content="Investigate this event",
            clarification_exchanges=(first_exchange,),
            followup_root_ordinal=1,
            source_run_id=uuid4(),
            policy=_QuestionPolicy("When was it first observed?"),
        )
        final = await resolve_followup_outcome(
            QueryResponse(status="completed", answer="Complete RAG answer"),
            original_user_content="Investigate this event",
            clarification_exchanges=(
                first_exchange,
                ClarificationExchange(
                    question=second.content,
                    answer="09:32 UTC",
                ),
            ),
            followup_root_ordinal=1,
            source_run_id=uuid4(),
            policy=_AnswerPolicy(),
        )

        self.assertEqual(first.thread_status, "awaiting_followup")
        self.assertEqual(
            first.metadata_json["chat_followup"]["round"],
            1,
        )
        self.assertEqual(second.thread_status, "awaiting_followup")
        self.assertEqual(
            second.metadata_json["chat_followup"]["round"],
            2,
        )
        self.assertEqual(final.thread_status, "idle")
        self.assertEqual(final.content, "Complete RAG answer")

    async def test_max_round_guard_returns_validated_rag_answer(self) -> None:
        exchanges = tuple(
            ClarificationExchange(
                question=f"Question {index}",
                answer=f"Answer {index}",
            )
            for index in range(settings.chat_followup_max_rounds)
        )
        policy = _QuestionPolicy("This question must not be asked")

        outcome = await resolve_followup_outcome(
            QueryResponse(status="completed", answer="Bounded final answer"),
            original_user_content="Investigate this event",
            clarification_exchanges=exchanges,
            followup_root_ordinal=1,
            source_run_id=uuid4(),
            policy=policy,
        )

        self.assertEqual(settings.chat_followup_max_rounds, 3)
        self.assertEqual(policy.calls, [])
        self.assertEqual(outcome.content, "Bounded final answer")
        self.assertEqual(outcome.thread_status, "idle")

    async def test_sufficient_later_round_returns_rag_answer_and_idle(self) -> None:
        policy = _AnswerPolicy()
        outcome = await resolve_followup_outcome(
            QueryResponse(status="completed", answer="Complete analysis"),
            original_user_content="Investigate this event",
            clarification_exchanges=(
                ClarificationExchange(
                    question="Which host was affected?",
                    answer="host-7",
                ),
                ClarificationExchange(
                    question="When was it first observed?",
                    answer="09:32 UTC",
                ),
            ),
            followup_root_ordinal=3,
            source_run_id=uuid4(),
            policy=policy,
        )

        self.assertEqual(policy.calls, 1)
        self.assertEqual(outcome.content, "Complete analysis")
        self.assertEqual(outcome.thread_status, "idle")

    async def test_exact_normalized_duplicate_question_stops_safely(self) -> None:
        policy = _QuestionPolicy("  WHICH   HOST was affected?! ")
        outcome = await resolve_followup_outcome(
            QueryResponse(status="completed", answer="Current RAG answer"),
            original_user_content="Investigate this event",
            clarification_exchanges=(
                ClarificationExchange(
                    question="Which host was affected?",
                    answer="The host is unavailable",
                ),
            ),
            followup_root_ordinal=1,
            source_run_id=uuid4(),
            policy=policy,
        )

        self.assertEqual(outcome.content, "Current RAG answer")
        self.assertEqual(outcome.thread_status, "idle")

    async def test_later_policy_error_fails_open_to_rag_answer(self) -> None:
        source_run_id = uuid4()
        with self.assertLogs("app.chat", level="WARNING") as captured:
            outcome = await resolve_followup_outcome(
                QueryResponse(status="completed", answer="Useful RAG answer"),
                original_user_content="Investigate this event",
                clarification_exchanges=(
                    ClarificationExchange(
                        question="Which host?",
                        answer="host-7",
                    ),
                ),
                followup_root_ordinal=1,
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
            clarification_exchanges=(
                ClarificationExchange(
                    question="Which host?",
                    answer="CURRENT host-7",
                ),
                ClarificationExchange(
                    question="When did it happen?",
                    answer="09:32 UTC",
                ),
            ),
        )

        self.assertLessEqual(
            len(query),
            settings.chat_followup_combined_query_max_chars,
        )
        self.assertIn("Original user request:", query)
        self.assertIn("Assistant question:\nWhich host?", query)
        self.assertIn("User answer:\nCURRENT host-7", query)
        self.assertIn("Assistant question:\nWhen did it happen?", query)
        self.assertIn("User answer:\n09:32 UTC", query)

    def test_extreme_query_preserves_original_and_newest_answer(self) -> None:
        exchanges = tuple(
            ClarificationExchange(
                question=f"Question {index} " + ("q" * 500),
                answer=(
                    (
                        "NEWEST ANSWER "
                        if index == 4
                        else f"Older answer {index} "
                    )
                    + ("a" * 5_000)
                ),
            )
            for index in range(1, 5)
        )

        query = build_clarified_query(
            original_user_content="ORIGINAL PREFIX " + ("o" * 20_000),
            clarification_exchanges=exchanges,
        )

        self.assertLessEqual(
            len(query),
            settings.chat_followup_combined_query_max_chars,
        )
        self.assertIn("Original user request:\nORIGINAL PREFIX ", query)
        self.assertIn("User answer:\nNEWEST ANSWER ", query)


if __name__ == "__main__":
    unittest.main()
