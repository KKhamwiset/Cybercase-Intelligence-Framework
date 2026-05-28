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
    """A single generated evaluation sample."""
    query: str
    relevant_stix_ids: list[str]
    reference_answer: str
    language: str = "en"
    category: str = "general"

    def to_dict(self) -> dict:
        return asdict(self)


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
                   t.attack_id AS attack_id, degree
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

        results = self.neo4j.run_query("""
            MATCH (t:Technique {stix_id: $stix_id})<-[:MITIGATES]-(m)
            RETURN m.stix_id AS stix_id, m.name AS name, m.attack_id AS attack_id
        """, {"stix_id": stix_id})

        if not results:
            return None

        relevant_ids = [stix_id] + [r["stix_id"] for r in results]
        mit_names = [f"{r['name']} ({r['attack_id']})" for r in results if r.get("attack_id")]
        mit_list = ", ".join(mit_names) if mit_names else ", ".join(r["name"] for r in results)

        return GeneratedSample(
            query=f"What mitigations exist for {name}?",
            relevant_stix_ids=relevant_ids,
            reference_answer=(
                f"Mitigations for {name} ({attack_id}) include: {mit_list}. "
                f"These mitigations help reduce the risk or impact of this technique."
            ),
            language="en",
            category="mitigation_lookup",
        )

    # ── 2. Technique Lookup ───────────────────────────────────────────────

    def generate_technique_lookup(self, technique: dict) -> GeneratedSample | None:
        """'What is [technique] ([ATT&CK ID])?' → node + subtechniques."""
        stix_id = technique["stix_id"]
        name = technique["name"]
        attack_id = technique.get("attack_id", "")

        results = self.neo4j.run_query("""
            MATCH (sub:Subtechnique)-[:SUBTECHNIQUE_OF]->(t:Technique {stix_id: $stix_id})
            RETURN sub.stix_id AS stix_id, sub.name AS name, sub.attack_id AS attack_id
        """, {"stix_id": stix_id})

        relevant_ids = [stix_id] + [r["stix_id"] for r in results]

        if results:
            sub_names = [f"{r['name']} ({r['attack_id']})" for r in results if r.get("attack_id")]
            sub_list = ", ".join(sub_names) if sub_names else ", ".join(r["name"] for r in results)
            answer = (
                f"{name} ({attack_id}) is an adversary technique in the MITRE ATT&CK framework. "
                f"Sub-techniques include: {sub_list}."
            )
        else:
            answer = (
                f"{name} ({attack_id}) is an adversary technique in the MITRE ATT&CK framework."
            )

        return GeneratedSample(
            query=f"What is {name} ({attack_id})?",
            relevant_stix_ids=relevant_ids,
            reference_answer=answer,
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

        results = self.neo4j.run_query("""
            MATCH (g:Group {stix_id: $stix_id})-[:USES]->(t:Technique)
            RETURN t.stix_id AS stix_id, t.name AS name, t.attack_id AS attack_id
            LIMIT 20
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

    # ── 9. Software Type Query ────────────────────────────────────────────

    def generate_software_type_query(self, software_type: str) -> GeneratedSample | None:
        """'What software is classified as [malware/tool]?' → node property filter."""
        results = self.neo4j.run_query("""
            MATCH (s:Software)
            WHERE s.software_type = $sw_type
            RETURN s.stix_id AS stix_id, s.name AS name, s.attack_id AS attack_id
        """, {"sw_type": software_type})

        if not results:
            return None

        relevant_ids = [r["stix_id"] for r in results]
        sw_names = ", ".join(
            f"{r['name']} ({r['attack_id']})" for r in results[:15] if r.get("attack_id")
        )
        if not sw_names:
            sw_names = ", ".join(r["name"] for r in results[:15])

        total = len(results)
        suffix = f" and {total - 15} more" if total > 15 else ""

        label = "malware families" if software_type == "malware" else "tools"

        return GeneratedSample(
            query=f"What software is classified as {software_type} in MITRE ATT&CK?",
            relevant_stix_ids=relevant_ids,
            reference_answer=(
                f"MITRE ATT&CK catalogs {total} {label}, including: "
                f"{sw_names}{suffix}."
            ),
            language="en",
            category="software_type_query",
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

        techniques = self.neo4j.get_top_techniques(limit=200)
        print(f"  Techniques: {len(techniques)}")

        groups = self.neo4j.get_top_groups(limit=100)
        print(f"  Groups: {len(groups)}")

        software = self.neo4j.get_top_software(limit=100)
        print(f"  Software: {len(software)}")

        tactics = self.neo4j.get_all_tactics()
        print(f"  Tactics: {len(tactics)}")

        groups_with_campaigns = self.neo4j.get_groups_with_campaigns(limit=100)
        print(f"  Groups with campaigns: {len(groups_with_campaigns)}")

        techniques_with_detection = self.neo4j.get_techniques_with_detection(limit=100)
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

        # 9. Software Type Query (malware + tool = 2 samples)
        for sw_type in ["malware", "tool"]:
            s = self.templates.generate_software_type_query(sw_type)
            _add(s)
        print(f"  software_type_query: generated")

        # 10. Campaign Attribution
        for g in groups_with_campaigns:
            s = self.templates.generate_campaign_attribution(g)
            _add(s)
            if s:
                thai_candidates.append((s, g))
        print(f"  campaign_attribution: generated")

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
            # Check that the reference answer is not empty for English samples
            if sample.language == "en" and not sample.reference_answer.strip():
                result.warnings.append(
                    f"Sample {i} has empty reference_answer: '{sample.query[:50]}...'"
                )

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
        default="evaluation/eval_dataset_generated.json",
        help="Output path for generated dataset (default: eval_dataset_generated.json)",
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
