"""
Neo4j-Grounded Evaluation Dataset Generator
=============================================
Generates a validated evaluation dataset by querying Neo4j directly,
eliminating manual ground-truth labeling errors.

Core principle: The graph IS the ground truth. Every `relevant_stix_ids`
list is derived from a Cypher query against the same knowledge base the
retriever searches against.

Usage:
    cd backend/RAG/GraphRAG
    python -m evaluation.generate_eval_dataset
    python -m evaluation.generate_eval_dataset --output evaluation/eval_dataset.json
    python -m evaluation.generate_eval_dataset --validate-only --output evaluation/eval_dataset_generated.json

Problems solved:
    1. Under-labeling      → Cypher returns ALL matching IDs
    2. Contradictions       → reference_answer derived from same query results
    3. Empty ground truth   → Validator rejects samples with 0 IDs
    4. Small dataset (14)   → Template × node iteration → 80-120 samples
"""

from __future__ import annotations

import argparse
import json
import io
import random
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional, cast

# Fix relative imports when run directly
if __package__ is None or __package__ == "evaluation":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    __package__ = "GraphRAG.evaluation"

# UTF-8 fix for Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from neo4j import GraphDatabase, Query

from ..config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


# ══════════════════════════════════════════════════════════════════════════════
# DATA MODEL
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class GeneratedSample:
    """A single generated evaluation sample.

    Incident samples additionally carry:
      - query_en        : English parallel of the Thai query (variants B/E
                          of the generation benchmark need it)
      - gold_attack_ids : ATT&CK IDs for generation ID-F1 scoring
      - attack_steps    : ordered chronological steps, each
                          {order, cue, cue_type: named|described,
                           gold_attack_ids, gold_stix_ids} — retrieval is
                          scored per step (step-coverage@k), mirroring how
                          real Thai case files narrate attacks
                          chronologically with English technical terms.
    """
    query: str
    relevant_stix_ids: list[str]
    reference_answer: str = ""
    language: str = "en"
    category: str = "general"
    query_en: str = ""
    gold_attack_ids: list[str] = field(default_factory=list)
    attack_steps: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        # Keep legacy lookup samples compact — only emit the new fields
        # when they carry data.
        if not self.query_en:
            d.pop("query_en")
        if not self.gold_attack_ids:
            d.pop("gold_attack_ids")
        if not self.attack_steps:
            d.pop("attack_steps")
        return d


# ══════════════════════════════════════════════════════════════════════════════
# NEO4J CONNECTION
# ══════════════════════════════════════════════════════════════════════════════


class Neo4jGroundTruthBuilder:
    """Connects to Neo4j and runs Cypher queries for ground truth extraction."""

    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        print(f"[GEN] Connected to Neo4j: {NEO4J_URI}")

    def close(self):
        self.driver.close()

    def run_query(self, cypher: str, params: dict | None = None) -> list[dict]:
        """Execute a Cypher query and return results as list of dicts."""
        with self.driver.session() as session:
            result = session.run(Query(cast(Any, cypher)), parameters=params or {})
            return [dict(record) for record in result]

    # ── Seed Node Discovery ───────────────────────────────────────────────

    def get_top_techniques(self, limit: int = 15) -> list[dict]:
        """Find techniques with the most relationships (well-connected nodes)."""
        return self.run_query("""
            MATCH (t:Technique)-[r]-()
            WHERE t.is_subtechnique IS NULL OR t.is_subtechnique = false
            WITH t, count(r) AS degree
            ORDER BY degree DESC
            LIMIT $limit
            RETURN t.stix_id AS stix_id, t.name AS name,
                   t.attack_id AS attack_id, t.description AS description, degree
        """, {"limit": limit})

    def get_top_groups(self, limit: int = 12) -> list[dict]:
        """Find groups with the most USES relationships."""
        return self.run_query("""
            MATCH (g:Group)-[r:USES]-()
            WITH g, count(r) AS degree
            ORDER BY degree DESC
            LIMIT $limit
            RETURN g.stix_id AS stix_id, g.name AS name,
                   g.attack_id AS attack_id, degree
        """, {"limit": limit})

    def get_top_software(self, limit: int = 12) -> list[dict]:
        """Find software with the most USES relationships."""
        return self.run_query("""
            MATCH (s:Software)-[r:USES]-()
            WITH s, count(r) AS degree
            ORDER BY degree DESC
            LIMIT $limit
            RETURN s.stix_id AS stix_id, s.name AS name,
                   s.attack_id AS attack_id,
                   s.software_type AS software_type, degree
        """, {"limit": limit})

    def get_all_tactics(self) -> list[dict]:
        """Get all tactics."""
        return self.run_query("""
            MATCH (tac:Tactic)
            RETURN tac.stix_id AS stix_id, tac.name AS name,
                   tac.attack_id AS attack_id, tac.shortname AS shortname
            ORDER BY tac.name
        """)

    def get_groups_with_campaigns(self, limit: int = 8) -> list[dict]:
        """Find groups that have campaigns attributed to them."""
        return self.run_query("""
            MATCH (c:Campaign)-[:ATTRIBUTED_TO]->(g:Group)
            WITH g, count(c) AS campaign_count
            WHERE campaign_count >= 1
            ORDER BY campaign_count DESC
            LIMIT $limit
            RETURN g.stix_id AS stix_id, g.name AS name,
                   g.attack_id AS attack_id, campaign_count
        """, {"limit": limit})

    def get_techniques_with_detection(self, limit: int = 10) -> list[dict]:
        """Find techniques that have DataComponent detection links."""
        return self.run_query("""
            MATCH (dc:DataComponent)-[:DETECTS]->(t:Technique)
            WHERE t.is_subtechnique IS NULL OR t.is_subtechnique = false
            WITH t, count(dc) AS detect_count
            WHERE detect_count >= 2
            ORDER BY detect_count DESC
            LIMIT $limit
            RETURN t.stix_id AS stix_id, t.name AS name,
                   t.attack_id AS attack_id, detect_count
        """, {"limit": limit})

    def get_techniques_by_attack_ids(self, attack_ids: list[str]) -> dict[str, str]:
        """Return {attack_id: stix_id} for the given ATT&CK IDs (techniques + subtechniques).

        Label-constrained: legacy ATT&CK mitigations reuse technique IDs
        (e.g. a Mitigation node also carries attack_id T1064), so an
        unconstrained match can silently return the wrong entity's STIX ID.
        """
        results = self.run_query("""
            MATCH (n)
            WHERE (n:Technique OR n:Subtechnique) AND n.attack_id IN $ids
            RETURN n.attack_id AS attack_id, n.stix_id AS stix_id
        """, {"ids": attack_ids})
        return {
            r["attack_id"]: r["stix_id"]
            for r in results
            if r.get("stix_id") and r.get("attack_id")
        }


# ══════════════════════════════════════════════════════════════════════════════
# QUERY TEMPLATE REGISTRY
# ══════════════════════════════════════════════════════════════════════════════


