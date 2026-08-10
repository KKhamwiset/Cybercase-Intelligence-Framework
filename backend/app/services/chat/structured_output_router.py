"""Route structured-output schemas to the selected core LLM provider."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel

from app.services.chat.core_llm import CoreLlmProvider
from app.services.chat.structured_output import anthropic_json_schema


def structured_output_schema(
    model: type[BaseModel],
    *,
    provider: CoreLlmProvider,
) -> dict[str, Any]:
    """Build the provider-specific structured-output schema for ``model``."""

    if provider == "anthropic":
        return anthropic_json_schema(model)
    if provider == "openrouter":
        schema = anthropic_json_schema(model)
        _require_all_object_properties(schema)
        return schema
    raise ValueError(f"Unsupported core LLM provider: {provider!r}")


def _require_all_object_properties(value: object) -> None:
    if isinstance(value, list):
        for item in value:
            _require_all_object_properties(item)
        return
    if not isinstance(value, dict):
        return

    for child in value.values():
        _require_all_object_properties(child)

    if value.get("type") != "object":
        return
    properties = value.get("properties", {})
    if not isinstance(properties, Mapping):
        raise TypeError("JSON Schema object properties must be a mapping")
    value["required"] = list(properties.keys())


__all__ = ["structured_output_schema"]
