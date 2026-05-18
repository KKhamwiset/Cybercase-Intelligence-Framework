"""
STIX 2.1 Parser for MITRE ATT&CK Data
======================================
Parses enterprise-attack.json and mobile-attack.json into typed entities
and relationships matching the schema_design.md specification.

Key design decisions:
- Filters out revoked and deprecated objects
- Separates techniques from subtechniques via x_mitre_is_subtechnique
- Software = union of 'tool' + 'malware' STIX types
- Derives IN_TACTIC edges from kill_chain_phases
- Derives HAS_COMPONENT edges from x_mitre_data_source_ref
"""

import json
from pathlib import Path

from app.services.rag.models import (
    AttackEntity,
    AttackRelationship,
    Campaign,
    DataComponent,
    DataSource,
    Group,
    Mitigation,
    Software,
    Tactic,
    Technique,
)


def _get_attack_id(obj: dict) -> str:
    """Extract ATT&CK ID (e.g., T1566) from external_references."""
    for ref in obj.get("external_references", []):
        if ref.get("source_name") in ("mitre-attack", "mitre-mobile-attack"):
            return ref.get("external_id", "")
    return ""


def _get_url(obj: dict) -> str:
    """Extract ATT&CK URL from external_references."""
    for ref in obj.get("external_references", []):
        if ref.get("source_name") in ("mitre-attack", "mitre-mobile-attack"):
            return ref.get("url", "")
    return ""


def _is_revoked_or_deprecated(obj: dict) -> bool:
    """Check if object is revoked or deprecated."""
    return obj.get("revoked", False) or obj.get("x_mitre_deprecated", False)


def _get_tactics_from_kill_chain(obj: dict) -> list[str]:
    """Extract tactic shortnames from kill_chain_phases."""
    phases = obj.get("kill_chain_phases", [])
    return [
        p["phase_name"]
        for p in phases
        if p.get("kill_chain_name") in ("mitre-attack", "mitre-mobile-attack")
    ]


# ──────────────────────────────────────────────────────────────────────────────
# STIX TYPE → EDGE LABEL MAPPING
# ──────────────────────────────────────────────────────────────────────────────
RELATIONSHIP_TYPE_MAP = {
    "uses": "USES",
    "mitigates": "MITIGATES",
    "subtechnique-of": "SUBTECHNIQUE_OF",
    "attributed-to": "ATTRIBUTED_TO",
    "detects": "DETECTS",
    "revoked-by": "REVOKED_BY",
}

# Map STIX type → node label for determining source/target labels
STIX_TYPE_TO_LABEL = {
    "attack-pattern": "Technique",  # will differentiate subtechnique later
    "intrusion-set": "Group",
    "tool": "Software",
    "malware": "Software",
    "campaign": "Campaign",
    "course-of-action": "Mitigation",
    "x-mitre-tactic": "Tactic",
    "x-mitre-data-source": "DataSource",
    "x-mitre-data-component": "DataComponent",
}