class QueryTemplateRegistry:
    """Defines evaluation query templates that map to Cypher traversal patterns."""

    def __init__(self, neo4j: Neo4jGroundTruthBuilder):
        self.neo4j = neo4j

    # ── 1. Mitigation Lookup ──────────────────────────────────────────────

    def generate_mitigation_lookup(self, technique: dict) -> GeneratedSample | None:
        """'What mitigations exist for [technique]?' → MITIGATES relationship."""
        stix_id = technique["stix_id"]
        name = technique["name"]
        attack_id = technique.get("attack_id", "")
        tech_desc = technique.get("description") or ""
        tech_desc_short = tech_desc[:300].rstrip() + ("..." if len(tech_desc) > 300 else "")

        results = self.neo4j.run_query("""
            MATCH (t:Technique {stix_id: $stix_id})<-[:MITIGATES]-(m)
            RETURN m.stix_id AS stix_id, m.name AS name,
                   m.attack_id AS attack_id, m.description AS description
        """, {"stix_id": stix_id})

        if not results:
            return None

        relevant_ids = [stix_id] + [r["stix_id"] for r in results]

        mit_parts = []
        for r in results:
            label = f"{r['name']} ({r['attack_id']})" if r.get("attack_id") else r["name"]
            mit_desc = (r.get("description") or "")[:150].rstrip()
            if mit_desc:
                mit_parts.append(f"{label}: {mit_desc}")
            else:
                mit_parts.append(label)

        mit_detail = "; ".join(mit_parts)

        intro = f"{name} ({attack_id}) is a MITRE ATT&CK technique"
        if tech_desc_short:
            intro += f" — {tech_desc_short}"
        intro += "."

        return GeneratedSample(
            query=f"What mitigations exist for {name}?",
            relevant_stix_ids=relevant_ids,
            reference_answer=(
                f"{intro} "
                f"Recommended mitigations include: {mit_detail}. "
                f"Implementing these controls reduces the risk of adversaries successfully "
                f"executing {name} against your environment."
            ),
            language="en",
            category="mitigation_lookup",
        )

    # ── 2. Technique Lookup ───────────────────────────────────────────────

    def generate_technique_lookup(self, technique: dict) -> GeneratedSample | None:
        """'What is [technique] ([ATT&CK ID])?' → node + subtechniques + description."""
        stix_id = technique["stix_id"]
        name = technique["name"]
        attack_id = technique.get("attack_id", "")
        description = technique.get("description") or ""
        desc_short = description[:500].rstrip() + ("..." if len(description) > 500 else "")

        results = self.neo4j.run_query("""
            MATCH (sub:Subtechnique)-[:SUBTECHNIQUE_OF]->(t:Technique {stix_id: $stix_id})
            RETURN sub.stix_id AS stix_id, sub.name AS name, sub.attack_id AS attack_id
        """, {"stix_id": stix_id})

        # Also fetch tactic memberships for richer context
        tactic_results = self.neo4j.run_query("""
            MATCH (t:Technique {stix_id: $stix_id})-[:IN_TACTIC]->(tac:Tactic)
            RETURN tac.name AS tactic_name
        """, {"stix_id": stix_id})

        relevant_ids = [stix_id] + [r["stix_id"] for r in results]

        parts = [f"{name} ({attack_id}) is an adversary technique in the MITRE ATT&CK framework."]

        if tactic_results:
            tactic_names = ", ".join(r["tactic_name"] for r in tactic_results if r.get("tactic_name"))
            if tactic_names:
                parts.append(f"It belongs to the {tactic_names} tactic(s).")

        if desc_short:
            parts.append(desc_short)

        if results:
            sub_names = [f"{r['name']} ({r['attack_id']})" for r in results if r.get("attack_id")]
            sub_list = ", ".join(sub_names) if sub_names else ", ".join(r["name"] for r in results)
            parts.append(f"Sub-techniques include: {sub_list}.")

        return GeneratedSample(
            query=f"What is {name} ({attack_id})?",
            relevant_stix_ids=relevant_ids,
            reference_answer=" ".join(parts),
            language="en",
            category="technique_lookup",
        )

    # ── 3. Group Software ─────────────────────────────────────────────────

    def generate_group_software(self, group: dict) -> GeneratedSample | None:
        """'What tools and malware does [group] use?' → USES→Software."""
        stix_id = group["stix_id"]
        name = group["name"]

        results = self.neo4j.run_query("""
            MATCH (g:Group {stix_id: $stix_id})-[:USES]->(s:Software)
            RETURN s.stix_id AS stix_id, s.name AS name,
                   s.attack_id AS attack_id, s.software_type AS software_type
        """, {"stix_id": stix_id})

        if not results:
            return None

        relevant_ids = [stix_id] + [r["stix_id"] for r in results]

        tools = [r for r in results if r.get("software_type") == "tool"]
        malware = [r for r in results if r.get("software_type") == "malware"]

        parts = []
        if tools:
            tool_names = ", ".join(f"{r['name']} ({r['attack_id']})" for r in tools if r.get("attack_id"))
            if tool_names:
                parts.append(f"Tools: {tool_names}")
        if malware:
            mal_names = ", ".join(f"{r['name']} ({r['attack_id']})" for r in malware if r.get("attack_id"))
            if mal_names:
                parts.append(f"Malware: {mal_names}")

        if not parts:
            sw_names = ", ".join(r["name"] for r in results)
            parts.append(f"Software: {sw_names}")

        return GeneratedSample(
            query=f"What tools and malware does {name} use?",
            relevant_stix_ids=relevant_ids,
            reference_answer=(
                f"{name} ({group.get('attack_id', '')}) uses the following software: "
                + "; ".join(parts) + "."
            ),
            language="en",
            category="group_software",
        )

    # ── 4. Group Techniques ───────────────────────────────────────────────

    def generate_group_techniques(self, group: dict) -> GeneratedSample | None:
        """'What techniques does [group] use?' → USES→Technique."""
        stix_id = group["stix_id"]
        name = group["name"]

        # No LIMIT: ground truth must be complete ("the graph IS the ground
        # truth"). Large gold sets are handled by capped recall@k, not by
        # truncating the answer key.
        results = self.neo4j.run_query("""
            MATCH (g:Group {stix_id: $stix_id})-[:USES]->(t:Technique)
            RETURN t.stix_id AS stix_id, t.name AS name, t.attack_id AS attack_id
        """, {"stix_id": stix_id})

        if not results:
            return None

        relevant_ids = [stix_id] + [r["stix_id"] for r in results]
        tech_names = ", ".join(
            f"{r['name']} ({r['attack_id']})" for r in results if r.get("attack_id")
        )
        if not tech_names:
            tech_names = ", ".join(r["name"] for r in results)

        return GeneratedSample(
            query=f"What techniques does {name} use?",
            relevant_stix_ids=relevant_ids,
            reference_answer=(
                f"{name} ({group.get('attack_id', '')}) uses the following techniques: "
                f"{tech_names}."
            ),
            language="en",
            category="group_techniques",
        )

    # ── 5. Tactic Techniques ──────────────────────────────────────────────

    def generate_tactic_techniques(self, tactic: dict) -> GeneratedSample | None:
        """'What are all [tactic] techniques?' → IN_TACTIC relationship."""
        stix_id = tactic["stix_id"]
        name = tactic["name"]

        results = self.neo4j.run_query("""
            MATCH (t:Technique)-[:IN_TACTIC]->(tac:Tactic {stix_id: $stix_id})
            WHERE t.is_subtechnique IS NULL OR t.is_subtechnique = false
            RETURN t.stix_id AS stix_id, t.name AS name, t.attack_id AS attack_id
        """, {"stix_id": stix_id})

        if not results:
            return None

        relevant_ids = [stix_id] + [r["stix_id"] for r in results]
        tech_names = ", ".join(
            f"{r['name']} ({r['attack_id']})" for r in results if r.get("attack_id")
        )
        if not tech_names:
            tech_names = ", ".join(r["name"] for r in results)

        return GeneratedSample(
            query=f"What are all {name} techniques?",
            relevant_stix_ids=relevant_ids,
            reference_answer=(
                f"{name} techniques include: {tech_names}. "
                f"These are part of the {name} tactic in the MITRE ATT&CK framework."
            ),
            language="en",
            category="tactic_techniques",
        )

    # ── 6. Software Techniques ────────────────────────────────────────────

    def generate_software_techniques(self, software: dict) -> GeneratedSample | None:
        """'What techniques does [software] use?' → USES→Technique."""
        stix_id = software["stix_id"]
        name = software["name"]

        results = self.neo4j.run_query("""
            MATCH (s:Software {stix_id: $stix_id})-[:USES]->(t:Technique)
            RETURN t.stix_id AS stix_id, t.name AS name, t.attack_id AS attack_id
        """, {"stix_id": stix_id})

        if not results:
            return None

        relevant_ids = [stix_id] + [r["stix_id"] for r in results]
        tech_names = ", ".join(
            f"{r['name']} ({r['attack_id']})" for r in results if r.get("attack_id")
        )
        if not tech_names:
            tech_names = ", ".join(r["name"] for r in results)

        sw_type = software.get("software_type", "software")

        return GeneratedSample(
            query=f"What techniques does {name} use?",
            relevant_stix_ids=relevant_ids,
            reference_answer=(
                f"{name} ({software.get('attack_id', '')}) is a {sw_type} that uses "
                f"the following techniques: {tech_names}."
            ),
            language="en",
            category="software_techniques",
        )

    # ── 7. Technique Detection ────────────────────────────────────────────

    def generate_technique_detection(self, technique: dict) -> GeneratedSample | None:
        """'How can I detect [technique]?' → DETECTS relationship."""
        stix_id = technique["stix_id"]
        name = technique["name"]
        attack_id = technique.get("attack_id", "")

        results = self.neo4j.run_query("""
            MATCH (dc:DataComponent)-[:DETECTS]->(t:Technique {stix_id: $stix_id})
            OPTIONAL MATCH (ds:DataSource)-[:HAS_COMPONENT]->(dc)
            RETURN dc.stix_id AS dc_stix_id, dc.name AS dc_name,
                   ds.stix_id AS ds_stix_id, ds.name AS ds_name
        """, {"stix_id": stix_id})

        if not results:
            return None

        relevant_ids = [stix_id]
        dc_names = []
        for r in results:
            if r.get("dc_stix_id"):
                relevant_ids.append(r["dc_stix_id"])
                dc_names.append(r["dc_name"])
            if r.get("ds_stix_id"):
                relevant_ids.append(r["ds_stix_id"])

        # Deduplicate
        relevant_ids = list(dict.fromkeys(relevant_ids))
        dc_list = ", ".join(dict.fromkeys(dc_names))

        return GeneratedSample(
            query=f"How can I detect {name} ({attack_id})?",
            relevant_stix_ids=relevant_ids,
            reference_answer=(
                f"{name} ({attack_id}) can be detected using the following data components: "
                f"{dc_list}. Monitoring these data sources helps identify adversary activity "
                f"related to this technique."
            ),
            language="en",
            category="technique_detection",
        )

    # ── 8. Technique Groups ───────────────────────────────────────────────

    def generate_technique_groups(self, technique: dict) -> GeneratedSample | None:
        """'What groups use [technique]?' → Group-USES→Technique."""
        stix_id = technique["stix_id"]
        name = technique["name"]
        attack_id = technique.get("attack_id", "")

        results = self.neo4j.run_query("""
            MATCH (g:Group)-[:USES]->(t:Technique {stix_id: $stix_id})
            RETURN g.stix_id AS stix_id, g.name AS name, g.attack_id AS attack_id
        """, {"stix_id": stix_id})

        if not results:
            return None

        relevant_ids = [stix_id] + [r["stix_id"] for r in results]
        group_names = ", ".join(
            f"{r['name']} ({r['attack_id']})" for r in results if r.get("attack_id")
        )
        if not group_names:
            group_names = ", ".join(r["name"] for r in results)

        return GeneratedSample(
            query=f"What threat groups use {name} ({attack_id})?",
            relevant_stix_ids=relevant_ids,
            reference_answer=(
                f"The following threat groups are known to use {name} ({attack_id}): "
                f"{group_names}."
            ),
            language="en",
            category="technique_groups",
        )

    # ── 10. Campaign Attribution ──────────────────────────────────────────

    def generate_campaign_attribution(self, group: dict) -> GeneratedSample | None:
        """'What campaigns are attributed to [group]?' → ATTRIBUTED_TO relationship."""
        stix_id = group["stix_id"]
        name = group["name"]

        results = self.neo4j.run_query("""
            MATCH (c:Campaign)-[:ATTRIBUTED_TO]->(g:Group {stix_id: $stix_id})
            RETURN c.stix_id AS stix_id, c.name AS name, c.attack_id AS attack_id
        """, {"stix_id": stix_id})

        if not results:
            return None

        relevant_ids = [stix_id] + [r["stix_id"] for r in results]
        camp_names = ", ".join(
            f"{r['name']} ({r['attack_id']})" for r in results if r.get("attack_id")
        )
        if not camp_names:
            camp_names = ", ".join(r["name"] for r in results)

        return GeneratedSample(
            query=f"What campaigns are attributed to {name}?",
            relevant_stix_ids=relevant_ids,
            reference_answer=(
                f"The following campaigns are attributed to {name} "
                f"({group.get('attack_id', '')}): {camp_names}."
            ),
            language="en",
            category="campaign_attribution",
        )


