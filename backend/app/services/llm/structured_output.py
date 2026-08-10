"""Provider-facing JSON Schema helpers for structured model output."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel


_ANTHROPIC_UNSUPPORTED_SCHEMA_KEYS = frozenset(
    {
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
)
_ANTHROPIC_SUPPORTED_STRING_FORMATS = frozenset(
    {
        "date-time",
        "time",
        "date",
        "duration",
        "email",
        "hostname",
        "uri",
        "ipv4",
        "ipv6",
        "uuid",
    }
)


def anthropic_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Build an Anthropic-compatible schema without weakening local validation.

    Pydantic's full schema remains the source of truth for response validation.
    This copy only removes JSON Schema constraints unsupported by Anthropic's
    structured-output grammar and closes object schemas recursively.
    """

    normalized = _normalize_schema(model.model_json_schema())
    if not isinstance(normalized, dict):
        raise TypeError("Pydantic model schema must be a JSON object")
    return normalized


def _normalize_schema(value: object) -> object:
    if isinstance(value, list):
        return [_normalize_schema(item) for item in value]
    if not isinstance(value, Mapping):
        return value

    normalized: dict[str, Any] = {}
    for key, child in value.items():
        key_text = str(key)
        if key_text in _ANTHROPIC_UNSUPPORTED_SCHEMA_KEYS:
            continue
        if key_text == "format" and child not in _ANTHROPIC_SUPPORTED_STRING_FORMATS:
            continue
        normalized[key_text] = _normalize_schema(child)

    if normalized.get("type") == "object":
        normalized["additionalProperties"] = False
    return normalized


__all__ = ["anthropic_json_schema"]
