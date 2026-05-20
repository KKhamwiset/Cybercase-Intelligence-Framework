"""
Ground Truth Dataset
=====================
Data model and I/O for evaluation datasets.

Each sample has:
  - query: the user question (English or Thai)
  - relevant_stix_ids: STIX IDs that should be retrieved
  - reference_answer: optional gold-standard answer for generation eval
  - language: "en" or "th"
  - category: query type (technique_lookup, relationship, group, etc.)
"""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


@dataclass
class EvalSample:
    """A single evaluation sample."""
    query: str
    relevant_stix_ids: list[str]
    reference_answer: str = ""
    language: str = "en"
    category: str = "general"

    def has_reference_answer(self) -> bool:
        return bool(self.reference_answer.strip())


def load_ground_truth(path: str | Path) -> list[EvalSample]:
    """Load evaluation samples from a JSON file.

    Expected format:
    [
        {
            "query": "What is Phishing?",
            "relevant_stix_ids": ["attack-pattern--a62a8db3-..."],
            "reference_answer": "Phishing is...",
            "language": "en",
            "category": "technique_lookup"
        },
        ...
    ]
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Ground truth file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    samples = []
    for item in data:
        samples.append(
            EvalSample(
                query=item["query"],
                relevant_stix_ids=item["relevant_stix_ids"],
                reference_answer=item.get("reference_answer", ""),
                language=item.get("language", "en"),
                category=item.get("category", "general"),
            )
        )

    print(f"[EVAL] Loaded {len(samples)} evaluation samples from {path.name}")
    return samples


def save_ground_truth(samples: list[EvalSample], path: str | Path) -> None:
    """Save evaluation samples to a JSON file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = [asdict(s) for s in samples]

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"[EVAL] Saved {len(samples)} samples to {path.name}")