# ══════════════════════════════════════════════════════════════════════════════
# THAI LANGUAGE VARIANTS
# ══════════════════════════════════════════════════════════════════════════════

# Deterministic Thai templates — no LLM needed
THAI_QUERY_TEMPLATES: dict[str, str] = {
    "mitigation_lookup": "มาตรการป้องกันสำหรับ {name} มีอะไรบ้าง?",
    "technique_lookup": "เทคนิค {name} ({attack_id}) คืออะไร?",
    "group_software": "กลุ่ม {name} ใช้เครื่องมือและมัลแวร์อะไรบ้าง?",
    "group_techniques": "กลุ่ม {name} ใช้เทคนิคอะไรบ้าง?",
    "tactic_techniques": "เทคนิคทั้งหมดใน {name} มีอะไรบ้าง?",
    "software_techniques": "{name} ใช้เทคนิคอะไรบ้าง?",
    "technique_detection": "จะตรวจจับ {name} ({attack_id}) ได้อย่างไร?",
    "technique_groups": "กลุ่มภัยคุกคามใดที่ใช้ {name} ({attack_id})?",
    "campaign_attribution": "แคมเปญใดบ้างที่เกี่ยวข้องกับ {name}?",
}

# Thai answer prefix templates
THAI_ANSWER_PREFIX: dict[str, str] = {
    "mitigation_lookup": "มาตรการป้องกันสำหรับ {name} ({attack_id}) ได้แก่: ",
    "technique_lookup": "{name} ({attack_id}) เป็นเทคนิคของผู้โจมตีในกรอบ MITRE ATT&CK ",
    "group_software": "{name} ({attack_id}) ใช้ซอฟต์แวร์ต่อไปนี้: ",
    "group_techniques": "{name} ({attack_id}) ใช้เทคนิคต่อไปนี้: ",
    "tactic_techniques": "เทคนิคใน {name} ได้แก่: ",
    "software_techniques": "{name} ({attack_id}) ใช้เทคนิคต่อไปนี้: ",
    "technique_detection": "{name} ({attack_id}) สามารถตรวจจับได้โดยใช้: ",
    "technique_groups": "กลุ่มภัยคุกคามที่ใช้ {name} ({attack_id}) ได้แก่: ",
    "campaign_attribution": "แคมเปญที่เกี่ยวข้องกับ {name} ({attack_id}) ได้แก่: ",
}


def _make_thai_variant(sample: GeneratedSample, seed_node: dict) -> GeneratedSample | None:
    """Create a Thai-language variant of an English sample."""
    category = sample.category
    if category not in THAI_QUERY_TEMPLATES:
        return None

    name = seed_node.get("name", "")
    attack_id = seed_node.get("attack_id", "")

    try:
        thai_query = THAI_QUERY_TEMPLATES[category].format(
            name=name, attack_id=attack_id
        )
    except (KeyError, IndexError):
        return None

    # Build a Thai reference answer by prepending Thai prefix to entity names
    if category in THAI_ANSWER_PREFIX:
        prefix = THAI_ANSWER_PREFIX[category].format(name=name, attack_id=attack_id)
        # Extract the entity list portion from the English answer
        # (reuse entity names as-is since they're proper nouns)
        en_answer = sample.reference_answer
        # Find text after the first colon if present
        colon_idx = en_answer.find(": ")
        if colon_idx != -1:
            entity_part = en_answer[colon_idx + 2:]
            thai_answer = prefix + entity_part
        else:
            thai_answer = prefix + en_answer
    else:
        thai_answer = sample.reference_answer

    return GeneratedSample(
        query=thai_query,
        relevant_stix_ids=sample.relevant_stix_ids.copy(),
        reference_answer=thai_answer,
        language="th",
        category=sample.category,
    )


# ══════════════════════════════════════════════════════════════════════════════
# INCIDENT SCENARIOS  (grounded via Neo4j ATT&CK ID → STIX ID lookup)
# ══════════════════════════════════════════════════════════════════════════════

