"""Central OpenRouter model registry, curated presets, and alias resolver for Backend services."""

from __future__ import annotations

from dataclasses import dataclass


DEFAULT_OPENROUTER_MODEL = "openai/gpt-oss-120b"


@dataclass(frozen=True)
class ModelPreset:
    canonical_id: str
    display_name: str
    family: str
    aliases: tuple[str, ...]
    description: str


CURATED_MODEL_PRESETS: tuple[ModelPreset, ...] = (
    ModelPreset(
        canonical_id="openai/gpt-oss-120b",
        display_name="GPT-OSS 120B",
        family="GPT-OSS",
        aliases=("gpt-oss-120b", "gpt-oss", "oss-120b", "oss", "default"),
        description="Open-weight 120B reasoning and structured extraction model (Default)",
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
    _ALIAS_MAP[preset.canonical_id.lower()] = preset.canonical_id
    for alias in preset.aliases:
        _ALIAS_MAP[alias.lower().strip()] = preset.canonical_id


def resolve_openrouter_model(model_name_or_alias: str | None) -> str:
    """Resolve an alias or model name to its canonical OpenRouter model string."""
    if not model_name_or_alias or not model_name_or_alias.strip():
        return DEFAULT_OPENROUTER_MODEL

    cleaned = model_name_or_alias.strip()
    if cleaned.lower().startswith("openrouter/"):
        cleaned = cleaned[len("openrouter/"):]

    lookup_key = cleaned.lower()
    if lookup_key in _ALIAS_MAP:
        return _ALIAS_MAP[lookup_key]

    if "/" in cleaned:
        return cleaned

    # Fallback to default if unknown alias
    return DEFAULT_OPENROUTER_MODEL


def list_available_models() -> list[dict[str, object]]:
    """Return catalog list of all curated ready-selection models with their metadata."""
    catalog = []
    for p in CURATED_MODEL_PRESETS:
        catalog.append(
            {
                "canonical_id": p.canonical_id,
                "display_name": p.display_name,
                "family": p.family,
                "primary_alias": p.aliases[0],
                "all_aliases": list(p.aliases),
                "description": p.description,
                "is_default": p.canonical_id == DEFAULT_OPENROUTER_MODEL,
            }
        )
    return catalog


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
    lines.append("  python -m RAG.GraphRAG.main --model oss             (Default: openai/gpt-oss-120b)")
    lines.append("  python -m RAG.GraphRAG.main --model sonnet          (anthropic/claude-3.5-sonnet)")
    lines.append("  python -m RAG.GraphRAG.main --model haiku           (anthropic/claude-3.5-haiku)")
    lines.append("  python -m RAG.GraphRAG.main --model luna            (openai/gpt-5.6-luna)")
    lines.append("  python -m RAG.GraphRAG.main --model 4o              (openai/gpt-4o)")
    lines.append("  python -m RAG.GraphRAG.main --model <vendor>/<id>   (Any custom OpenRouter model ID)")
    lines.append("=" * 95)
    return "\n".join(lines)
