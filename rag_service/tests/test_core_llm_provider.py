import ast
import sys
from pathlib import Path
from types import ModuleType

import pytest

from RAG.GraphRAG import config
from RAG.GraphRAG import llm_provider
from RAG.GraphRAG.llm_provider import CoreLlmConfigurationError


PIPELINE_FILES = (
    "agent_graph.py",
    "chain.py",
    "cross_lingual.py",
    "evaluator.py",
    "query_decomposer.py",
    "router.py",
)


def test_default_provider_and_openrouter_target(monkeypatch: pytest.MonkeyPatch) -> None:
    assert config.CORE_LLM_PROVIDER == "openrouter"
    monkeypatch.setattr(config, "CORE_LLM_PROVIDER", "openrouter")
    monkeypatch.setattr(config, "OPENROUTER_CYBERCASE", "core-secret")
    monkeypatch.setattr(config, "CORE_LLM_OPENROUTER_MODEL", "openai/gpt-5.6-luna")

    target = llm_provider.resolve_core_llm_target("claude-feature-model")

    assert target.provider == "openrouter"
    assert target.model == "openai/gpt-5.6-luna"
    assert target.messages_url == "https://openrouter.ai/api/v1/messages"
    assert target.headers["Authorization"] == "Bearer core-secret"
    assert "x-api-key" not in target.headers


def test_explicit_anthropic_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "CORE_LLM_PROVIDER", "anthropic")
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "anthropic-secret")

    target = llm_provider.resolve_core_llm_target("claude-feature-model")

    assert target.provider == "anthropic"
    assert target.model == "claude-feature-model"
    assert target.messages_url == "https://api.anthropic.com/v1/messages"
    assert target.headers["x-api-key"] == "anthropic-secret"
    assert "Authorization" not in target.headers


def test_invalid_selector_is_rejected() -> None:
    with pytest.raises(ValueError, match="anthropic.*openrouter"):
        config.validate_core_llm_provider("invalid")


def test_missing_selected_key_does_not_fallback_to_other_or_evaluation_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "CORE_LLM_PROVIDER", "openrouter")
    monkeypatch.setattr(config, "OPENROUTER_CYBERCASE", "")
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "available-but-not-selected")
    monkeypatch.setattr(config, "OPENROUTER_API_KEY", "evaluation-only")

    with pytest.raises(CoreLlmConfigurationError, match="OPENROUTER_CYBERCASE"):
        llm_provider.resolve_core_llm_target("claude-feature-model")


@pytest.mark.parametrize(
    ("provider", "expected_model", "has_openrouter_headers"),
    (
        ("openrouter", "openai/gpt-5.6-luna", True),
        ("anthropic", "claude-feature-model", False),
    ),
)
def test_factory_constructs_selected_client(
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    expected_model: str,
    has_openrouter_headers: bool,
) -> None:
    captured: dict[str, object] = {}

    class FakeChatAnthropic:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(config, "CORE_LLM_PROVIDER", provider)
    monkeypatch.setattr(config, "OPENROUTER_CYBERCASE", "core-secret")
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "anthropic-secret")
    monkeypatch.setattr(llm_provider, "ChatAnthropic", FakeChatAnthropic)

    llm_provider.create_core_chat_model(
        anthropic_model="claude-feature-model",
        temperature=0,
        max_tokens=128,
    )

    assert captured["model_name"] == expected_model
    if has_openrouter_headers:
        assert captured["base_url"] == "https://openrouter.ai/api"
        assert captured["default_headers"] == {
            "Authorization": "Bearer core-secret"
        }
    else:
        assert "base_url" not in captured
        assert "default_headers" not in captured


def test_local_mode_takes_precedence_over_cloud_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from RAG.GraphRAG.pipeline import router

    fake_ollama_module = ModuleType("langchain_ollama")

    class FakeChatOllama:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    fake_ollama_module.ChatOllama = FakeChatOllama  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "langchain_ollama", fake_ollama_module)

    def fail_cloud_factory(**kwargs: object) -> None:
        raise AssertionError(f"cloud factory called in local mode: {kwargs}")

    monkeypatch.setattr(router, "create_core_chat_model", fail_cloud_factory)

    instance = router.QueryRouter(use_local=True)

    assert isinstance(instance.llm, FakeChatOllama)


def test_all_production_pipeline_modules_use_central_factory() -> None:
    pipeline_dir = (
        Path(__file__).parents[1] / "app" / "RAG" / "GraphRAG" / "pipeline"
    )

    for filename in PIPELINE_FILES:
        source = (pipeline_dir / filename).read_text(encoding="utf-8")
        tree = ast.parse(source)
        called_names = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert "ChatAnthropic" not in called_names, filename
        assert "create_core_chat_model" in called_names, filename