# Each scenario: technique_ids (ATT&CK IDs to look up), Thai query, English query,
# Thai reference answer, English reference answer.
INCIDENT_SCENARIOS: list[dict] = [
    # ── Thai scenarios (bilingual: both th + en sample generated) ───────────
    {
        "technique_ids": ["T1566", "T1566.002", "T1078", "T1041", "T1114"],
        "query_th": (
            "บริษัทแห่งหนึ่งรายงานว่าข้อมูลลูกค้าทั้งหมดถูกขโมย "
            "พนักงาน HR ได้รับอีเมลอ้างว่ามาจากทีม IT ให้กดลิ้งก์เพื่อยืนยันตัวตน "
            "หลังจากกรอกรหัสผ่านบนหน้าเว็บที่ลิ้งก์พาไป "
            "พบว่ามีการล็อกอินจาก IP ต่างประเทศและข้อมูลลูกค้าหายไปทั้งหมด"
        ),
        "query_en": (
            "A company reported all customer data was stolen. "
            "An HR employee received an email claiming to be from IT, asking them to click a link "
            "and verify their identity. After entering their password on the linked page, "
            "logins from foreign IP addresses were detected and all customer data disappeared."
        ),
        "answer_th": (
            "จากการวิเคราะห์เหตุการณ์สามารถจับคู่กับ MITRE ATT&CK ได้ดังนี้\n\n"
            "Initial Access — Phishing: Spear Phishing Link (T1566.002): "
            "ผู้โจมตีส่งอีเมลหลอกลวงที่มีลิ้งก์ไปยังหน้าเว็บปลอมเพื่อ harvest credentials "
            "ตรงกับ T1566 (Phishing) sub-technique T1566.002 (Spear Phishing Link)\n\n"
            "Credential Access / Defense Evasion — Valid Accounts (T1078): "
            "เมื่อพนักงานกรอก username/password บนหน้าเว็บปลอม ผู้โจมตีได้ valid credentials "
            "และสามารถล็อกอินเข้าระบบได้โดยผ่านการตรวจสอบ authentication ปกติ\n\n"
            "Collection — Email Collection (T1114): "
            "ผู้โจมตีอาจเข้าถึงอีเมลของพนักงานเพื่อรวบรวมข้อมูลลับเพิ่มเติม ตรงกับ T1114\n\n"
            "Exfiltration — Exfiltration Over C2 Channel (T1041): "
            "การดึงข้อมูลลูกค้าออกไปผ่านช่องทาง command-and-control ตรงกับ T1041\n\n"
            "สรุป: การโจมตีรูปแบบ Credential Phishing มุ่งเป้าพนักงานเพื่อ bypass technical controls "
            "ผู้สืบสวนควรตรวจสอบ email server logs, authentication logs และ outbound network traffic"
        ),
        "answer_en": (
            "MITRE ATT&CK mapping for this incident:\n\n"
            "Initial Access — Phishing: Spear Phishing Link (T1566.002): "
            "Sending a phishing email with a link to a fake login page to harvest credentials matches T1566.002.\n\n"
            "Credential Access — Valid Accounts (T1078): "
            "The harvested credentials allowed the attacker to authenticate normally, bypassing security controls.\n\n"
            "Collection — Email Collection (T1114): "
            "Accessing the compromised employee's email to gather additional intelligence matches T1114.\n\n"
            "Exfiltration — Exfiltration Over C2 Channel (T1041): "
            "Exfiltrating all customer data via the attacker's C2 infrastructure matches T1041.\n\n"
            "Summary: Credential phishing bypassing technical controls through social engineering. "
            "Investigate email server logs, authentication logs, and outbound network traffic."
        ),
    },
    {
        "technique_ids": ["T1110", "T1110.001", "T1068", "T1486", "T1490"],
        "query_th": (
            "เซิร์ฟเวอร์ขององค์กรถูกโจมตีด้วยการลองรหัสผ่านอัตโนมัติหลายพันครั้งผ่าน SSH "
            "ผู้โจมตีสามารถเข้าสู่ระบบได้สำเร็จ จากนั้นใช้ช่องโหว่ใน kernel "
            "เพื่อยกระดับสิทธิ์เป็น root และสุดท้ายติดตั้ง ransomware "
            "ที่เข้ารหัสไฟล์ข้อมูลสำคัญทั้งหมดพร้อมเรียกค่าไถ่"
        ),
        "query_en": (
            "An organization's server was attacked with thousands of automated password attempts via SSH. "
            "The attacker successfully logged in, then exploited a kernel vulnerability "
            "to escalate privileges to root, and finally deployed ransomware "
            "that encrypted all important data files and demanded ransom."
        ),
        "answer_th": (
            "การวิเคราะห์ตาม MITRE ATT&CK:\n\n"
            "Initial Access — Brute Force: Password Guessing (T1110.001): "
            "การลองรหัสผ่านหลายพันครั้งอัตโนมัติผ่าน SSH ตรงกับ T1110 (Brute Force) "
            "sub-technique T1110.001 (Password Guessing)\n\n"
            "Privilege Escalation — Exploitation for Privilege Escalation (T1068): "
            "การใช้ช่องโหว่ใน kernel เพื่อยกระดับสิทธิ์จาก user ทั่วไปเป็น root ตรงกับ T1068\n\n"
            "Impact — Data Encrypted for Impact (T1486): "
            "การเข้ารหัสไฟล์ข้อมูลและเรียกค่าไถ่ตรงกับ T1486 (Data Encrypted for Impact)\n\n"
            "Impact — Inhibit System Recovery (T1490): "
            "ผู้โจมตี ransomware มักลบ shadow copies และ backup เพื่อป้องกันการกู้คืน ตรงกับ T1490\n\n"
            "สรุป: Ransomware attack ผ่าน SSH Brute Force และ privilege escalation "
            "ควรตรวจสอบ SSH authentication logs, kernel audit logs และสถานะ backup"
        ),
        "answer_en": (
            "MITRE ATT&CK mapping:\n\n"
            "Initial Access — Brute Force: Password Guessing (T1110.001): "
            "Automated password attempts against SSH match T1110.001.\n\n"
            "Privilege Escalation — Exploitation for Privilege Escalation (T1068): "
            "Exploiting a kernel vulnerability to escalate to root matches T1068.\n\n"
            "Impact — Data Encrypted for Impact (T1486): "
            "Encrypting files and demanding ransom matches T1486.\n\n"
            "Impact — Inhibit System Recovery (T1490): "
            "Ransomware attackers typically delete shadow copies and backups to prevent recovery, matching T1490.\n\n"
            "Summary: Ransomware attack via SSH brute force and privilege escalation. "
            "Investigate SSH authentication logs, kernel audit logs, and backup integrity."
        ),
    },
    {
        "technique_ids": ["T1566.001", "T1204.002", "T1059.005", "T1056.001", "T1041"],
        "query_th": (
            "ผู้บริหารระดับสูงได้รับอีเมลพร้อมไฟล์ Word แนบมาจากที่อยู่ที่ไม่รู้จัก "
            "เมื่อเปิดไฟล์และคลิก Enable Content ตามที่ระบุในเอกสาร "
            "โปรแกรมลึกลับถูกติดตั้งโดยอัตโนมัติ "
            "ต่อมาพบว่าเครื่องดังกล่าวบันทึก keystroke ทั้งหมดและส่งออกไปยังเซิร์ฟเวอร์ภายนอก"
        ),
        "query_en": (
            "A senior executive received an email with a Word document attachment from an unknown address. "
            "When they opened the file and clicked Enable Content as instructed in the document, "
            "an unknown program was automatically installed. "
            "Later it was found that the machine was logging all keystrokes and sending them to an external server."
        ),
        "answer_th": (
            "การวิเคราะห์ตาม MITRE ATT&CK:\n\n"
            "Initial Access — Spear Phishing Attachment (T1566.001): "
            "การส่งอีเมลพร้อมไฟล์แนบอันตรายไปยังผู้บริหารแบบ targeted ตรงกับ T1566.001\n\n"
            "Execution — User Execution: Malicious File (T1204.002): "
            "การที่ผู้ใช้คลิก Enable Content เพื่อรัน macro ตรงกับ T1204.002\n\n"
            "Execution — Command and Scripting Interpreter: Visual Basic (T1059.005): "
            "Macro ที่รันในเอกสาร Word คือ VBA script ตรงกับ T1059.005\n\n"
            "Collection — Input Capture: Keylogging (T1056.001): "
            "โปรแกรมที่ติดตั้งมาทำหน้าที่บันทึก keystroke ทุกตัวตรงกับ T1056.001\n\n"
            "Exfiltration — Exfiltration Over C2 Channel (T1041): "
            "การส่งข้อมูล keystroke ออกไปยังเซิร์ฟเวอร์ภายนอกตรงกับ T1041\n\n"
            "สรุป: Spear Phishing with malicious macro targeting executives เพื่อติดตั้ง keylogger "
            "ควรตรวจสอบ email logs, process creation logs และ outbound network connections"
        ),
        "answer_en": (
            "MITRE ATT&CK mapping:\n\n"
            "Initial Access — Spear Phishing Attachment (T1566.001): "
            "Targeted email with malicious document attachment to an executive matches T1566.001.\n\n"
            "Execution — User Execution: Malicious File (T1204.002): "
            "The user clicking 'Enable Content' to execute the macro matches T1204.002.\n\n"
            "Execution — Visual Basic (T1059.005): "
            "The Word macro itself is a VBA script, matching T1059.005.\n\n"
            "Collection — Input Capture: Keylogging (T1056.001): "
            "The installed program capturing all keystrokes matches T1056.001.\n\n"
            "Exfiltration — Exfiltration Over C2 Channel (T1041): "
            "Sending captured keystrokes to an external server matches T1041.\n\n"
            "Summary: Spear phishing with malicious macro to install a keylogger targeting executives. "
            "Investigate email logs, process creation logs, and outbound connections."
        ),
    },
    {
        "technique_ids": ["T1078", "T1133", "T1046", "T1083", "T1048.002"],
        "query_th": (
            "ข้อมูล credential ขององค์กรรั่วไหลจากเหตุการณ์ละเมิดข้อมูลก่อนหน้า "
            "ผู้โจมตีนำ credential เหล่านั้นมาเชื่อมต่อ VPN ขององค์กร "
            "เมื่อเข้าถึงเครือข่ายภายในได้แล้ว ทำการสำรวจระบบ ค้นหาไฟล์ที่มีคำว่า 'confidential' "
            "และดึงข้อมูลลับทางการค้าออกไปผ่าน HTTPS"
        ),
        "query_en": (
            "Corporate credentials leaked from a previous data breach. "
            "The attacker used them to connect to the corporate VPN. "
            "Once inside the network, they scanned systems, searched for files containing 'confidential', "
            "and exfiltrated trade secrets over HTTPS."
        ),
        "answer_th": (
            "การวิเคราะห์ตาม MITRE ATT&CK:\n\n"
            "Initial Access — External Remote Services (T1133) และ Valid Accounts (T1078): "
            "การใช้ credential ที่รั่วไหลเชื่อมต่อ VPN ตรงกับ T1133 ร่วมกับ T1078 "
            "ทำให้การเชื่อมต่อดูถูกกฎหมายและหลีกเลี่ยงการตรวจจับ\n\n"
            "Discovery — Network Service Discovery (T1046): "
            "การสำรวจเครือข่ายภายในเพื่อหาเป้าหมายตรงกับ T1046\n\n"
            "Discovery — File and Directory Discovery (T1083): "
            "การค้นหาไฟล์ที่มีคำว่า 'confidential' ตรงกับ T1083\n\n"
            "Exfiltration — Exfiltration Over Alternative Protocol (T1048.002): "
            "การส่งข้อมูลออกผ่าน HTTPS เพื่อหลีกเลี่ยง DLP ตรงกับ T1048.002 "
            "(Exfiltration Over Asymmetric Encrypted Non-C2 Protocol)\n\n"
            "สรุป: การโจมตีที่ใช้ประโยชน์จาก credential ที่รั่วไหลเพื่อเข้าถึงเครือข่ายอย่างถูกกฎหมาย "
            "ควรบังคับใช้ MFA และ monitoring สำหรับ VPN connections"
        ),
        "answer_en": (
            "MITRE ATT&CK mapping:\n\n"
            "Initial Access — External Remote Services (T1133) and Valid Accounts (T1078): "
            "Using leaked credentials to connect via VPN combines T1133 and T1078, making access appear legitimate.\n\n"
            "Discovery — Network Service Discovery (T1046): "
            "Scanning the internal network for systems matches T1046.\n\n"
            "Discovery — File and Directory Discovery (T1083): "
            "Searching for files containing 'confidential' matches T1083.\n\n"
            "Exfiltration — Exfiltration Over Alternative Protocol (T1048.002): "
            "Sending data over HTTPS to evade DLP detection matches T1048.002.\n\n"
            "Summary: Exploiting leaked credentials for legitimate network access. "
            "Enforce MFA and monitor VPN authentication patterns."
        ),
    },
    {
        "technique_ids": ["T1195.002", "T1543.003", "T1071.001", "T1102"],
        "query_th": (
            "ซอฟต์แวร์อัปเดตที่ได้รับจาก vendor ที่เชื่อถือได้ถูกพบว่ามีโค้ดอันตรายซ่อนอยู่ "
            "เมื่อองค์กรติดตั้งอัปเดตตามปกติ ระบบเริ่มเชื่อมต่อไปยังเซิร์ฟเวอร์ภายนอกโดยอัตโนมัติ "
            "และพบว่ามี Windows service ใหม่ถูกสร้างขึ้นในระบบ"
        ),
        "query_en": (
            "A software update from a trusted vendor was found to contain hidden malicious code. "
            "When the organization installed the routine update, systems automatically began "
            "connecting to external servers, and a new Windows service was found created in the system."
        ),
        "answer_th": (
            "การวิเคราะห์ตาม MITRE ATT&CK:\n\n"
            "Initial Access — Supply Chain Compromise: Compromise Software Supply Chain (T1195.002): "
            "การฝังโค้ดอันตรายใน software update จาก vendor ที่ถูกต้องตรงกับ T1195.002 "
            "เป็นการโจมตีที่ยากตรวจจับเพราะมาจากแหล่งที่น่าเชื่อถือ\n\n"
            "Persistence — Create or Modify System Process: Windows Service (T1543.003): "
            "การสร้าง Windows service ใหม่ในระบบเป็น persistence mechanism ตรงกับ T1543.003 "
            "ทำให้ malware ทำงานอัตโนมัติเมื่อระบบรีสตาร์ท\n\n"
            "Command and Control — Application Layer Protocol: Web Protocols (T1071.001): "
            "การเชื่อมต่อกับ C2 server ผ่าน HTTP/HTTPS ตรงกับ T1071.001\n\n"
            "Command and Control — Web Service (T1102): "
            "ผู้โจมตีอาจใช้ legitimate web services เป็น C2 infrastructure ตรงกับ T1102\n\n"
            "สรุป: Supply Chain Attack ผ่านการ compromise software update ของ vendor "
            "มีผลกระทบต่อทุกองค์กรที่ใช้ซอฟต์แวร์นั้น ควรตรวจสอบ code signing และ integrity verification"
        ),
        "answer_en": (
            "MITRE ATT&CK mapping:\n\n"
            "Initial Access — Supply Chain Compromise (T1195.002): "
            "Embedding malicious code in a legitimate vendor's software update matches T1195.002, "
            "a sophisticated attack that bypasses trust-based security controls.\n\n"
            "Persistence — Create or Modify System Process: Windows Service (T1543.003): "
            "Creating a new Windows service as a persistence mechanism matches T1543.003.\n\n"
            "Command and Control — Application Layer Protocol: Web Protocols (T1071.001): "
            "Connecting to C2 servers over HTTP/HTTPS matches T1071.001.\n\n"
            "Command and Control — Web Service (T1102): "
            "Using legitimate web services as C2 infrastructure matches T1102.\n\n"
            "Summary: Supply chain attack via vendor software compromise affecting all customers. "
            "Verify code signing and implement software integrity checking."
        ),
    },
    {
        "technique_ids": ["T1003", "T1003.001", "T1550.002", "T1078.002"],
        "query_th": (
            "ผู้โจมตีเข้าถึงเครื่องพนักงานทั่วไปได้ จากนั้นใช้เครื่องมือพิเศษดึง "
            "credential hash จาก Windows memory "
            "และนำ hash เหล่านั้นไปใช้เข้าถึงเซิร์ฟเวอร์อื่นในโดเมนโดยไม่ต้องรู้รหัสผ่านจริง "
            "จนกระทั่งได้สิทธิ์ Domain Administrator และยึดครองระบบทั้งหมด"
        ),
        "query_en": (
            "The attacker gained access to a regular employee's machine, then used a special tool "
            "to extract credential hashes from Windows memory. "
            "They used those hashes to access other domain servers without knowing actual passwords, "
            "eventually achieving Domain Administrator privileges and taking over the entire system."
        ),
        "answer_th": (
            "การวิเคราะห์ตาม MITRE ATT&CK:\n\n"
            "Credential Access — OS Credential Dumping: LSASS Memory (T1003.001): "
            "การใช้เครื่องมือ (เช่น Mimikatz) ดึง credential hash จาก LSASS process ตรงกับ T1003.001\n\n"
            "Lateral Movement — Use Alternate Authentication Material: Pass the Hash (T1550.002): "
            "การนำ NTLM hash ไปใช้ authenticate กับเซิร์ฟเวอร์อื่นโดยไม่รู้รหัสผ่านจริง "
            "ตรงกับ T1550.002 (Pass the Hash) เป็น technique ที่อันตรายมากใน Windows domain\n\n"
            "Privilege Escalation / Persistence — Valid Accounts: Domain Accounts (T1078.002): "
            "การได้มาซึ่งสิทธิ์ Domain Administrator ตรงกับ T1078.002 "
            "ทำให้ผู้โจมตีควบคุม Active Directory ทั้งหมดได้\n\n"
            "สรุป: Pass-the-Hash lateral movement ใช้ประโยชน์จาก Windows NTLM authentication "
            "ควรบังคับใช้ Credential Guard และ Protected Users security group"
        ),
        "answer_en": (
            "MITRE ATT&CK mapping:\n\n"
            "Credential Access — OS Credential Dumping: LSASS Memory (T1003.001): "
            "Using a tool (e.g., Mimikatz) to extract credential hashes from Windows LSASS memory matches T1003.001.\n\n"
            "Lateral Movement — Pass the Hash (T1550.002): "
            "Using NTLM hashes to authenticate to domain servers without the plaintext password matches T1550.002.\n\n"
            "Privilege Escalation — Valid Accounts: Domain Accounts (T1078.002): "
            "Achieving Domain Administrator privileges matches T1078.002, "
            "giving full Active Directory control.\n\n"
            "Summary: Pass-the-Hash lateral movement exploiting Windows NTLM authentication. "
            "Enforce Credential Guard and Protected Users security group."
        ),
    },
    {
        "technique_ids": ["T1190", "T1005", "T1041"],
        "query_th": (
            "เว็บแอปพลิเคชันขายสินค้าออนไลน์ของบริษัทถูกโจมตีผ่านช่องค้นหาสินค้า "
            "ผู้โจมตีส่งคำสั่ง SQL พิเศษเข้าไปในช่องค้นหา "
            "ทำให้สามารถเข้าถึงฐานข้อมูลโดยตรงและดึงข้อมูลบัตรเครดิตของลูกค้าออกมาได้ทั้งหมด"
        ),
        "query_en": (
            "A company's e-commerce web application was attacked through the product search field. "
            "The attacker injected special SQL commands into the search input, "
            "enabling direct database access and exfiltration of all customer credit card data."
        ),
        "answer_th": (
            "การวิเคราะห์ตาม MITRE ATT&CK:\n\n"
            "Initial Access — Exploit Public-Facing Application (T1190): "
            "การโจมตีผ่านช่องโหว่ SQL Injection ในเว็บแอปพลิเคชันสาธารณะตรงกับ T1190 "
            "เป็นช่องโหว่ OWASP Top 10 ที่พบบ่อยที่สุด\n\n"
            "Collection — Data from Local System (T1005): "
            "การเข้าถึงและดึงข้อมูลจากฐานข้อมูลโดยตรงผ่าน SQL Injection ตรงกับ T1005 "
            "ซึ่งรวมถึงข้อมูลที่เก็บในฐานข้อมูลของเซิร์ฟเวอร์\n\n"
            "Exfiltration — Exfiltration Over C2 Channel (T1041): "
            "การส่งข้อมูลบัตรเครดิตออกไปภายนอกตรงกับ T1041\n\n"
            "สรุป: SQL Injection ผ่านเว็บแอปพลิเคชัน นำไปสู่การเข้าถึงฐานข้อมูลและขโมยข้อมูลชำระเงิน "
            "ควรตรวจสอบ web application firewall logs และ database query logs "
            "พร้อมแจ้ง PDPA breach notification ภายใน 72 ชั่วโมง"
        ),
        "answer_en": (
            "MITRE ATT&CK mapping:\n\n"
            "Initial Access — Exploit Public-Facing Application (T1190): "
            "SQL Injection against a public-facing web application matches T1190, "
            "one of the most common OWASP Top 10 vulnerabilities.\n\n"
            "Collection — Data from Local System (T1005): "
            "Direct database access and data extraction via SQL Injection matches T1005.\n\n"
            "Exfiltration — Exfiltration Over C2 Channel (T1041): "
            "Sending extracted credit card data externally matches T1041.\n\n"
            "Summary: SQL Injection against a web application leading to database breach and payment data theft. "
            "Investigate WAF logs, database query logs, and file a PDPA breach notification within 72 hours."
        ),
    },
    {
        "technique_ids": ["T1052.001", "T1074.001", "T1567.002"],
        "query_th": (
            "พนักงานที่กำลังจะลาออกไปร่วมงานกับบริษัทคู่แข่ง "
            "ทำการคัดลอกสูตรผลิตภัณฑ์ลับและแผนธุรกิจลงใน USB drive หลายสัปดาห์ก่อนวันสุดท้าย "
            "และต่อมาพบว่าไฟล์เหล่านั้นถูกอัปโหลดไปยัง Google Drive ส่วนตัวของพนักงาน"
        ),
        "query_en": (
            "An employee preparing to join a competitor copied confidential product formulas "
            "and business plans to a USB drive several weeks before their last day, "
            "and those files were later found uploaded to the employee's personal Google Drive."
        ),
        "answer_th": (
            "การวิเคราะห์ตาม MITRE ATT&CK (Insider Threat):\n\n"
            "Exfiltration — Exfiltration over Physical Medium: USB Drive (T1052.001): "
            "การคัดลอกไฟล์ลงใน USB drive ตรงกับ T1052.001 "
            "เป็น technique ที่ใช้บ่อยในคดี insider threat เพราะหลีกเลี่ยง network monitoring\n\n"
            "Collection — Local Data Staging (T1074.001): "
            "การรวบรวมไฟล์จากหลายแหล่งก่อนการ exfiltrate ตรงกับ T1074.001 (Local Data Staging)\n\n"
            "Exfiltration — Exfiltration to Cloud Storage (T1567.002): "
            "การอัปโหลดไฟล์ไปยัง Google Drive ส่วนตัวตรงกับ T1567.002 "
            "ซึ่งหลีกเลี่ยง DLP ได้เพราะเป็น legitimate service\n\n"
            "สรุป: Insider Threat case ใช้ทั้ง physical (USB) และ cloud exfiltration "
            "ควรตรวจสอบ DLP logs, USB device connection logs, cloud storage access logs "
            "และอาจดำเนินคดีตาม พ.ร.บ.คอมพิวเตอร์ฯ มาตรา 7 และ พ.ร.บ.ความลับทางการค้า"
        ),
        "answer_en": (
            "MITRE ATT&CK mapping (Insider Threat):\n\n"
            "Exfiltration — Exfiltration over Physical Medium: USB Drive (T1052.001): "
            "Copying files to a USB drive matches T1052.001, commonly used in insider threat cases "
            "as it bypasses network monitoring.\n\n"
            "Collection — Local Data Staging (T1074.001): "
            "Collecting files from multiple locations before exfiltration matches T1074.001.\n\n"
            "Exfiltration — Exfiltration to Cloud Storage (T1567.002): "
            "Uploading to personal Google Drive matches T1567.002, evading DLP via a legitimate service.\n\n"
            "Summary: Insider threat using both physical (USB) and cloud exfiltration. "
            "Investigate DLP logs, USB device connection logs, and cloud storage access logs."
        ),
    },
    {
        "technique_ids": ["T1566", "T1204", "T1021", "T1083", "T1041", "T1486", "T1490"],
        "query_th": (
            "กลุ่มโจมตีส่งอีเมลหลอกลวงไปยังพนักงานหลายคน เมื่อพนักงานคนหนึ่งคลิกลิ้งก์ "
            "malware ถูกติดตั้งและผู้โจมตีเคลื่อนย้ายไปยังเครื่องอื่นในเครือข่าย "
            "จากนั้นขโมยข้อมูลสำคัญออกไปก่อน แล้วจึงเข้ารหัสไฟล์ทั้งหมดและแสดงข้อความเรียกค่าไถ่"
        ),
        "query_en": (
            "An attack group sent phishing emails to multiple employees. After one employee clicked a link, "
            "malware was installed and the attackers moved to other network machines. "
            "They first stole important data, then encrypted all files and displayed a ransom note."
        ),
        "answer_th": (
            "การวิเคราะห์ตาม MITRE ATT&CK (Double Extortion Ransomware):\n\n"
            "Initial Access — Phishing (T1566): การส่งอีเมลหลอกลวงพนักงานหลายคนพร้อมกัน\n\n"
            "Execution — User Execution (T1204): พนักงานคลิกลิ้งก์และ malware ถูกรันโดยผู้ใช้\n\n"
            "Lateral Movement — Remote Services (T1021): "
            "ผู้โจมตีเคลื่อนย้ายผ่านเครือข่ายผ่าน SMB/RDP ไปยังเครื่องอื่น\n\n"
            "Discovery — File and Directory Discovery (T1083): ค้นหาไฟล์สำคัญก่อน exfiltrate\n\n"
            "Exfiltration — Exfiltration Over C2 Channel (T1041): "
            "ขโมยข้อมูลออกไปก่อน เป็น double extortion technique\n\n"
            "Impact — Data Encrypted for Impact (T1486): เข้ารหัสไฟล์ทั้งหมดและเรียกค่าไถ่\n\n"
            "Impact — Inhibit System Recovery (T1490): ลบ backup และ shadow copies เพื่อป้องกันการกู้คืน\n\n"
            "สรุป: Double Extortion Ransomware ทั้งขโมยข้อมูลและเข้ารหัส ทำให้เหยื่อถูกบีบสองทาง"
        ),
        "answer_en": (
            "MITRE ATT&CK mapping (Double Extortion Ransomware):\n\n"
            "Initial Access — Phishing (T1566): Mass phishing emails sent to multiple employees.\n\n"
            "Execution — User Execution (T1204): Employee clicked link executing the malware.\n\n"
            "Lateral Movement — Remote Services (T1021): Moving to other machines via SMB/RDP.\n\n"
            "Discovery — File and Directory Discovery (T1083): Identifying valuable files before exfiltration.\n\n"
            "Exfiltration — Exfiltration Over C2 Channel (T1041): Data stolen first (double extortion).\n\n"
            "Impact — Data Encrypted for Impact (T1486): All files encrypted with ransom demand.\n\n"
            "Impact — Inhibit System Recovery (T1490): Backups and shadow copies deleted to prevent recovery.\n\n"
            "Summary: Double extortion ransomware combining data theft and encryption for maximum leverage."
        ),
    },
    {
        "technique_ids": ["T1059.001", "T1047", "T1546.003", "T1046", "T1041"],
        "query_th": (
            "ผู้โจมตีใช้เฉพาะ built-in tools ของ Windows เช่น PowerShell และ WMI "
            "เพื่อหลีกเลี่ยงการตรวจจับโดย antivirus ทำการสำรวจเครือข่าย "
            "สร้าง WMI subscription เพื่อ persistence และส่งข้อมูลออกเป็นชิ้นเล็กๆ ผ่าน HTTPS"
        ),
        "query_en": (
            "The attacker used only Windows built-in tools like PowerShell and WMI "
            "to evade antivirus detection, performed network reconnaissance, "
            "created a WMI subscription for persistence, and exfiltrated data in small chunks over HTTPS."
        ),
        "answer_th": (
            "การวิเคราะห์ตาม MITRE ATT&CK (Living off the Land / Fileless Attack):\n\n"
            "Execution — PowerShell (T1059.001): "
            "การใช้ PowerShell สำหรับ execution ตรงกับ T1059.001 ไม่ทิ้ง file บน disk\n\n"
            "Execution — Windows Management Instrumentation (T1047): "
            "การใช้ WMI สำหรับ execution และการจัดการระบบตรงกับ T1047\n\n"
            "Persistence — Event Triggered Execution: WMI Event Subscription (T1546.003): "
            "การสร้าง WMI subscription เป็น persistence mechanism ตรงกับ T1546.003 "
            "ทำงานต่อเนื่องหลัง reboot โดยไม่ต้องมีไฟล์\n\n"
            "Discovery — Network Service Discovery (T1046): "
            "การสำรวจเครือข่ายเพื่อหาเป้าหมายตรงกับ T1046\n\n"
            "Exfiltration — Exfiltration Over C2 Channel (T1041): "
            "การส่งข้อมูลเป็นชิ้นเล็กๆ ผ่าน HTTPS ตรงกับ T1041\n\n"
            "สรุป: Fileless/LOTL attack ใช้เฉพาะ Windows built-in tools หลีกเลี่ยง EDR ได้ดี "
            "ควร monitor PowerShell script block logging และ WMI activity"
        ),
        "answer_en": (
            "MITRE ATT&CK mapping (Living off the Land / Fileless Attack):\n\n"
            "Execution — PowerShell (T1059.001): Using PowerShell exclusively for execution matches T1059.001.\n\n"
            "Execution — Windows Management Instrumentation (T1047): Using WMI for execution matches T1047.\n\n"
            "Persistence — WMI Event Subscription (T1546.003): "
            "Creating WMI subscriptions for persistence matches T1546.003, surviving reboots without files.\n\n"
            "Discovery — Network Service Discovery (T1046): Network reconnaissance matches T1046.\n\n"
            "Exfiltration — Exfiltration Over C2 Channel (T1041): "
            "Sending small HTTPS data chunks matches T1041.\n\n"
            "Summary: Fileless/LOTL attack using only Windows built-in tools to evade EDR. "
            "Enable PowerShell script block logging and monitor WMI activity."
        ),
    },
    # ── English-only Incident Scenarios ──────────────────────────────────────
    {
        "technique_ids": ["T1566.002", "T1534", "T1078"],
        "query_en": (
            "A financial institution detected unauthorized wire transfers after an employee "
            "fell victim to a Business Email Compromise attack. "
            "The attacker spoofed the CFO's email address and convinced the finance team "
            "to urgently transfer funds to a new vendor account."
        ),
        "answer_en": (
            "MITRE ATT&CK mapping for Business Email Compromise (BEC):\n\n"
            "Initial Access — Phishing: Spear Phishing Link (T1566.002): "
            "The attacker may have used phishing to first compromise an internal email account "
            "before launching the BEC campaign.\n\n"
            "Lateral Movement — Internal Spear Phishing (T1534): "
            "Sending fraudulent emails impersonating the CFO to internal finance staff "
            "matches T1534 (Internal Spear Phishing), the core BEC technique.\n\n"
            "Defense Evasion / Persistence — Valid Accounts (T1078): "
            "If the attacker compromised the actual CFO email account, this matches T1078, "
            "making the emails appear fully legitimate.\n\n"
            "Summary: Business Email Compromise via executive impersonation. "
            "Investigate email headers, authentication logs, DMARC/DKIM records, and wire transfer approval workflows."
        ),
    },
    {
        "technique_ids": ["T1595", "T1190", "T1053.005", "T1048.001", "T1071.004"],
        "query_en": (
            "A threat actor conducted extensive reconnaissance for months before striking. "
            "They exploited a zero-day vulnerability in the organization's VPN appliance, "
            "established persistence using scheduled tasks, "
            "and slowly exfiltrated intellectual property over encrypted DNS queries to evade detection."
        ),
        "answer_en": (
            "MITRE ATT&CK mapping (Long-term APT campaign):\n\n"
            "Reconnaissance — Active Scanning (T1595): "
            "Months of pre-attack reconnaissance matches T1595, characteristic of nation-state APT actors.\n\n"
            "Initial Access — Exploit Public-Facing Application (T1190): "
            "Exploiting a zero-day vulnerability in the VPN appliance matches T1190.\n\n"
            "Persistence — Scheduled Task/Job (T1053.005): "
            "Creating scheduled tasks for persistence matches T1053.005.\n\n"
            "Exfiltration — Exfiltration Over Alternative Protocol: DNS (T1048.001): "
            "Exfiltrating data encoded in DNS queries matches T1048.001.\n\n"
            "Command and Control — Application Layer Protocol: DNS (T1071.004): "
            "Using DNS as a covert C2 channel matches T1071.004.\n\n"
            "Summary: Long-term APT campaign using VPN zero-day, scheduled task persistence, "
            "and DNS tunneling for covert data exfiltration."
        ),
    },
    {
        "technique_ids": ["T1110.004", "T1136.003", "T1496", "T1530", "T1537"],
        "query_en": (
            "A cloud administrator's account was compromised through credential stuffing. "
            "The attackers created new IAM users with elevated privileges, "
            "launched cryptocurrency mining instances, "
            "and exfiltrated sensitive data from S3 buckets to an external server."
        ),
        "answer_en": (
            "MITRE ATT&CK mapping (Cloud attack):\n\n"
            "Initial Access — Brute Force: Credential Stuffing (T1110.004): "
            "Using previously breached credentials against the cloud admin account matches T1110.004.\n\n"
            "Persistence — Create Account: Cloud Account (T1136.003): "
            "Creating new IAM users with elevated privileges matches T1136.003.\n\n"
            "Impact — Resource Hijacking (T1496): "
            "Launching cryptocurrency mining instances matches T1496.\n\n"
            "Collection — Data from Cloud Storage Object (T1530): "
            "Accessing and reading sensitive data from S3 buckets matches T1530.\n\n"
            "Exfiltration — Transfer Data to Cloud Account (T1537): "
            "Exfiltrating S3 data to an external cloud account matches T1537.\n\n"
            "Summary: Cloud account compromise via credential stuffing leading to resource hijacking "
            "and data exfiltration. Enforce MFA on all cloud admin accounts."
        ),
    },
    {
        "technique_ids": ["T1195.001", "T1554", "T1543"],
        "query_en": (
            "Malicious packages were published to a popular open-source package repository "
            "after the maintainer's account was compromised. "
            "Thousands of developers downloaded the infected package, "
            "giving attackers persistent access to development environments "
            "and allowing backdoor injection into downstream applications."
        ),
        "answer_en": (
            "MITRE ATT&CK mapping (Software dependency supply chain):\n\n"
            "Initial Access — Supply Chain Compromise: Compromise Software Dependencies (T1195.001): "
            "Injecting malicious code into packages in an official repository matches T1195.001.\n\n"
            "Persistence — Compromise Client Software Binary (T1554): "
            "Injecting backdoors into downstream software through developer environments matches T1554.\n\n"
            "Persistence — Create or Modify System Process (T1543): "
            "Modifying system processes in developer environments for persistence matches T1543.\n\n"
            "Summary: Dependency supply chain attack targeting package repositories. "
            "Implement dependency pinning, SBOM tracking, and package integrity verification."
        ),
    },
    {
        "technique_ids": ["T1133", "T1078.003", "T1485", "T1489"],
        "query_en": (
            "A power plant's industrial control system was attacked. "
            "The attacker accessed the system through a vendor's authorized remote support channel, "
            "then sent incorrect commands to control devices, "
            "causing machinery malfunction and a regional power outage."
        ),
        "answer_en": (
            "MITRE ATT&CK mapping (ICS/Critical Infrastructure attack):\n\n"
            "Initial Access — External Remote Services (T1133): "
            "Using a vendor's authorized remote access channel to reach the ICS matches T1133. "
            "Third-party remote access is a critical attack vector in OT/ICS environments.\n\n"
            "Initial Access — Valid Accounts: Local Accounts (T1078.003): "
            "Using existing accounts in the industrial control system matches T1078.003.\n\n"
            "Impact — Data Destruction (T1485): "
            "Sending malicious commands to overwrite control logic or destroy operational data matches T1485.\n\n"
            "Impact — Service Stop (T1489): "
            "Causing machinery malfunction and power outage by stopping critical services matches T1489.\n\n"
            "Summary: Critical Infrastructure attack via trusted vendor remote access. "
            "Enforce strict vendor access controls, network segmentation, and OT-specific monitoring."
        ),
    },
]


