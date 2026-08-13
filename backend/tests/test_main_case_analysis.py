from copy import deepcopy
import json
import unittest
from typing import get_args
from unittest.mock import patch

import httpx

from app.config import settings
from app.services.case_analysis import (
    AnalysisMode,
    CaseAnalysisFailure,
    MainCaseAnalysisService,
    build_case_analysis_prompt,
)
from app.services.llm.core_llm import CoreLlmTarget


def _target() -> CoreLlmTarget:
    return CoreLlmTarget(
        provider="anthropic",
        model="test-model",
        api_key="test-key",
        base_url="https://provider.test",
        messages_url="https://provider.test/v1/messages",
        headers={"x-api-key": "test-key"},
    )


def _case_inputs() -> tuple[dict[str, object], dict[str, object]]:
    return (
        {
            "case_summary": "reported host-7 activity",
            "entities": [
                {
                    "entity_id": "host-7",
                    "attributes": {"roles": ["affected", "source"]},
                }
            ],
        },
        {
            "answer": "The grounded analysis identified host-7.",
            "retrieval_context_id": "retrieval-1",
            "mitre_table": [
                {
                    "technique_id": "T1059",
                    "metadata": {"confidence": "supported"},
                }
            ],
        },
    )


class MainCaseAnalysisServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_success_does_not_mutate_nested_inputs(self) -> None:
        case_state, analysis_context = _case_inputs()
        expected_case_state = deepcopy(case_state)
        expected_analysis_context = deepcopy(analysis_context)

        def respond(request: httpx.Request) -> httpx.Response:
            request_payload = json.loads(request.content)
            system_prompt = request_payload["system"]
            self.assertIn("TRUST HIERARCHY", system_prompt)
            self.assertIn("Do not retrieve new information", system_prompt)
            self.assertIn("ANALYSIS MODE: question_answer", system_prompt)
            self.assertIn("Answer the supplied question directly", system_prompt)
            self.assertIn("proportional to the specific question", system_prompt)
            self.assertIn("Do not force the standard five-section", system_prompt)
            self.assertIn(
                "Which host should be investigated next?",
                request_payload["messages"][0]["content"],
            )
            return httpx.Response(
                200,
                json={
                    "content": [
                        {"type": "text", "text": "Investigate host-7 next."}
                    ],
                    "stop_reason": "end_turn",
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(respond)
        ) as client:
            with patch(
                "app.services.case_analysis.service.resolve_core_llm_target",
                return_value=_target(),
            ):
                answer = await MainCaseAnalysisService(client=client).analyze(
                    mode="question_answer",
                    case_state_json=case_state,
                    analysis_context=analysis_context,
                    question="Which host should be investigated next?",
                )

        self.assertEqual(answer, "Investigate host-7 next.")
        self.assertEqual(case_state, expected_case_state)
        self.assertEqual(analysis_context, expected_analysis_context)

    async def test_provider_failure_does_not_mutate_nested_inputs(self) -> None:
        case_state, analysis_context = _case_inputs()
        expected_case_state = deepcopy(case_state)
        expected_analysis_context = deepcopy(analysis_context)

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(503, json={"error": "unavailable"})
            )
        ) as client:
            with (
                patch(
                    "app.services.case_analysis.service.resolve_core_llm_target",
                    return_value=_target(),
                ),
                self.assertRaises(CaseAnalysisFailure) as raised,
            ):
                await MainCaseAnalysisService(client=client).analyze(
                    mode="question_answer",
                    case_state_json=case_state,
                    analysis_context=analysis_context,
                    question="What does the current analysis support?",
                )

        self.assertEqual(raised.exception.code, "analysis_provider_error")
        self.assertEqual(case_state, expected_case_state)
        self.assertEqual(analysis_context, expected_analysis_context)

    async def test_case_overview_uses_deterministic_overview_task(self) -> None:
        case_state, analysis_context = _case_inputs()

        def respond(request: httpx.Request) -> httpx.Response:
            request_payload = json.loads(request.content)
            prompt = request_payload["messages"][0]["content"]
            system_prompt = request_payload["system"]
            self.assertIn("TRUST HIERARCHY", system_prompt)
            self.assertIn("Do not retrieve new information", system_prompt)
            self.assertIn("ANALYSIS MODE: case_overview", system_prompt)
            self.assertIn("five short sections in this order", system_prompt)
            self.assertIn('"analysis_mode":"case_overview"', prompt)
            self.assertIn('"question":null', prompt)
            return httpx.Response(
                200,
                json={
                    "content": [
                        {"type": "text", "text": "Bounded main case analysis."}
                    ],
                    "stop_reason": "end_turn",
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(respond)
        ) as client:
            with patch(
                "app.services.case_analysis.service.resolve_core_llm_target",
                return_value=_target(),
            ):
                answer = await MainCaseAnalysisService(client=client).analyze(
                    mode="case_overview",
                    case_state_json=case_state,
                    analysis_context=analysis_context,
                    question=None,
                )

        self.assertEqual(answer, "Bounded main case analysis.")

    async def test_openrouter_output_text_block_is_accepted(self) -> None:
        case_state, analysis_context = _case_inputs()

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={
                        "content": [
                            {"type": "redacted_thinking", "data": "omitted"},
                            {"type": "output_text", "text": "Output-text analysis."},
                        ],
                        "stop_reason": "end_turn",
                    },
                )
            )
        ) as client:
            with patch(
                "app.services.case_analysis.service.resolve_core_llm_target",
                return_value=_target(),
            ):
                answer = await MainCaseAnalysisService(client=client).analyze(
                    mode="case_overview",
                    case_state_json=case_state,
                    analysis_context=analysis_context,
                    question=None,
                )

        self.assertEqual(answer, "Output-text analysis.")

    async def test_openai_choices_envelope_is_accepted(self) -> None:
        case_state, analysis_context = _case_inputs()

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={
                        "choices": [
                            {
                                "message": {
                                    "role": "assistant",
                                    "content": "Choices-envelope analysis.",
                                },
                                "finish_reason": "stop",
                            }
                        ]
                    },
                )
            )
        ) as client:
            with patch(
                "app.services.case_analysis.service.resolve_core_llm_target",
                return_value=_target(),
            ):
                answer = await MainCaseAnalysisService(client=client).analyze(
                    mode="case_overview",
                    case_state_json=case_state,
                    analysis_context=analysis_context,
                    question=None,
                )

        self.assertEqual(answer, "Choices-envelope analysis.")

    async def test_success_error_envelope_is_classified_as_provider_error(self) -> None:
        case_state, analysis_context = _case_inputs()

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={
                        "type": "error",
                        "error": {
                            "type": "api_error",
                            "error_type": "provider_overloaded",
                        },
                    },
                )
            )
        ) as client:
            with (
                patch(
                    "app.services.case_analysis.service.resolve_core_llm_target",
                    return_value=_target(),
                ),
                self.assertRaises(CaseAnalysisFailure) as raised,
            ):
                await MainCaseAnalysisService(client=client).analyze(
                    mode="case_overview",
                    case_state_json=case_state,
                    analysis_context=analysis_context,
                    question=None,
                )

        self.assertEqual(raised.exception.code, "analysis_provider_error")

    def test_analysis_mode_literal_is_exported(self) -> None:
        self.assertEqual(
            get_args(AnalysisMode),
            ("case_overview", "question_answer"),
        )

    def test_invalid_mode_and_question_combinations_fail_stably(self) -> None:
        case_state, analysis_context = _case_inputs()
        invalid_requests = (
            ("unsupported", None),
            ("question_answer", None),
            ("question_answer", "   "),
            ("case_overview", "Do not accept this question"),
        )

        for mode, question in invalid_requests:
            with (
                self.subTest(mode=mode, question=question),
                self.assertRaises(CaseAnalysisFailure) as raised,
            ):
                build_case_analysis_prompt(
                    mode=mode,  # type: ignore[arg-type]
                    case_state_json=case_state,
                    analysis_context=analysis_context,
                    question=question,
                )
            self.assertEqual(raised.exception.code, "analysis_invalid_request")

    def test_oversized_question_answer_retains_exact_mode_and_question(self) -> None:
        exact_question = "  Which exact host is supported by this case?  "
        with patch.object(settings, "chat_ask_max_input_chars", 480):
            prompt = build_case_analysis_prompt(
                mode="question_answer",
                case_state_json={"case_summary": "case " * 1_000},
                analysis_context={"retrieved_context": "context " * 1_000},
                question=exact_question,
            )

        serialized = prompt.split("<case_context_json>\n", 1)[1].split(
            "\n</case_context_json>",
            1,
        )[0]
        payload = json.loads(serialized)
        self.assertLessEqual(len(prompt), 480)
        self.assertEqual(payload["analysis_mode"], "question_answer")
        self.assertEqual(payload["question"], exact_question)
        self.assertTrue(payload["context_truncated"])
        self.assertTrue(payload["case_state"]["truncated"])
        self.assertTrue(payload["analysis_context"]["truncated"])


if __name__ == "__main__":
    unittest.main()
