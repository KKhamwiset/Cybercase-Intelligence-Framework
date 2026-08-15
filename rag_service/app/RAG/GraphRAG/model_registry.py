"""Central OpenRouter model registry, curated presets, and alias resolver for GraphRAG."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


DEFAULT_OPENROUTER_MODEL = "qwen/qwen3.8-27b"


@dataclass(frozen=True)
class ModelPreset:
    canonical_id: str
    display_name: str
    family: str
    aliases: tuple[str, ...]
    description: str


# Curated ready-selection catalog
CURATED_MODEL_PRESETS: tuple[ModelPreset, ...] = (
    ModelPreset(
        canonical_id="qwen/qwen3.8-27b",
        display_name="Qwen 3.8 27B",
        family="Qwen",
        aliases=("qwen", "qwen-27b", "qwen3.8", "qwen3.8-27b", "default"),
        description="Multilingual and structured analysis open weights leader (Default)",
    ),
    ModelPreset(
        canonical_id="deepseek/deepseek-v4-flash-0731",
        display_name="DeepSeek V4 Flash",
        family="DeepSeek",
        aliases=("deepseek", "deepseek-flash", "deepseek-v4"),
        description="High-speed flash reasoning and threat analysis",
    ),
    ModelPreset(
        canonical_id="anthropic/claude-3.5-sonnet",
        display_name="Claude 3.5 Sonnet",
        family="Claude",
        aliases=("sonnet", "claude-sonnet", "claude-3.5-sonnet", "sonnet-3.5"),
        description="Frontier cyber reasoning and incident report generation",
    ),
    ModelPreset(
        canonical_id="anthropic/claude-3.5-haiku",
        display_name="Claude 3.5 Haiku",
        family="Claude",
        aliases=("haiku", "claude-haiku", "claude-3.5-haiku", "haiku-3.5"),
        description="Fast, token-efficient extraction and evaluation",
    ),
    ModelPreset(
        canonical_id="openai/gpt-5.6-luna",
        display_name="GPT 5.6 Luna",
        family="GPT",
        aliases=("luna", "gpt-luna", "gpt-5.6-luna"),
        description="High-context general analysis and extraction",
    ),
    ModelPreset(
        canonical_id="openai/gpt-4o",
        display_name="GPT-4o",
        family="GPT",
        aliases=("4o", "gpt-4o", "openai-4o"),
        description="Flagship multimodal OpenAI model",
    ),
)

_ALIAS_MAP: dict[str, str] = {}
for preset in CURATED_MODEL_PRESETS:
    # Map canonical id
    _ALIAS_MAP[preset.canonical_id.lower()] = preset.canonical_id
    # Map aliases
    for alias in preset.aliases:
        _ALIAS_MAP[alias.lower().strip()] = preset.canonical_id


def resolve_openrouter_model(name_or_alias: str | None) -> str:
    """Resolve a friendly model nickname, alias, or full ID to the canonical OpenRouter ID.

    If given None or empty string, returns DEFAULT_OPENROUTER_MODEL.
    If the name is not in the curated alias map but contains a '/', it passes through as a custom ID.
    """
    if not name_or_alias or not name_or_alias.strip():
        return DEFAULT_OPENROUTER_MODEL

    clean_name = name_or_alias.strip()
    if clean_name.lower().startswith("openrouter/"):
        clean_name = clean_name[len("openrouter/"):].strip()

    normalized = clean_name.lower()
    if normalized in _ALIAS_MAP:
        return _ALIAS_MAP[normalized]

    # Passthrough any explicit custom vendor/model identifier
    if "/" in clean_name:
        return clean_name

    # Fallback to default if unknown alias
    return DEFAULT_OPENROUTER_MODEL


def list_available_models() -> list[dict[str, object]]:
    """Return structured catalog of ready-selection models."""
    return [
        {
            "canonical_id": p.canonical_id,
            "display_name": p.display_name,
            "family": p.family,
            "aliases": list(p.aliases),
            "description": p.description,
            "is_default": p.canonical_id == DEFAULT_OPENROUTER_MODEL,
        }
        for p in CURATED_MODEL_PRESETS
    ]


def format_model_table() -> str:
    """Render formatted ASCII comparison table of curated ready-selection models."""
    lines = [
        "=" * 95,
        "CYBERCASE OPENROUTER MODEL REGISTRY — READY-SELECTION CATALOG",
        "=" * 95,
        f"{'Family':<10} | {'Primary Alias':<15} | {'OpenRouter Canonical ID':<35} | {'Default?':<10}",
        "-" * 95,
    ]
    for p in CURATED_MODEL_PRESETS:
        is_def = "[DEFAULT]" if p.canonical_id == DEFAULT_OPENROUTER_MODEL else ""
        lines.append(
            f"{p.family:<10} | {p.aliases[0]:<15} | {p.canonical_id:<35} | {is_def:<10}"
        )
    lines.append("=" * 95)
    lines.append("Usage Examples:")
    lines.append("  python -m RAG.GraphRAG.main --model qwen            (Default: qwen/qwen3.8-27b)")
    lines.append("  python -m RAG.GraphRAG.main --model deepseek        (deepseek/deepseek-v4-flash-0731)")
    lines.append("  python -m RAG.GraphRAG.main --model sonnet          (anthropic/claude-3.5-sonnet)")
    lines.append("  python -m RAG.GraphRAG.main --model haiku           (anthropic/claude-3.5-haiku)")
    lines.append("  python -m RAG.GraphRAG.main --model luna            (openai/gpt-5.6-luna)")
    lines.append("  python -m RAG.GraphRAG.main --model 4o              (openai/gpt-4o)")
    lines.append("  python -m RAG.GraphRAG.main --model <vendor>/<id>   (Any custom OpenRouter model ID)")
    lines.append("=" * 95)
    return "\n".join(lines)
