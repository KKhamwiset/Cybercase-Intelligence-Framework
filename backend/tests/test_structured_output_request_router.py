import json
import unittest
from typing import cast
from unittest.mock import patch

import httpx

from app.config import settings
from app.services.llm.core_llm import CoreLlmProvider
from app.services.llm.structured_output_request_router import (
    StructuredOutputFeature,
    structured_output_request_options,
)
from app.services.chat.followup_policy import AnthropicFollowUpPolicy
from app.services.extraction.llm_extraction import (
    AnthropicExtractionAdapter,
    ExtractionFailure,
)
from app.services.reports.report_generation import (
    AnthropicReportAdapter,
    ReportProviderFailure,
)


class _RecordingAsyncClient:
    def __init__(self, response_json: dict[str, object], **_: object) -> None:
        self.response_json = response_json
        self.request_payload: dict[str, object] | None = None

    async def __aenter__(self) -> "_RecordingAsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> bool:
        return False

    async def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, object],
    ) -> httpx.Response:
        del headers
        self.request_payload = json
        return httpx.Response(
            200,
            json=self.response_json,
            request=httpx.Request("POST", url),
        )


def _text_response(text: str = "{}") -> dict[str, object]:
    return {
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": text}],
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


def _followup_response() -> dict[str, object]:
    return _text_response(
        json.dumps(
            {
                "action": "proceed",
                "question": "",
                "reason_code": "sufficient_case_context",
            }
        )
    )


class StructuredOutputRequestRouterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.original_settings = {
            "core_llm_provider": settings.core_llm_provider,
            "anthropic_api_key": settings.anthropic_api_key,
            "openrouter_cybercase": settings.openrouter_cybercase,
            "chat_followup_policy_max_output_tokens": (
                settings.chat_followup_policy_max_output_tokens
            ),
        }
        settings.anthropic_api_key = "anthropic-test-key"
        settings.openrouter_cybercase = "openrouter-test-key"
        settings.chat_followup_policy_max_output_tokens = 128

    def tearDown(self) -> None:
        for name, value in self.original_settings.items():
            setattr(settings, name, value)

    def test_anthropic_preserves_configured_options_exactly(self) -> None:
        self.assertEqual(
            structured_output_request_options(
                provider="anthropic",
                feature="followup",
                configured_max_tokens=128,
            ),
            {"max_tokens": 128},
        )
        self.assertEqual(
            structured_output_request_options(
                provider="anthropic",
                feature="extraction",
                configured_max_tokens=2_048,
            ),
            {"max_tokens": 2_048},
        )
        self.assertEqual(
            structured_output_request_options(
                provider="anthropic",
                feature="report",
                configured_max_tokens=8_192,
                temperature=0.0,
            ),
            {"max_tokens": 8_192, "temperature": 0.0},
        )

    def test_openrouter_applies_feature_floors_and_omits_temperature(
        self,
    ) -> None:
        self.assertEqual(
            structured_output_request_options(
                provider="openrouter",
                feature="followup",
                configured_max_tokens=128,
            ),
            {"max_tokens": 2_048},
        )
        self.assertEqual(
            structured_output_request_options(
                provider="openrouter",
                feature="extraction",
                configured_max_tokens=2_048,
            ),
            {"max_tokens": 8_192},
        )
        self.assertEqual(
            structured_output_request_options(
                provider="openrouter",
                feature="report",
                configured_max_tokens=8_192,
                temperature=0.0,
            ),
            {"max_tokens": 16_384},
        )
        self.assertEqual(
            structured_output_request_options(
                provider="openrouter",
                feature="report",
                configured_max_tokens=20_000,
                temperature=0.0,
            ),
            {"max_tokens": 20_000},
        )

    def test_unknown_provider_or_feature_raises_without_fallback(self) -> None:
        with self.assertRaises(ValueError):
            structured_output_request_options(
                provider=cast(CoreLlmProvider, "unknown"),
                feature="extraction",
                configured_max_tokens=2_048,
            )
        with self.assertRaises(ValueError):
            structured_output_request_options(
                provider="anthropic",
                feature=cast(StructuredOutputFeature, "unknown"),
                configured_max_tokens=2_048,
            )

    async def test_anthropic_call_sites_keep_existing_budgets(self) -> None:
        settings.core_llm_provider = "anthropic"

        followup_client = _RecordingAsyncClient(_followup_response())
        await AnthropicFollowUpPolicy().decide(
            original_user_content="Reported suspicious sign-in.",
            clarification_exchanges=(),
            client=followup_client,
        )
        assert followup_client.request_payload is not None
        self.assertEqual(followup_client.request_payload["max_tokens"], 128)
        self.assertNotIn("temperature", followup_client.request_payload)
        self.assertNotIn("reasoning", followup_client.request_payload)

        extraction_client = _RecordingAsyncClient(_text_response())
        with patch(
            "app.services.extraction.llm_extraction.httpx.AsyncClient",
            return_value=extraction_client,
        ):
            await AnthropicExtractionAdapter().complete(
                system_prompt="system",
                input_payload={},
                model="anthropic-extraction-model",
                max_output_tokens=2_048,
            )
        assert extraction_client.request_payload is not None
        self.assertEqual(extraction_client.request_payload["max_tokens"], 2_048)
        self.assertNotIn("temperature", extraction_client.request_payload)
        self.assertNotIn("reasoning", extraction_client.request_payload)

        report_client = _RecordingAsyncClient(_text_response())
        with patch(
            "app.services.reports.report_generation.httpx.AsyncClient",
            return_value=report_client,
        ):
            await AnthropicReportAdapter().complete(
                system_prompt="system",
                input_payload={},
                model="anthropic-report-model",
                max_output_tokens=8_192,
                temperature=0.0,
            )
        assert report_client.request_payload is not None
        self.assertEqual(report_client.request_payload["max_tokens"], 8_192)
        self.assertEqual(report_client.request_payload["temperature"], 0.0)
        self.assertNotIn("reasoning", report_client.request_payload)

    async def test_openrouter_followup_and_report_call_sites_keep_floors(
        self,
    ) -> None:
        settings.core_llm_provider = "openrouter"

        followup_client = _RecordingAsyncClient(_followup_response())
        await AnthropicFollowUpPolicy().decide(
            original_user_content="Reported suspicious sign-in.",
            clarification_exchanges=(),
            client=followup_client,
        )
        assert followup_client.request_payload is not None
        self.assertEqual(followup_client.request_payload["max_tokens"], 2_048)
        self.assertNotIn("temperature", followup_client.request_payload)
        self.assertNotIn("reasoning", followup_client.request_payload)

        report_client = _RecordingAsyncClient(_text_response())
        with patch(
            "app.services.reports.report_generation.httpx.AsyncClient",
            return_value=report_client,
        ):
            await AnthropicReportAdapter().complete(
                system_prompt="system",
                input_payload={},
                model="anthropic-report-model",
                max_output_tokens=8_192,
                temperature=0.0,
            )
        assert report_client.request_payload is not None
        self.assertEqual(report_client.request_payload["max_tokens"], 16_384)
        self.assertNotIn("temperature", report_client.request_payload)
        self.assertNotIn("reasoning", report_client.request_payload)

    async def test_openrouter_extraction_call_site_uses_8192_floor(self) -> None:
        settings.core_llm_provider = "openrouter"
        extraction_client = _RecordingAsyncClient(_text_response())

        with patch(
            "app.services.extraction.llm_extraction.httpx.AsyncClient",
            return_value=extraction_client,
        ):
            await AnthropicExtractionAdapter().complete(
                system_prompt="system",
                input_payload={},
                model="anthropic-extraction-model",
                max_output_tokens=2_048,
            )

        assert extraction_client.request_payload is not None
        self.assertEqual(extraction_client.request_payload["max_tokens"], 8_192)
        self.assertNotIn("temperature", extraction_client.request_payload)
        self.assertNotIn("reasoning", extraction_client.request_payload)

    async def test_extraction_safe_stop_failures_preserve_usage(self) -> None:
        settings.core_llm_provider = "openrouter"
        secret = "raw-provider-content-must-not-leak"

        for stop_reason, expected_code in (
            ("refusal", "extraction_refusal"),
            ("max_tokens", "extraction_output_limit"),
            ("length", "extraction_output_limit"),
        ):
            with self.subTest(stop_reason=stop_reason):
                client = _RecordingAsyncClient(
                    {
                        "stop_reason": stop_reason,
                        "content": [{"type": "text", "text": secret}],
                        "usage": {"input_tokens": 321, "output_tokens": 8_192},
                    }
                )
                with patch(
                    "app.services.extraction.llm_extraction.httpx.AsyncClient",
                    return_value=client,
                ):
                    with self.assertRaises(ExtractionFailure) as context:
                        await AnthropicExtractionAdapter().complete(
                            system_prompt="system",
                            input_payload={},
                            model="anthropic-extraction-model",
                            max_output_tokens=2_048,
                        )

                failure = context.exception
                self.assertEqual(failure.code, expected_code)
                self.assertEqual(failure.input_tokens, 321)
                self.assertEqual(failure.output_tokens, 8_192)
                self.assertIsNone(failure.raw_response)
                self.assertNotIn(secret, str(failure))

    async def test_report_length_stop_is_an_output_limit_with_usage(self) -> None:
        settings.core_llm_provider = "openrouter"
        client = _RecordingAsyncClient(
            {
                "stop_reason": "length",
                "content": [{"type": "text", "text": "partial"}],
                "usage": {"input_tokens": 456, "output_tokens": 16_384},
            }
        )
        with patch(
            "app.services.reports.report_generation.httpx.AsyncClient",
            return_value=client,
        ):
            with self.assertRaises(ReportProviderFailure) as context:
                await AnthropicReportAdapter().complete(
                    system_prompt="system",
                    input_payload={},
                    model="anthropic-report-model",
                    max_output_tokens=8_192,
                    temperature=0.0,
                )

        self.assertEqual(context.exception.code, "report_output_limit")
        self.assertEqual(context.exception.input_tokens, 456)
        self.assertEqual(context.exception.output_tokens, 16_384)


if __name__ == "__main__":
    unittest.main()