class IncidentScenarioGenerator:
    """Generates incident-style evaluation samples grounded in Neo4j STIX IDs."""

    def __init__(self, neo4j: Neo4jGroundTruthBuilder):
        self.neo4j = neo4j

    def generate(self) -> list[GeneratedSample]:
        """Build all incident samples, looking up STIX IDs from Neo4j."""
        # Collect all unique ATT&CK IDs across all scenarios
        all_ids: set[str] = set()
        for sc in INCIDENT_SCENARIOS:
            all_ids.update(sc["technique_ids"])

        id_map = self.neo4j.get_techniques_by_attack_ids(list(all_ids))
        found = len(id_map)
        print(f"  [INCIDENT] Looked up {len(all_ids)} ATT&CK IDs → {found} found in Neo4j")

        samples: list[GeneratedSample] = []
        skipped = 0

        for sc in INCIDENT_SCENARIOS:
            found_ids = [tid for tid in sc["technique_ids"] if tid in id_map]
            stix_ids = [id_map[tid] for tid in found_ids]
            if not stix_ids:
                skipped += 1
                continue

            # Thai sample
            if sc.get("query_th") and sc.get("answer_th"):
                samples.append(GeneratedSample(
                    query=sc["query_th"],
                    relevant_stix_ids=stix_ids,
                    reference_answer=sc["answer_th"],
                    language="th",
                    category="incident_analysis",
                    query_en=sc.get("query_en", ""),
                    gold_attack_ids=found_ids,
                ))
                # Also add English version of the same scenario
                if sc.get("query_en") and sc.get("answer_en"):
                    samples.append(GeneratedSample(
                        query=sc["query_en"],
                        relevant_stix_ids=stix_ids,
                        reference_answer=sc["answer_en"],
                        language="en",
                        category="incident_analysis",
                        gold_attack_ids=found_ids,
                    ))
            elif sc.get("query_en") and sc.get("answer_en"):
                # English-only scenario
                samples.append(GeneratedSample(
                    query=sc["query_en"],
                    relevant_stix_ids=stix_ids,
                    reference_answer=sc["answer_en"],
                    language="en",
                    category="incident_analysis",
                    gold_attack_ids=found_ids,
                ))

        if skipped:
            print(f"  [INCIDENT] Skipped {skipped} scenarios (no matching STIX IDs in Neo4j)")
        print(f"  [INCIDENT] Generated {len(samples)} incident samples "
              f"({sum(1 for s in samples if s.language == 'th')} Thai, "
              f"{sum(1 for s in samples if s.language == 'en')} English)")
        return samples


