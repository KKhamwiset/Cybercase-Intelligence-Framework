"""Resolve the single production chat LLM provider without fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.config import Settings, settings
from app.services.llm.model_registry import resolve_openrouter_model


CoreLlmProvider = Literal["anthropic", "openrouter"]


class CoreLlmConfigurationError(RuntimeError):
    """The selected production provider is missing required configuration."""

    def __init__(self, provider: CoreLlmProvider, key_env_name: str) -> None:
        super().__init__(
            f"CORE_LLM_PROVIDER={provider} requires {key_env_name}; "
            "no automatic provider fallback is configured"
        )
        self.provider = provider
        self.key_env_name = key_env_name


@dataclass(frozen=True)
class CoreLlmTarget:
    provider: CoreLlmProvider
    model: str
    api_key: str
    base_url: str
    messages_url: str
    headers: dict[str, str]


def resolve_core_llm_target(
    feature_anthropic_model: str,
    *,
    require_key: bool = True,
    configured_settings: Settings | None = None,
) -> CoreLlmTarget:
    """Return the exact selected target for an Anthropic-format feature call."""

    active_settings = configured_settings or settings
    provider = active_settings.core_llm_provider
    if provider == "openrouter":
        api_key = active_settings.openrouter_cybercase.strip()
        if require_key and not api_key:
            raise CoreLlmConfigurationError("openrouter", "OPENROUTER_CYBERCASE")
        selected_model = (
            feature_anthropic_model
            if feature_anthropic_model
            else active_settings.core_llm_openrouter_model
        )
        resolved_model = resolve_openrouter_model(selected_model)
        return CoreLlmTarget(
            provider="openrouter",
            model=resolved_model,
            api_key=api_key,
            base_url=active_settings.openrouter_base_url.rstrip("/"),
            messages_url=active_settings.openrouter_messages_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "anthropic-version": "2023-06-01",
            },
        )

    api_key = active_settings.anthropic_api_key.strip()
    if require_key and not api_key:
        raise CoreLlmConfigurationError("anthropic", "ANTHROPIC_API_KEY")
    return CoreLlmTarget(
        provider="anthropic",
        model=feature_anthropic_model,
        api_key=api_key,
        base_url="https://api.anthropic.com",
        messages_url=active_settings.anthropic_messages_url,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )


__all__ = [
    "CoreLlmConfigurationError",
    "CoreLlmProvider",
    "CoreLlmTarget",
    "resolve_core_llm_target",
]