class StixParser:
    """Parses MITRE ATT&CK STIX 2.1 JSON bundles into entities and relationships."""

    def __init__(self):
        self.entities: list[AttackEntity] = []
        self.relationships: list[AttackRelationship] = []

        # Lookup tables built during parsing
        self._id_to_name: dict[str, str] = {}
        self._id_to_label: dict[str, str] = {}
        self._tactic_shortname_to_id: dict[str, str] = {}
        self._data_component_to_source: dict[str, str] = {}

    def parse_folder(self, folder: Path, domain: str = "enterprise") -> None:
        """Parse all STIX bundle JSON files in a folder."""
        json_files = sorted(folder.glob("*.json"))
        if not json_files:
            print(f"[WARN] No JSON files found in {folder}")
            return

        print(f"\n[PARSE] Found {len(json_files)} JSON file(s) in {folder.name}/")
        for filepath in json_files:
            self.parse_file(filepath, domain=domain)

    def parse_file(self, filepath: Path, domain: str = "enterprise") -> None:
        """Parse a single STIX bundle JSON file."""
        print(
            f"[PARSE] Loading {filepath.name} ({filepath.stat().st_size / 1e6:.1f} MB)"
        )

        with open(filepath, "r", encoding="utf-8") as f:
            bundle = json.load(f)

        objects = bundle.get("objects", [])
        print(f"[PARSE] Total STIX objects: {len(objects)}")

        # ── First pass: build entities ────────────────────────────────────
        raw_relationships = []

        for obj in objects:
            if _is_revoked_or_deprecated(obj):
                continue

            stix_type = obj.get("type", "")
            stix_id = obj.get("id", "")

            if stix_type == "attack-pattern":
                entity = self._parse_technique(obj, domain)
                self.entities.append(entity)
                self._id_to_name[stix_id] = entity.name
                self._id_to_label[stix_id] = entity.node_label

            elif stix_type == "intrusion-set":
                entity = self._parse_group(obj, domain)
                self.entities.append(entity)
                self._id_to_name[stix_id] = entity.name
                self._id_to_label[stix_id] = "Group"

            elif stix_type in ("tool", "malware"):
                entity = self._parse_software(obj, stix_type, domain)
                self.entities.append(entity)
                self._id_to_name[stix_id] = entity.name
                self._id_to_label[stix_id] = "Software"

            elif stix_type == "campaign":
                entity = self._parse_campaign(obj, domain)
                self.entities.append(entity)
                self._id_to_name[stix_id] = entity.name
                self._id_to_label[stix_id] = "Campaign"

            elif stix_type == "course-of-action":
                entity = self._parse_mitigation(obj, domain)
                self.entities.append(entity)
                self._id_to_name[stix_id] = entity.name
                self._id_to_label[stix_id] = "Mitigation"

            elif stix_type == "x-mitre-tactic":
                entity = self._parse_tactic(obj, domain)
                self.entities.append(entity)
                self._id_to_name[stix_id] = entity.name
                self._id_to_label[stix_id] = "Tactic"
                self._tactic_shortname_to_id[entity.shortname] = stix_id

            elif stix_type == "x-mitre-data-source":
                entity = self._parse_data_source(obj, domain)
                self.entities.append(entity)
                self._id_to_name[stix_id] = entity.name
                self._id_to_label[stix_id] = "DataSource"

            elif stix_type == "x-mitre-data-component":
                entity = self._parse_data_component(obj, domain)
                self.entities.append(entity)
                self._id_to_name[stix_id] = entity.name
                self._id_to_label[stix_id] = "DataComponent"
                # Track data source ref for HAS_COMPONENT edges
                ds_ref = obj.get("x_mitre_data_source_ref", "")
                if ds_ref:
                    self._data_component_to_source[stix_id] = ds_ref

            elif stix_type == "relationship":
                raw_relationships.append(obj)

        # ── Second pass: build relationships ──────────────────────────────
        self._build_relationships(raw_relationships)

        # ── Derived edges ─────────────────────────────────────────────────
        self._build_tactic_edges()
        self._build_data_source_edges()

        # ── Summary ───────────────────────────────────────────────────────
        entity_counts = {}
        for e in self.entities:
            entity_counts[e.node_label] = entity_counts.get(e.node_label, 0) + 1

        print("\n[PARSE] Entities parsed:")
        for label, count in sorted(entity_counts.items()):
            print(f"        {label}: {count}")

        edge_counts = {}
        for r in self.relationships:
            edge_counts[r.edge_label] = edge_counts.get(r.edge_label, 0) + 1

        print("\n[PARSE] Relationships parsed:")
        for label, count in sorted(edge_counts.items()):
            print(f"        {label}: {count}")

    # ──────────────────────────────────────────────────────────────────────
    # ENTITY PARSERS
    # ──────────────────────────────────────────────────────────────────────
    def _parse_technique(self, obj: dict, domain: str) -> Technique:
        is_sub = obj.get("x_mitre_is_subtechnique", False)
        return Technique(
            stix_id=obj["id"],
            attack_id=_get_attack_id(obj),
            name=obj.get("name", ""),
            description=obj.get("description", ""),
            url=_get_url(obj),
            domain=domain,
            platforms=obj.get("x_mitre_platforms", []),
            is_subtechnique=is_sub,
            node_label="Subtechnique" if is_sub else "Technique",
            tactics=_get_tactics_from_kill_chain(obj),
        )

    def _parse_group(self, obj: dict, domain: str) -> Group:
        return Group(
            stix_id=obj["id"],
            attack_id=_get_attack_id(obj),
            name=obj.get("name", ""),
            description=obj.get("description", ""),
            url=_get_url(obj),
            domain=domain,
            aliases=obj.get("aliases", []),
        )

    def _parse_software(self, obj: dict, stix_type: str, domain: str) -> Software:
        return Software(
            stix_id=obj["id"],
            attack_id=_get_attack_id(obj),
            name=obj.get("name", ""),
            description=obj.get("description", ""),
            url=_get_url(obj),
            domain=domain,
            aliases=obj.get("aliases", obj.get("x_mitre_aliases", [])),
            software_type=stix_type,
        )

    def _parse_campaign(self, obj: dict, domain: str) -> Campaign:
        return Campaign(
            stix_id=obj["id"],
            attack_id=_get_attack_id(obj),
            name=obj.get("name", ""),
            description=obj.get("description", ""),
            url=_get_url(obj),
            domain=domain,
            aliases=obj.get("aliases", []),
        )

    def _parse_mitigation(self, obj: dict, domain: str) -> Mitigation:
        return Mitigation(
            stix_id=obj["id"],
            attack_id=_get_attack_id(obj),
            name=obj.get("name", ""),
            description=obj.get("description", ""),
            url=_get_url(obj),
            domain=domain,
        )

    def _parse_tactic(self, obj: dict, domain: str) -> Tactic:
        return Tactic(
            stix_id=obj["id"],
            attack_id=_get_attack_id(obj),
            name=obj.get("name", ""),
            description=obj.get("description", ""),
            url=_get_url(obj),
            domain=domain,
            shortname=obj.get("x_mitre_shortname", ""),
        )

    def _parse_data_source(self, obj: dict, domain: str) -> DataSource:
        return DataSource(
            stix_id=obj["id"],
            attack_id=_get_attack_id(obj),
            name=obj.get("name", ""),
            description=obj.get("description", ""),
            url=_get_url(obj),
            domain=domain,
            platforms=obj.get("x_mitre_platforms", []),
        )

    def _parse_data_component(self, obj: dict, domain: str) -> DataComponent:
        return DataComponent(
            stix_id=obj["id"],
            name=obj.get("name", ""),
            description=obj.get("description", ""),
            domain=domain,
        )

    # ──────────────────────────────────────────────────────────────────────
    # RELATIONSHIP BUILDERS
    # ──────────────────────────────────────────────────────────────────────
    def _build_relationships(self, raw_rels: list[dict]) -> None:
        """Build typed relationships from raw STIX relationship objects."""
        for obj in raw_rels:
            if _is_revoked_or_deprecated(obj):
                continue

            rel_type = obj.get("relationship_type", "")
            edge_label = RELATIONSHIP_TYPE_MAP.get(rel_type)

            if not edge_label or edge_label == "REVOKED_BY":
                continue  # skip unknown or revoked-by

            source_ref = obj.get("source_ref", "")
            target_ref = obj.get("target_ref", "")

            # Only keep relationships where both endpoints exist
            if source_ref not in self._id_to_name or target_ref not in self._id_to_name:
                continue

            self.relationships.append(
                AttackRelationship(
                    stix_id=obj["id"],
                    relationship_type=rel_type,
                    source_ref=source_ref,
                    target_ref=target_ref,
                    source_name=self._id_to_name.get(source_ref, ""),
                    target_name=self._id_to_name.get(target_ref, ""),
                    description=obj.get("description", ""),
                    edge_label=edge_label,
                )
            )

    def _build_tactic_edges(self) -> None:
        """Derive IN_TACTIC edges from technique kill_chain_phases."""
        for entity in self.entities:
            if not isinstance(entity, Technique):
                continue

            for tactic_shortname in entity.tactics:
                tactic_id = self._tactic_shortname_to_id.get(tactic_shortname)
                if not tactic_id:
                    continue

                self.relationships.append(
                    AttackRelationship(
                        stix_id=f"derived--{entity.stix_id}--{tactic_id}",
                        relationship_type="in-tactic",
                        source_ref=entity.stix_id,
                        target_ref=tactic_id,
                        source_name=entity.name,
                        target_name=self._id_to_name.get(tactic_id, ""),
                        description="",
                        edge_label="IN_TACTIC",
                    )
                )

    def _build_data_source_edges(self) -> None:
        """Derive HAS_COMPONENT edges from x_mitre_data_source_ref."""
        for dc_id, ds_id in self._data_component_to_source.items():
            if ds_id not in self._id_to_name:
                continue

            self.relationships.append(
                AttackRelationship(
                    stix_id=f"derived--{ds_id}--{dc_id}",
                    relationship_type="has-component",
                    source_ref=ds_id,
                    target_ref=dc_id,
                    source_name=self._id_to_name.get(ds_id, ""),
                    target_name=self._id_to_name.get(dc_id, ""),
                    description="",
                    edge_label="HAS_COMPONENT",
                )
            )

    # ──────────────────────────────────────────────────────────────────────
    # PUBLIC API
    # ──────────────────────────────────────────────────────────────────────
    def get_entities_by_label(self, label: str) -> list[AttackEntity]:
        """Get all entities of a specific node label."""
        return [e for e in self.entities if e.node_label == label]

    def get_relationships_by_label(self, label: str) -> list[AttackRelationship]:
        """Get all relationships of a specific edge label."""
        return [r for r in self.relationships if r.edge_label == label]


def parse_all_domains() -> StixParser:
    """Parse all configured ATT&CK domain folders and return a unified parser."""
    from config import ATTACK_DOMAINS

    parser = StixParser()

    for domain_name, folder_path in ATTACK_DOMAINS.items():
        if folder_path.is_dir():
            parser.parse_folder(folder_path, domain=domain_name)
        elif folder_path.exists() and folder_path.suffix == ".json":
            # Fallback: if a single file is passed instead of a folder
            parser.parse_file(folder_path, domain=domain_name)
        else:
            print(f"[WARN] {folder_path} not found, skipping {domain_name} domain")

    # Deduplicate entities and relationships (since many exist across multiple versioned files)
    unique_entities = {e.stix_id: e for e in parser.entities}
    parser.entities = list(unique_entities.values())

    unique_rels = {r.stix_id: r for r in parser.relationships}
    parser.relationships = list(unique_rels.values())

    print(
        f"\n[PARSE] Total Deduplicated: {len(parser.entities)} entities, {len(parser.relationships)} relationships"
    )
    return parser