# ══════════════════════════════════════════════════════════════════════════════
# DATASET GENERATOR
# ══════════════════════════════════════════════════════════════════════════════


class DatasetGenerator:
    """Iterates query templates × seed nodes to generate evaluation samples."""

    def __init__(self, neo4j: Neo4jGroundTruthBuilder, thai_ratio: float = 0.2):
        self.neo4j = neo4j
        self.templates = QueryTemplateRegistry(neo4j)
        self.thai_ratio = thai_ratio

    def generate(self) -> list[GeneratedSample]:
        """Generate the full evaluation dataset."""
        samples: list[GeneratedSample] = []
        seen_queries: set[str] = set()

        def _add(sample: GeneratedSample | None, seed: dict | None = None) -> None:
            """Add sample if valid and not duplicate."""
            if sample is None:
                return
            if not sample.relevant_stix_ids:
                return
            if sample.query in seen_queries:
                return
            seen_queries.add(sample.query)
            samples.append(sample)

        # ── Discover seed nodes ───────────────────────────────────────────
        print("\n[GEN] Discovering seed nodes from Neo4j...")

        techniques = self.neo4j.get_top_techniques(limit=500)
        print(f"  Techniques: {len(techniques)}")

        groups = self.neo4j.get_top_groups(limit=300)
        print(f"  Groups: {len(groups)}")

        software = self.neo4j.get_top_software(limit=300)
        print(f"  Software: {len(software)}")

        tactics = self.neo4j.get_all_tactics()
        print(f"  Tactics: {len(tactics)}")

        groups_with_campaigns = self.neo4j.get_groups_with_campaigns(limit=300)
        print(f"  Groups with campaigns: {len(groups_with_campaigns)}")

        techniques_with_detection = self.neo4j.get_techniques_with_detection(limit=300)
        print(f"  Techniques with detection: {len(techniques_with_detection)}")

        # ── Generate samples per template ─────────────────────────────────
        print("\n[GEN] Generating samples...")

        # 1. Mitigation Lookup
        thai_candidates: list[tuple[GeneratedSample, dict]] = []

        for t in techniques:
            s = self.templates.generate_mitigation_lookup(t)
            _add(s)
            if s and s.query not in seen_queries | {s.query}:
                pass  # already added
            if s:
                thai_candidates.append((s, t))
        print(f"  mitigation_lookup: generated")

        # 2. Technique Lookup
        for t in techniques:
            s = self.templates.generate_technique_lookup(t)
            _add(s)
            if s:
                thai_candidates.append((s, t))
        print(f"  technique_lookup: generated")

        # 3. Group Software
        for g in groups:
            s = self.templates.generate_group_software(g)
            _add(s)
            if s:
                thai_candidates.append((s, g))
        print(f"  group_software: generated")

        # 4. Group Techniques
        for g in groups:
            s = self.templates.generate_group_techniques(g)
            _add(s)
            if s:
                thai_candidates.append((s, g))
        print(f"  group_techniques: generated")

        # 5. Tactic Techniques
        for tac in tactics:
            s = self.templates.generate_tactic_techniques(tac)
            _add(s)
            if s:
                thai_candidates.append((s, tac))
        print(f"  tactic_techniques: generated")

        # 6. Software Techniques
        for sw in software:
            s = self.templates.generate_software_techniques(sw)
            _add(s)
            if s:
                thai_candidates.append((s, sw))
        print(f"  software_techniques: generated")

        # 7. Technique Detection
        for t in techniques_with_detection:
            s = self.templates.generate_technique_detection(t)
            _add(s)
            if s:
                thai_candidates.append((s, t))
        print(f"  technique_detection: generated")

        # 8. Technique Groups
        for t in techniques[:10]:  # Top 10 only to avoid overlap
            s = self.templates.generate_technique_groups(t)
            _add(s)
            if s:
                thai_candidates.append((s, t))
        print(f"  technique_groups: generated")

        # (software_type_query removed: pure enumeration over hundreds of
        # gold IDs — a Cypher task, not a top-K retrieval task, and not a
        # question the product's users ask.)

        # 10. Campaign Attribution
        for g in groups_with_campaigns:
            s = self.templates.generate_campaign_attribution(g)
            _add(s)
            if s:
                thai_candidates.append((s, g))
        print(f"  campaign_attribution: generated")

        # 11. Incident Analysis (Thai + English scenarios)
        print(f"\n[GEN] Generating incident analysis scenarios...")
        incident_gen = IncidentScenarioGenerator(self.neo4j)
        for inc in incident_gen.generate():
            _add(inc)
        print(f"  incident_analysis: generated")

        # ── Thai variants ─────────────────────────────────────────────────
        en_count = len(samples)
        thai_target = max(1, int(en_count * self.thai_ratio))

        # Select a diverse subset for Thai translation
        random.seed(42)  # Reproducible
        if len(thai_candidates) > thai_target:
            # Stratified sampling: pick from different categories
            by_cat: dict[str, list[tuple[GeneratedSample, dict]]] = {}
            for s, seed in thai_candidates:
                by_cat.setdefault(s.category, []).append((s, seed))

            selected: list[tuple[GeneratedSample, dict]] = []
            cats = list(by_cat.keys())
            random.shuffle(cats)
            idx = 0
            while len(selected) < thai_target and idx < thai_target * 3:
                cat = cats[idx % len(cats)]
                candidates = by_cat.get(cat, [])
                if candidates:
                    chosen = candidates.pop(random.randint(0, len(candidates) - 1))
                    selected.append(chosen)
                    if not candidates:
                        by_cat.pop(cat, None)
                        cats = [c for c in cats if c in by_cat]
                        if not cats:
                            break
                idx += 1
        else:
            selected = thai_candidates

        for en_sample, seed in selected:
            th_sample = _make_thai_variant(en_sample, seed)
            _add(th_sample)

        th_count = len(samples) - en_count
        print(f"\n[GEN] Generated {en_count} English + {th_count} Thai = {len(samples)} total samples")

        return samples


