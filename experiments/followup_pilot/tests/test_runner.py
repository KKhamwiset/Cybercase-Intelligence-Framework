from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from experiments.followup_pilot.evaluator import (
    calculate_metrics,
    conduct_blind_evaluation,
)
from experiments.followup_pilot.runner import (
    FollowUpDecision,
    HumanAnswer,
    OUTSIDE_ANSWER_SHEET,
    QueryResponse,
    build_initial_query,
    load_case,
    run_adaptive_followup,
    run_no_followup,
    save_result,
)
from experiments.followup_pilot.schemas import (
    ExperimentResult,
    QuestionRecord,
    RagCallRecord,
)


CASE_PATH = (
    Path(__file__).resolve().parents[1] / "cases" / "m365_phishing_001.json"
)


class FakeRag:
    def __init__(self, answers: list[str]) -> None:
        self.responses = [
            QueryResponse(
                status="completed",
                answer=answer,
                retrieval_context_id=f"context-{index}",
            )
            for index, answer in enumerate(answers)
        ]
        self.queries: list[str] = []

    async def __call__(self, query: str) -> QueryResponse:
        self.queries.append(query)
        if not self.responses:
            raise AssertionError("unexpected external-style RAG call")
        return self.responses.pop(0)


class FakePolicy:
    def __init__(self, outcomes: list[FollowUpDecision | Exception]) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[dict[str, object]] = []

    async def decide(
        self,
        *,
        original_user_content: str,
        clarification_exchanges: object,
        rag_answer: str,
    ) -> FollowUpDecision:
        self.calls.append(
            {
                "original": original_user_content,
                "exchanges": tuple(clarification_exchanges),  # type: ignore[arg-type]
                "rag_answer": rag_answer,
            }
        )
        if not self.outcomes:
            raise AssertionError("unexpected policy call")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FixedRng:
    def shuffle(self, values: list[ExperimentResult]) -> None:
        values.reverse()


def answer_provider(answers: list[HumanAnswer]):
    remaining = list(answers)

    def provide(case, round_number, question):
        del case, round_number, question
        if not remaining:
            raise AssertionError("unexpected human answer request")
        return remaining.pop(0)

    return provide


def result_for(
    method: str,
    *,
    analysis: str,
    questions: list[QuestionRecord] | None = None,
) -> ExperimentResult:
    now = datetime(2026, 8, 3, tzinfo=timezone.utc)
    return ExperimentResult(
        experiment_id=f"experiment-{method}",
        case_id="m365_phishing_001",
        method=method,
        original_request="วิเคราะห์เหตุการณ์",
        initial_context="incomplete",
        questions=questions or [],
        followup_rounds=len(questions or []),
        final_rag_query="query",
        final_analysis=analysis,
        stopped_by="no_followup" if method == "no_followup" else "policy_answer",
        rag_model="same-rag",
        followup_model="same-policy",
        started_at=now,
        finished_at=now,
        latency_ms=1,
        rag_calls=[
            RagCallRecord(
                round=0,
                query="query",
                retrieval_context_id=None,
                latency_ms=1,
            )
        ],
    )


class RunnerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.case = load_case(CASE_PATH)

    async def test_no_followup_calls_rag_once_and_never_needs_policy(self) -> None:
        rag = FakeRag(["baseline analysis"])

        result = await run_no_followup(self.case, rag_call=rag)

        self.assertEqual(len(rag.queries), 1)
        self.assertEqual(result.followup_rounds, 0)
        self.assertEqual(result.questions, [])
        self.assertEqual(result.stopped_by, "no_followup")
        self.assertEqual(result.final_analysis, "baseline analysis")

    async def test_adaptive_rebuilds_query_and_preserves_exchange_order(self) -> None:
        rag = FakeRag(["initial", "after account", "final"])
        policy = FakePolicy(
            [
                FollowUpDecision(
                    action="ask_followup",
                    question="บัญชีใดได้รับผลกระทบ?",
                ),
                FollowUpDecision(action="answer", question=""),
            ]
        )
        provider = answer_provider(
            [
                HumanAnswer(
                    answer="บัญชีที่ได้รับผลกระทบคือ finance@example.com",
                    requested_fields=("affected_account",),
                )
            ]
        )

        result = await run_adaptive_followup(
            self.case,
            rag_call=rag,
            policy=policy,
            answer_provider=provider,
        )

        self.assertEqual(result.stopped_by, "policy_answer")
        self.assertEqual(len(rag.queries), 2)
        self.assertIn("บัญชีใดได้รับผลกระทบ?", rag.queries[1])
        self.assertIn("finance@example.com", rag.queries[1])
        self.assertEqual(result.final_rag_query, rag.queries[1])
        self.assertEqual(len(policy.calls), 2)
        second_exchanges = policy.calls[1]["exchanges"]
        self.assertEqual(
            [(item.question, item.answer) for item in second_exchanges],
            [
                (
                    "บัญชีใดได้รับผลกระทบ?",
                    "บัญชีที่ได้รับผลกระทบคือ finance@example.com",
                )
            ],
        )

    async def test_adaptive_stops_immediately_when_policy_answers(self) -> None:
        rag = FakeRag(["sufficient analysis"])
        policy = FakePolicy([FollowUpDecision(action="answer", question="")])

        result = await run_adaptive_followup(
            self.case,
            rag_call=rag,
            policy=policy,
            answer_provider=answer_provider([]),
        )

        self.assertEqual(result.stopped_by, "policy_answer")
        self.assertEqual(len(rag.queries), 1)
        self.assertEqual(result.followup_rounds, 0)

    async def test_adaptive_stops_after_three_answered_rounds(self) -> None:
        rag = FakeRag(["r0", "r1", "r2", "r3"])
        policy = FakePolicy(
            [
                FollowUpDecision(action="ask_followup", question=f"question {n}?")
                for n in range(1, 4)
            ]
        )
        provider = answer_provider(
            [HumanAnswer(answer=f"answer {n}") for n in range(1, 4)]
        )

        result = await run_adaptive_followup(
            self.case,
            rag_call=rag,
            policy=policy,
            answer_provider=provider,
        )

        self.assertEqual(result.stopped_by, "max_rounds")
        self.assertEqual(result.followup_rounds, 3)
        self.assertEqual(len(policy.calls), 3)
        self.assertEqual(len(rag.queries), 4)
        self.assertEqual([item.round for item in result.questions], [1, 2, 3])

    async def test_policy_exception_fails_open_to_latest_rag_answer(self) -> None:
        rag = FakeRag(["latest safe analysis"])
        policy = FakePolicy([TimeoutError("policy timed out")])

        result = await run_adaptive_followup(
            self.case,
            rag_call=rag,
            policy=policy,
            answer_provider=answer_provider([]),
        )

        self.assertEqual(result.stopped_by, "policy_failure")
        self.assertEqual(result.failure_reason, "TimeoutError")
        self.assertEqual(result.final_analysis, "latest safe analysis")
        self.assertEqual(len(rag.queries), 1)

    async def test_result_file_contains_required_metadata(self) -> None:
        result = await run_no_followup(self.case, rag_call=FakeRag(["analysis"]))
        with tempfile.TemporaryDirectory() as directory:
            path = save_result(result, Path(directory))
            loaded = ExperimentResult.model_validate_json(path.read_text("utf-8"))

        self.assertEqual(loaded.case_id, self.case.case_id)
        self.assertEqual(loaded.rag_model, "existing-rag-service")
        self.assertEqual(len(loaded.rag_calls), 1)
        self.assertGreaterEqual(loaded.latency_ms, 0)


class EvaluatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.case = load_case(CASE_PATH)

    def test_completeness_and_manual_metrics_are_calculated(self) -> None:
        question = QuestionRecord(
            round=1,
            question="บัญชีใดได้รับผลกระทบ?",
            answer="finance@example.com",
            is_compound=True,
            requested_fields=["affected_account"],
        )
        result = result_for(
            "adaptive_followup",
            analysis="analysis",
            questions=[question, question.model_copy(update={"round": 2})],
        )
        scores = {field: "missing" for field in self.case.reference_fields}
        scores["incident_type"] = "correct_supported"
        scores["affected_account"] = "correct_supported"
        scores["source_ip"] = "unsupported"

        metrics = calculate_metrics(
            case=self.case,
            result=result,
            field_scores=scores,
        )

        self.assertEqual(metrics.analysis_completeness, 0.2)
        self.assertEqual(metrics.hidden_field_recovery, 0.5)
        self.assertEqual(metrics.final_hidden_field_utilization, 0.5)
        self.assertEqual(metrics.questions_asked, 2)
        self.assertEqual(metrics.exact_duplicate_question_count, 1)
        self.assertEqual(metrics.compound_question_count, 2)
        self.assertEqual(metrics.unsupported_field_count, 1)

    def test_unknown_fallback_does_not_count_as_recovery(self) -> None:
        question = QuestionRecord(
            round=1,
            question="บัญชีใดได้รับผลกระทบ?",
            answer=OUTSIDE_ANSWER_SHEET,
            is_compound=False,
            requested_fields=["affected_account"],
        )
        scores = {field: "missing" for field in self.case.reference_fields}

        metrics = calculate_metrics(
            case=self.case,
            result=result_for(
                "adaptive_followup",
                analysis="analysis",
                questions=[question],
            ),
            field_scores=scores,
        )

        self.assertEqual(metrics.hidden_field_recovery, 0.0)
        self.assertEqual(metrics.final_hidden_field_utilization, 0.0)

    def test_evaluator_hides_mapping_until_all_scores_are_collected(self) -> None:
        outputs: list[str] = []
        input_calls = 0

        def fake_input(prompt: str) -> str:
            nonlocal input_calls
            input_calls += 1
            rendered = "\n".join(outputs)
            self.assertNotIn("no_followup", rendered)
            self.assertNotIn("adaptive_followup", rendered)
            self.assertIn("System", prompt)
            return "missing"

        evaluation = conduct_blind_evaluation(
            case=self.case,
            results=[
                result_for("no_followup", analysis="Analysis one"),
                result_for("adaptive_followup", analysis="Analysis two"),
            ],
            input_fn=fake_input,
            output_fn=outputs.append,
            rng=FixedRng(),
        )

        self.assertEqual(input_calls, len(self.case.reference_fields) * 2)
        self.assertEqual(
            set(evaluation.mapping.values()),
            {"no_followup", "adaptive_followup"},
        )
        revealed = "\n".join(outputs)
        self.assertIn("no_followup", revealed)
        self.assertIn("adaptive_followup", revealed)

    def test_fixture_hides_exactly_two_recoverable_fields(self) -> None:
        self.assertEqual(
            set(self.case.hidden_answers),
            {"affected_account", "initial_access"},
        )
        self.assertNotIn("finance@example.com", self.case.initial_context)
        self.assertNotIn("กรอกอีเมลและรหัสผ่าน", self.case.initial_context)
        initial_query = build_initial_query(self.case)
        self.assertNotIn("finance@example.com", initial_query)
        self.assertIn("203.0.113.77", initial_query)


if __name__ == "__main__":
    unittest.main()
