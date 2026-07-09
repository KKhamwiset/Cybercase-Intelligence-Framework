"""
Export Alias / Tactic Lookup Tables from Neo4j
================================================
One-off export for attack_id_metrics.py:

  - alias_map            : lowercased technique name -> attack_id, used by
                           extract_technique_names() to credit answers that
                           name a technique without citing its ID
  - technique_to_tactics : attack_id -> tactic shortnames, used by
                           tactic_level_score()

Output: evaluation/data/attack_lookup.json

Usage:
    cd rag_service/app/RAG/GraphRAG
    python -m evaluation.export_alias_tables
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

# Fix relative imports when run directly
if __package__ is None or __package__ == "evaluation":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    __package__ = "GraphRAG.evaluation"

# UTF-8 fix for Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from neo4j import GraphDatabase

from ..config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

OUTPUT_PATH = Path(__file__).resolve().parent / "data" / "attack_lookup.json"

# Technique names that are also common English words — excluded from the
# alias map because whole-word matching on them produces false positives
# in ordinary prose (extract_technique_names docstring).
AMBIGUOUS_NAMES = {"proxy", "phishing", "masquerading", "rootkit", "at"}


def main() -> None:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    print(f"[EXPORT] Connected to Neo4j: {NEO4J_URI}")

    try:
        with driver.session() as session:
            technique_rows = [
                dict(r) for r in session.run(
                    """
                    MATCH (t)
                    WHERE (t:Technique OR t:Subtechnique) AND t.attack_id IS NOT NULL
                    RETURN t.attack_id AS attack_id, t.name AS name
                    """
                )
            ]
            tactic_rows = [
                dict(r) for r in session.run(
                    """
                    MATCH (t)-[:IN_TACTIC]->(tac:Tactic)
                    WHERE t.attack_id IS NOT NULL
                    RETURN t.attack_id AS attack_id,
                           collect(DISTINCT coalesce(tac.shortname, tac.name)) AS tactics
                    """
                )
            ]
    finally:
        driver.close()

    alias_map: dict[str, str] = {}
    skipped = 0
    for row in technique_rows:
        name = (row.get("name") or "").strip().lower()
        if not name or name in AMBIGUOUS_NAMES:
            skipped += 1
            continue
        alias_map[name] = row["attack_id"]

    technique_to_tactics = {
        row["attack_id"]: sorted(row["tactics"]) for row in tactic_rows
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {
                "alias_map": alias_map,
                "technique_to_tactics": technique_to_tactics,
            },
            f, indent=2, ensure_ascii=False,
        )

    print(f"[EXPORT] {len(alias_map)} aliases ({skipped} ambiguous/empty skipped)")
    print(f"[EXPORT] {len(technique_to_tactics)} technique->tactics entries")
    print(f"[EXPORT] Saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
