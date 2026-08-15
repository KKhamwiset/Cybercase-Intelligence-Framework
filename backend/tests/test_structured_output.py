import unittest
from unittest.mock import patch

import httpx

from app.config import settings
from app.schemas.chat.reports import StructuredReport
from app.services.extraction.llm_extraction import (
    AnthropicExtractionAdapter,
    BaselineExtraction,
)
from app.services.reports.report_generation import (
    AnthropicReportAdapter,
    ReportProviderFailure,
)
from app.services.reports.report_provider_schema import ProviderStructuredReport
from app.services.llm.structured_output import anthropic_json_schema


_UNSUPPORTED_KEYS = {
    "exclusiveMaximum",
    "exclusiveMinimum",
    "maxItems",
    "maxLength",
    "maxProperties",
    "maximum",
    "minItems",
    "minLength",
    "minProperties",
    "minimum",
    "multipleOf",
    "pattern",
    "uniqueItems",
    "default",
}


class _CaptureAsyncClient:
    def __init__(
        self,
        *,
        response_json: dict[str, object] | None = None,
        **_: object,
    ) -> None:
        self.request_payload: dict[str, object] | None = None
        self.request_url: str | None = None
        self.request_headers: dict[str, str] | None = None
        self.response_json = response_json or {
            "content": [{"type": "text", "text": "{}"}],
            "usage": {},
        }

    async def __aenter__(self) -> "_CaptureAsyncClient":
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
        self.request_url = url
        self.request_headers = headers
        self.request_payload = json
        return httpx.Response(
            200,
            json=self.response_json,
        )


class StructuredOutputSchemaTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.original_provider = settings.core_llm_provider
        self.original_api_key = settings.anthropic_api_key
        self.original_openrouter_key = settings.openrouter_cybercase
        settings.core_llm_provider = "anthropic"
        settings.anthropic_api_key = "test-key"

    def tearDown(self) -> None:
        settings.core_llm_provider = self.original_provider
        settings.anthropic_api_key = self.original_api_key
        settings.openrouter_cybercase = self.original_openrouter_key

    def test_report_schema_removes_provider_unsupported_constraints(self) -> None:
        schema = anthropic_json_schema(StructuredReport)

        self._assert_provider_schema(schema)
        self.assertIn("$defs", schema)
        self.assertEqual(
            schema["properties"]["report_version"]["const"],
            "baseline_report_v1",
        )

    def test_extraction_schema_preserves_supported_formats_and_any_of(self) -> None:
        schema = anthropic_json_schema(BaselineExtraction)

        self._assert_provider_schema(schema)
        self.assertIn("anyOf", schema["$defs"]["ExtractedTimelineEvent"]["properties"]["timestamp"])
        self.assertEqual(
            schema["$defs"]["ExtractedEntity"]["properties"]["source_message_ids"]["items"]["format"],
            "uuid",
        )

    async def test_extraction_adapter_sends_normalized_schema(self) -> None:
        client = _CaptureAsyncClient()
        with patch(
            "app.services.extraction.llm_extraction.httpx.AsyncClient",
            return_value=client,
        ):
            await AnthropicExtractionAdapter().complete(
                system_prompt="system",
                input_payload={},
                model="test-model",
                max_output_tokens=32,
            )

        assert client.request_payload is not None
        schema = client.request_payload["output_config"]["format"]["schema"]
        self._assert_provider_schema(schema)
        self.assertNotIn("maxItems", str(schema))

    async def test_extraction_adapter_uses_openrouter_messages_contract(self) -> None:
        settings.core_llm_provider = "openrouter"
        settings.openrouter_cybercase = "openrouter-test-key"
        client = _CaptureAsyncClient()
        with patch(
            "app.services.extraction.llm_extraction.httpx.AsyncClient",
            return_value=client,
        ):
            await AnthropicExtractionAdapter().complete(
                system_prompt="system",
                input_payload={},
                model="claude-feature-model",
                max_output_tokens=32,
            )

        self.assertEqual(
            client.request_url,
            "https://openrouter.ai/api/v1/messages",
        )
        self.assertEqual(
            client.request_headers,
            {
                "Authorization": "Bearer openrouter-test-key",
                "anthropic-version": "2023-06-01",
            },
        )
        assert client.request_payload is not None
        self.assertEqual(
            client.request_payload["model"],
            "deepseek/deepseek-v4-flash-0731",
        )
        self.assertIn("output_config", client.request_payload)

    async def test_report_adapter_sends_normalized_schema(self) -> None:
        client = _CaptureAsyncClient()
        with patch(
            "app.services.reports.report_generation.httpx.AsyncClient",
            return_value=client,
        ):
            await AnthropicReportAdapter().complete(
                system_prompt="system",
                input_payload={},
                model="test-model",
                max_output_tokens=32,
                temperature=0.0,
            )

        assert client.request_payload is not None
        schema = client.request_payload["output_config"]["format"]["schema"]
        self._assert_provider_schema(schema)
        self.assertNotIn("maxItems", str(schema))
        self.assertEqual(
            schema["properties"],
            anthropic_json_schema(ProviderStructuredReport)["properties"],
        )

    async def test_report_adapter_preserves_usage_for_output_limit(self) -> None:
        client = _CaptureAsyncClient(
            response_json={
                "stop_reason": "max_tokens",
                "content": [{"type": "text", "text": "partial"}],
                "usage": {"input_tokens": 111, "output_tokens": 32},
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
                    model="test-model",
                    max_output_tokens=32,
                    temperature=0.0,
                )

        self.assertEqual(context.exception.code, "report_output_limit")
        self.assertEqual(context.exception.input_tokens, 111)
        self.assertEqual(context.exception.output_tokens, 32)

    async def test_report_adapter_distinguishes_refusal(self) -> None:
        client = _CaptureAsyncClient(
            response_json={
                "stop_reason": "refusal",
                "content": [],
                "usage": {"input_tokens": 23, "output_tokens": 0},
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
                    model="test-model",
                    max_output_tokens=32,
                    temperature=0.0,
                )

        self.assertEqual(context.exception.code, "report_refusal")
        self.assertEqual(context.exception.input_tokens, 23)
        self.assertEqual(context.exception.output_tokens, 0)

    def _assert_provider_schema(self, schema: object) -> None:
        if isinstance(schema, dict):
            self.assertTrue(_UNSUPPORTED_KEYS.isdisjoint(schema))
            if schema.get("type") == "object":
                self.assertIs(schema.get("additionalProperties"), False)
            for value in schema.values():
                self._assert_provider_schema(value)
        elif isinstance(schema, list):
            for value in schema:
                self._assert_provider_schema(value)


if __name__ == "__main__":
    unittest.main()
