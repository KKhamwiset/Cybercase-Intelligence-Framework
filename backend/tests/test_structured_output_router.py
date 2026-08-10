import unittest
from typing import cast
from unittest.mock import patch

import httpx
from pydantic import BaseModel

from app.services.chat.core_llm import CoreLlmProvider, CoreLlmTarget
from app.services.chat.llm_extraction import AnthropicExtractionAdapter
from app.services.chat.report_generation import AnthropicReportAdapter
from app.services.chat.structured_output_router import structured_output_schema


class _NestedSchema(BaseModel):
    name: str
    optional_note: str | None = None


class _EnvelopeSchema(BaseModel):
    nested: _NestedSchema
    optional_nested: _NestedSchema | None = None


class _CaptureAsyncClient:
    def __init__(self, **_: object) -> None:
        self.request_payload: dict[str, object] | None = None

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
        self.request_payload = json
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "{}"}],
                "usage": {},
            },
        )


def _target(provider: CoreLlmProvider) -> CoreLlmTarget:
    return CoreLlmTarget(
        provider=provider,
        model="test-model",
        api_key="test-key",
        base_url="https://example.test",
        messages_url="https://example.test/messages",
        headers={"Authorization": "Bearer test-key"},
    )


class StructuredOutputRouterTests(unittest.IsolatedAsyncioTestCase):
    def test_anthropic_preserves_optional_properties(self) -> None:
        schema = structured_output_schema(_EnvelopeSchema, provider="anthropic")

        self.assertEqual(schema["required"], ["nested"])
        nested_schema = schema["$defs"]["_NestedSchema"]
        self.assertEqual(nested_schema["required"], ["name"])
        self.assertIn("anyOf", nested_schema["properties"]["optional_note"])

    def test_openrouter_requires_every_property_recursively(self) -> None:
        schema = structured_output_schema(_EnvelopeSchema, provider="openrouter")

        self._assert_all_object_properties_required(schema)
        nested_schema = schema["$defs"]["_NestedSchema"]
        self.assertIn("anyOf", nested_schema["properties"]["optional_note"])
        self.assertIs(nested_schema["additionalProperties"], False)

    def test_unknown_provider_is_rejected_without_fallback(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported core LLM provider"):
            structured_output_schema(
                _EnvelopeSchema,
                provider=cast(CoreLlmProvider, "other"),
            )

    async def test_extraction_adapter_routes_openrouter_schema(self) -> None:
        client = _CaptureAsyncClient()
        with (
            patch(
                "app.services.chat.llm_extraction.resolve_core_llm_target",
                return_value=_target("openrouter"),
            ),
            patch(
                "app.services.chat.llm_extraction.httpx.AsyncClient",
                return_value=client,
            ),
        ):
            await AnthropicExtractionAdapter().complete(
                system_prompt="system",
                input_payload={},
                model="feature-model",
                max_output_tokens=32,
            )

        schema = self._captured_schema(client)
        self._assert_all_object_properties_required(schema)

    async def test_report_adapter_routes_anthropic_schema(self) -> None:
        client = _CaptureAsyncClient()
        with (
            patch(
                "app.services.chat.report_generation.resolve_core_llm_target",
                return_value=_target("anthropic"),
            ),
            patch(
                "app.services.chat.report_generation.httpx.AsyncClient",
                return_value=client,
            ),
        ):
            await AnthropicReportAdapter().complete(
                system_prompt="system",
                input_payload={},
                model="feature-model",
                max_output_tokens=32,
                temperature=0.0,
            )

        schema = self._captured_schema(client)
        self.assertNotEqual(
            schema["required"],
            list(schema["properties"].keys()),
        )
        self.assertIn("anyOf", schema["properties"]["claims"]["items"])
        self._assert_schema_keys_absent(schema, {"oneOf", "discriminator"})

    async def test_report_adapter_routes_openrouter_provider_claim_schema(
        self,
    ) -> None:
        client = _CaptureAsyncClient()
        with (
            patch(
                "app.services.chat.report_generation.resolve_core_llm_target",
                return_value=_target("openrouter"),
            ),
            patch(
                "app.services.chat.report_generation.httpx.AsyncClient",
                return_value=client,
            ),
        ):
            await AnthropicReportAdapter().complete(
                system_prompt="system",
                input_payload={},
                model="feature-model",
                max_output_tokens=32,
                temperature=0.0,
            )

        schema = self._captured_schema(client)
        self._assert_all_object_properties_required(schema)
        self.assertIn("anyOf", schema["properties"]["claims"]["items"])
        self._assert_schema_keys_absent(schema, {"oneOf", "discriminator"})

    def _captured_schema(self, client: _CaptureAsyncClient) -> dict[str, object]:
        assert client.request_payload is not None
        output_config = client.request_payload["output_config"]
        assert isinstance(output_config, dict)
        output_format = output_config["format"]
        assert isinstance(output_format, dict)
        schema = output_format["schema"]
        assert isinstance(schema, dict)
        return schema

    def _assert_all_object_properties_required(self, value: object) -> None:
        if isinstance(value, dict):
            if value.get("type") == "object":
                properties = value.get("properties", {})
                self.assertIsInstance(properties, dict)
                assert isinstance(properties, dict)
                self.assertEqual(value.get("required"), list(properties.keys()))
                self.assertIs(value.get("additionalProperties"), False)
            for child in value.values():
                self._assert_all_object_properties_required(child)
        elif isinstance(value, list):
            for child in value:
                self._assert_all_object_properties_required(child)

    def _assert_schema_keys_absent(
        self,
        value: object,
        forbidden: set[str],
    ) -> None:
        if isinstance(value, dict):
            self.assertTrue(forbidden.isdisjoint(value))
            for child in value.values():
                self._assert_schema_keys_absent(child, forbidden)
        elif isinstance(value, list):
            for child in value:
                self._assert_schema_keys_absent(child, forbidden)


if __name__ == "__main__":
    unittest.main()
