"""
Neo4j Graph Database Loader
============================
Loads parsed ATT&CK entities and relationships into Neo4j.
Creates nodes with labels matching schema_design.md and edges with
relationship descriptions for GraphRAG expansion.
"""

from neo4j import GraphDatabase
from typing import Optional

from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, sep
from models import AttackEntity, AttackRelationship, Technique, Software
from .stix_parser import StixParser


class GraphLoader:
    """Loads ATT&CK data into Neo4j."""

    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        print(f"[NEO4J] Connected to {NEO4J_URI}")

    def close(self):
        self.driver.close()

    def clear_database(self):
        """Remove all existing nodes and relationships."""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        print("[NEO4J] Database cleared")

    def create_constraints(self):
        """Create uniqueness constraints for fast lookups."""
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Technique) REQUIRE n.stix_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Subtechnique) REQUIRE n.stix_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Group) REQUIRE n.stix_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Software) REQUIRE n.stix_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Campaign) REQUIRE n.stix_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Mitigation) REQUIRE n.stix_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Tactic) REQUIRE n.stix_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:DataSource) REQUIRE n.stix_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:DataComponent) REQUIRE n.stix_id IS UNIQUE",
        ]
        with self.driver.session() as session:
            for c in constraints:
                session.run(c)
        print("[NEO4J] Constraints created")

    def create_indexes(self):
        """Create indexes for common query patterns."""
        indexes = [
            "CREATE INDEX IF NOT EXISTS FOR (n:Technique) ON (n.attack_id)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Subtechnique) ON (n.attack_id)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Group) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Software) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Tactic) ON (n.shortname)",
        ]
        with self.driver.session() as session:
            for idx in indexes:
                session.run(idx)
        print("[NEO4J] Indexes created")

    # ──────────────────────────────────────────────────────────────────────
    # NODE CREATION
    # ──────────────────────────────────────────────────────────────────────
    def load_entities(self, entities: list[AttackEntity]) -> int:
        """Load all entities as nodes into Neo4j. Returns count loaded."""
        sep("Loading Nodes into Neo4j")
        count = 0

        with self.driver.session() as session:
            for entity in entities:
                props = self._entity_to_props(entity)
                label = entity.node_label

                # Use MERGE to avoid duplicates (same entity may appear in enterprise + mobile)
                query = f"""
                MERGE (n:{label} {{stix_id: $stix_id}})
                SET n += $props
                """
                session.run(query, stix_id=entity.stix_id, props=props)
                count += 1

                if count % 200 == 0:
                    print(f"        Loaded {count} nodes...")

        print(f"[NEO4J] Loaded {count} nodes total")
        return count

    def _entity_to_props(self, entity: AttackEntity) -> dict:
        """Convert entity to Neo4j property dict."""
        props = {
            "stix_id": entity.stix_id,
            "attack_id": entity.attack_id,
            "name": entity.name,
            "description": entity.description[:5000] if entity.description else "",
            "url": entity.url,
            "domain": entity.domain,
        }

        if isinstance(entity, Technique):
            props["platforms"] = entity.platforms
            props["is_subtechnique"] = entity.is_subtechnique

        if isinstance(entity, Software):
            props["software_type"] = entity.software_type
            props["aliases"] = entity.aliases

        if hasattr(entity, "aliases") and not isinstance(entity, Software):
            props["aliases"] = entity.aliases

        if hasattr(entity, "shortname"):
            props["shortname"] = entity.shortname

        if hasattr(entity, "platforms") and not isinstance(entity, Technique):
            props["platforms"] = entity.platforms

        return props

    # ──────────────────────────────────────────────────────────────────────
    # EDGE CREATION
    # ──────────────────────────────────────────────────────────────────────
    def load_relationships(self, relationships):
        sep("Loading Edges into Neo4j")

        batch_size = 1000
        count = 0

        with self.driver.session() as session:
            for i in range(0, len(relationships), batch_size):
                batch = relationships[i:i+batch_size]

                rel_data = [
                    {
                    "source_ref": r.source_ref,
                    "target_ref": r.target_ref,
                    "rel_id": r.stix_id,
                    "description": r.description[:5000] if r.description else "",
                    "edge_label": r.edge_label,
                    }
                    for r in batch
                ]

                query = """
                UNWIND $rels AS rel
                MATCH (src {stix_id: rel.source_ref})
                MATCH (tgt {stix_id: rel.target_ref})
                CALL apoc.create.relationship(
                    src,
                    rel.edge_label,
                    {
                        stix_id: rel.rel_id,
                        description: rel.description
                    },
                    tgt
                ) YIELD rel AS r
                RETURN count(r)
                """

                session.run(query, rels=rel_data)

                count += len(batch)
                print(f"        Loaded {count} edges...")

        print(f"[NEO4J] Loaded {count} edges")

    # ──────────────────────────────────────────────────────────────────────
    # FULL LOAD
    # ──────────────────────────────────────────────────────────────────────
    def load_all(self, parser: StixParser) -> None:
        """Full ingestion: clear → constraints → nodes → edges."""
        self.clear_database()
        self.create_constraints()
        self.create_indexes()
        self.load_entities(parser.entities)
        self.load_relationships(parser.relationships)

        # Print final stats
        with self.driver.session() as session:
            node_count = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
            edge_count = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
            print(f"\n[NEO4J] Final: {node_count} nodes, {edge_count} edges")
