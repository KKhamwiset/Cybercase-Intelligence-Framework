"""Unit tests for the OpenRouter model registry and alias resolver."""

import pytest
from app.services.llm.model_registry import (
    DEFAULT_OPENROUTER_MODEL,
    CURATED_MODEL_PRESETS,
    format_model_table,
    list_available_models,
    resolve_openrouter_model,
)


def test_default_model():
    assert DEFAULT_OPENROUTER_MODEL == "openai/gpt-oss-120b"
    assert resolve_openrouter_model(None) == DEFAULT_OPENROUTER_MODEL
    assert resolve_openrouter_model("") == DEFAULT_OPENROUTER_MODEL
    assert resolve_openrouter_model("default") == DEFAULT_OPENROUTER_MODEL


@pytest.mark.parametrize(
    ("alias", "expected_canonical_id"),
    [
        ("gpt-oss-120b", "openai/gpt-oss-120b"),
        ("gpt-oss", "openai/gpt-oss-120b"),
        ("oss-120b", "openai/gpt-oss-120b"),
        ("oss", "openai/gpt-oss-120b"),
        ("sonnet", "anthropic/claude-3.5-sonnet"),
        ("claude-sonnet", "anthropic/claude-3.5-sonnet"),
        ("claude-3.5-sonnet", "anthropic/claude-3.5-sonnet"),
        ("haiku", "anthropic/claude-3.5-haiku"),
        ("claude-haiku", "anthropic/claude-3.5-haiku"),
        ("luna", "openai/gpt-5.6-luna"),
        ("gpt-luna", "openai/gpt-5.6-luna"),
        ("4o", "openai/gpt-4o"),
        ("gpt-4o", "openai/gpt-4o"),
    ],
)
def test_curated_aliases_resolution(alias: str, expected_canonical_id: str):
    assert resolve_openrouter_model(alias) == expected_canonical_id
    assert resolve_openrouter_model(alias.upper()) == expected_canonical_id
    assert resolve_openrouter_model(f"openrouter/{alias}") == expected_canonical_id


def test_custom_model_passthrough():
    custom = "mistralai/mistral-large-2411"
    assert resolve_openrouter_model(custom) == custom
    assert resolve_openrouter_model(f"openrouter/{custom}") == custom


def test_list_and_table_formatting():
    models = list_available_models()
    assert len(models) == len(CURATED_MODEL_PRESETS)
    default_entry = next(m for m in models if m["canonical_id"] == DEFAULT_OPENROUTER_MODEL)
    assert default_entry["is_default"] is True

    table = format_model_table()
    assert "CYBERCASE OPENROUTER MODEL REGISTRY" in table
    assert "openai/gpt-oss-120b" in table
    assert "[DEFAULT]" in table