# ══════════════════════════════════════════════════════════════════════════════
# DATASET VALIDATOR
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class ValidationResult:
    """Result of dataset validation."""
    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        lines = ["\n" + "═" * 60, "  VALIDATION REPORT", "═" * 60]

        lines.append(f"\n  Total samples: {self.stats.get('total', 0)}")
        lines.append(f"  English: {self.stats.get('en_count', 0)}")
        lines.append(f"  Thai: {self.stats.get('th_count', 0)}")
        lines.append(f"  Categories: {self.stats.get('category_count', 0)}")

        if self.stats.get("categories"):
            lines.append("\n  Category breakdown:")
            for cat, count in sorted(self.stats["categories"].items()):
                lines.append(f"    {cat}: {count}")

        if self.stats.get("avg_ids"):
            lines.append(f"\n  Avg relevant_stix_ids per sample: {self.stats['avg_ids']:.1f}")
            lines.append(f"  Min: {self.stats.get('min_ids', 0)}")
            lines.append(f"  Max: {self.stats.get('max_ids', 0)}")

        if self.errors:
            lines.append(f"\n  ❌ ERRORS ({len(self.errors)}):")
            for e in self.errors:
                lines.append(f"    - {e}")

        if self.warnings:
            lines.append(f"\n  ⚠ WARNINGS ({len(self.warnings)}):")
            for w in self.warnings:
                lines.append(f"    - {w}")

        if self.is_valid:
            lines.append("\n  ✅ VALIDATION PASSED")
        else:
            lines.append("\n  ❌ VALIDATION FAILED")

        lines.append("")
        return "\n".join(lines)


