"""Provider-aware request options for structured-output LLM calls."""

from __future__ import annotations

from typing import Literal

from app.services.llm.core_llm import CoreLlmProvider


StructuredOutputFeature = Literal["followup", "extraction", "report"]

_OPENROUTER_OUTPUT_TOKEN_FLOORS: dict[StructuredOutputFeature, int] = {
    "followup": 2_048,
    "extraction": 8_192,
    "report": 16_384,
}


def structured_output_request_options(
    *,
    provider: CoreLlmProvider,
    feature: StructuredOutputFeature,
    configured_max_tokens: int,
    temperature: float | None = None,
) -> dict[str, object]:
    """Return only the provider-specific structured-output request options."""

    if feature not in _OPENROUTER_OUTPUT_TOKEN_FLOORS:
        raise ValueError(f"Unsupported structured-output feature: {feature!r}")

    if provider == "anthropic":
        options: dict[str, object] = {"max_tokens": configured_max_tokens}
        if temperature is not None:
            options["temperature"] = temperature
        return options

    if provider == "openrouter":
        return {
            "max_tokens": max(
                configured_max_tokens,
                _OPENROUTER_OUTPUT_TOKEN_FLOORS[feature],
            )
        }

    raise ValueError(f"Unsupported core LLM provider: {provider!r}")


__all__ = [
    "StructuredOutputFeature",
    "structured_output_request_options",
]
