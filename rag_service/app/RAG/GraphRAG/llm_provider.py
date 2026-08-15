"""Production cloud LLM factory for Anthropic-compatible chat clients."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from langchain_anthropic import ChatAnthropic

from . import config


CoreLlmProvider = Literal["anthropic", "openrouter"]


class CoreLlmConfigurationError(RuntimeError):
    """The selected cloud provider cannot be constructed safely."""

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
    anthropic_model: str | None = None,
    *,
    require_key: bool = True,
) -> CoreLlmTarget:
    """Resolve the selected production provider without consulting eval keys."""

    provider = config.validate_core_llm_provider(config.CORE_LLM_PROVIDER)
    if provider == "openrouter":
        api_key = config.OPENROUTER_CYBERCASE.strip()
        if require_key and not api_key:
            raise CoreLlmConfigurationError("openrouter", "OPENROUTER_CYBERCASE")
        base_url = config.CORE_LLM_OPENROUTER_BASE_URL.rstrip("/")
        selected_model = (
            anthropic_model
            if anthropic_model
            else config.CORE_LLM_OPENROUTER_MODEL
        )
        resolved_model = config.resolve_openrouter_model(selected_model)
        return CoreLlmTarget(
            provider="openrouter",
            model=resolved_model,
            api_key=api_key,
            base_url=base_url,
            messages_url=f"{base_url}/v1/messages",
            headers={
                "Authorization": f"Bearer {api_key}",
                "anthropic-version": "2023-06-01",
            },
        )

    api_key = config.ANTHROPIC_API_KEY.strip()
    if require_key and not api_key:
        raise CoreLlmConfigurationError("anthropic", "ANTHROPIC_API_KEY")
    base_url = config.CORE_LLM_ANTHROPIC_BASE_URL.rstrip("/")
    return CoreLlmTarget(
        provider="anthropic",
        model=anthropic_model or config.CORE_LLM_ANTHROPIC_MODEL,
        api_key=api_key,
        base_url=base_url,
        messages_url=f"{base_url}/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )


def create_core_chat_model(
    *,
    anthropic_model: str | None = None,
    temperature: float | int,
    max_tokens: int,
) -> ChatAnthropic:
    """Create one cloud ChatAnthropic client for the selected provider."""

    target = resolve_core_llm_target(anthropic_model)
    effective_max_tokens = (
        max(max_tokens, 4096)
        if target.provider == "openrouter"
        else max_tokens
    )
    kwargs: dict[str, object] = {
        "model_name": target.model,
        "api_key": target.api_key,
        "temperature": temperature,
        "max_tokens_to_sample": effective_max_tokens,
    }
    if target.provider == "openrouter":
        kwargs["base_url"] = target.base_url
        kwargs["default_headers"] = {
            "Authorization": f"Bearer {target.api_key}",
        }
    return ChatAnthropic(**kwargs)  # type: ignore[arg-type]


__all__ = [
    "CoreLlmConfigurationError",
    "CoreLlmProvider",
    "CoreLlmTarget",
    "create_core_chat_model",
    "resolve_core_llm_target",
]