class DatasetValidator:
    """Validates the generated dataset for consistency and completeness."""

    def __init__(self, min_samples: int = 50, min_categories: int = 8):
        self.min_samples = min_samples
        self.min_categories = min_categories

    def validate(self, samples: list[GeneratedSample]) -> ValidationResult:
        """Run all validation checks."""
        result = ValidationResult()

        # ── Collect stats ─────────────────────────────────────────────────
        categories: dict[str, int] = {}
        en_count = 0
        th_count = 0
        all_id_counts = []
        seen_queries: set[str] = set()

        for i, sample in enumerate(samples):
            categories[sample.category] = categories.get(sample.category, 0) + 1

            if sample.language == "en":
                en_count += 1
            else:
                th_count += 1

            all_id_counts.append(len(sample.relevant_stix_ids))

            # ── Rule 1: No empty ground truth ─────────────────────────────
            if not sample.relevant_stix_ids:
                result.errors.append(
                    f"Sample {i} has empty relevant_stix_ids: '{sample.query[:50]}...'"
                )
                result.is_valid = False

            # ── Rule 3: No duplicate queries ──────────────────────────────
            if sample.query in seen_queries:
                result.errors.append(
                    f"Duplicate query at sample {i}: '{sample.query[:50]}...'"
                )
                result.is_valid = False
            seen_queries.add(sample.query)

            # ── Rule 2: Answer mentions match relevant IDs ────────────────
            # Reference answers are optional for incident samples (scored by
            # gold_attack_ids, not reference text); still expected for
            # English lookup samples.
            if (
                sample.language == "en"
                and sample.category != "incident_analysis"
                and not sample.reference_answer.strip()
            ):
                result.warnings.append(
                    f"Sample {i} has empty reference_answer: '{sample.query[:50]}...'"
                )

            # ── Rule 6: incident samples carry generation-eval fields ─────
            if sample.category == "incident_analysis":
                n_gold = len(sample.gold_attack_ids)
                if not 3 <= n_gold <= 7:
                    result.warnings.append(
                        f"Sample {i} (incident) has {n_gold} gold_attack_ids "
                        f"(target 3-7): '{sample.query[:50]}...'"
                    )
                if sample.language == "th" and not sample.query_en:
                    result.warnings.append(
                        f"Sample {i} (incident, th) missing query_en: "
                        f"'{sample.query[:50]}...'"
                    )

            # ── Rule 7: attack_steps well-formed when present ──────────────
            for j, step in enumerate(sample.attack_steps):
                if step.get("cue_type") not in ("named", "described"):
                    result.errors.append(
                        f"Sample {i} step {j} has invalid cue_type "
                        f"{step.get('cue_type')!r} (must be named|described)"
                    )
                    result.is_valid = False
                if not (step.get("cue") or "").strip():
                    result.errors.append(f"Sample {i} step {j} has empty cue")
                    result.is_valid = False
                if not step.get("gold_attack_ids"):
                    result.errors.append(
                        f"Sample {i} step {j} has no gold_attack_ids"
                    )
                    result.is_valid = False

        # ── Rule 4: Minimum dataset size ──────────────────────────────────
        if len(samples) < self.min_samples:
            result.errors.append(
                f"Dataset has {len(samples)} samples, minimum is {self.min_samples}"
            )
            result.is_valid = False

        # ── Rule 5: Category coverage ─────────────────────────────────────
        if len(categories) < self.min_categories:
            result.warnings.append(
                f"Only {len(categories)} categories present, target is {self.min_categories}. "
                f"Missing categories may indicate empty graph data for those patterns."
            )

        # ── Populate stats ────────────────────────────────────────────────
        result.stats = {
            "total": len(samples),
            "en_count": en_count,
            "th_count": th_count,
            "category_count": len(categories),
            "categories": categories,
            "avg_ids": sum(all_id_counts) / len(all_id_counts) if all_id_counts else 0,
            "min_ids": min(all_id_counts) if all_id_counts else 0,
            "max_ids": max(all_id_counts) if all_id_counts else 0,
        }

        return result


# ══════════════════════════════════════════════════════════════════════════════
# OUTPUT
# ══════════════════════════════════════════════════════════════════════════════


def save_dataset(samples: list[GeneratedSample], output_path: Path) -> None:
    """Save the generated dataset as JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = [s.to_dict() for s in samples]

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\n[GEN] Saved {len(samples)} samples to {output_path}")


def load_dataset_for_validation(path: Path) -> list[GeneratedSample]:
    """Load an existing dataset JSON for validation."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return [
        GeneratedSample(
            query=item["query"],
            relevant_stix_ids=item["relevant_stix_ids"],
            reference_answer=item.get("reference_answer", ""),
            language=item.get("language", "en"),
            category=item.get("category", "general"),
            query_en=item.get("query_en", ""),
            gold_attack_ids=item.get("gold_attack_ids", []),
            attack_steps=item.get("attack_steps", []),
        )
        for item in data
    ]


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(
        description="Generate Neo4j-grounded evaluation dataset for RAG pipeline"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="evaluation/Thai_dataset.json",
        help="Output path for generated dataset (default: Thai_dataset.json)",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=50,
        help="Minimum number of samples required (default: 50)",
    )
    parser.add_argument(
        "--thai-ratio",
        type=float,
        default=0.2,
        help="Ratio of Thai language variants (default: 0.2)",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate an existing dataset file (no generation)",
    )

    args = parser.parse_args()
    output_path = Path(args.output)

    print("=" * 60)
    print("  Neo4j-Grounded Evaluation Dataset Generator")
    print("=" * 60)

    if args.validate_only:
        # ── Validate existing file ────────────────────────────────────────
        if not output_path.exists():
            print(f"\n[ERROR] File not found: {output_path}")
            sys.exit(1)

        print(f"\n[GEN] Validating existing dataset: {output_path}")
        samples = load_dataset_for_validation(output_path)
        validator = DatasetValidator(min_samples=args.min_samples)
        result = validator.validate(samples)
        print(result.summary())
        sys.exit(0 if result.is_valid else 1)

    # ── Generate new dataset ──────────────────────────────────────────────
    neo4j = Neo4jGroundTruthBuilder()

    try:
        generator = DatasetGenerator(neo4j, thai_ratio=args.thai_ratio)
        samples = generator.generate()

        # Validate before saving
        validator = DatasetValidator(min_samples=args.min_samples)
        result = validator.validate(samples)
        print(result.summary())

        if not result.is_valid:
            print("[GEN] ⚠ Validation failed but saving anyway for debugging.")
            print("[GEN] Fix the errors above and re-run.")

        save_dataset(samples, output_path)

        # Also print a comparison with the old dataset if it exists
        old_path = Path("evaluation/eval_dataset.json")
        if old_path.exists() and str(output_path) != str(old_path):
            try:
                old_samples = load_dataset_for_validation(old_path)
                old_usable = sum(1 for s in old_samples if s.relevant_stix_ids)
                print(f"\n[GEN] Comparison with existing dataset:")
                print(f"  Old: {len(old_samples)} total, {old_usable} usable")
                print(f"  New: {len(samples)} total, {sum(1 for s in samples if s.relevant_stix_ids)} usable")
                print(f"  Improvement: {len(samples) - len(old_samples):+d} samples")
            except Exception:
                pass

    finally:
        neo4j.close()
        print("\n[GEN] Neo4j connection closed.")


if __name__ == "__main__":
    main()
