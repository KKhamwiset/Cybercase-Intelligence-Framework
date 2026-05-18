"""
Neo4j Graph Retriever
======================
Expands subgraphs from Neo4j given STIX IDs retrieved from vector search.
Implements the "Graph Expansion" step of the GraphRAG architecture.

For a given entity (e.g., Technique T1566), fetches:
  - Groups that USE it
  - Software that USES it
  - Campaigns that USE it
  - Mitigations that MITIGATE it
  - Subtechniques (SUBTECHNIQUE_OF)
  - Tactics it belongs to (IN_TACTIC)
  - DataComponents that DETECT it
"""

from dataclasses import dataclass, field
from typing import Any, Optional, cast

from config import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER
from neo4j import GraphDatabase, Query


@dataclass
class GraphNode:
    """A node from the graph expansion."""

    stix_id: str
    name: str
    label: str
    attack_id: str = ""
    description: str = ""


@dataclass
class GraphEdge:
    """An edge from the graph expansion."""

    edge_label: str
    source_name: str
    target_name: str
    description: str = ""


@dataclass
class SubgraphResult:
    """Result of a graph expansion query."""

    center_node: Optional[GraphNode] = None
    neighbors: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)

    def to_text(self) -> str:
        """Format the subgraph as readable text for LLM context."""
        if not self.center_node:
            return ""

        lines = [
            f"## {self.center_node.label}: {self.center_node.name} ({self.center_node.attack_id})"
        ]

        # Group edges by type
        edge_groups: dict[str, list[GraphEdge]] = {}
        for edge in self.edges:
            edge_groups.setdefault(edge.edge_label, []).append(edge)

        EDGE_DISPLAY = {
            "USES": "Used by",
            "MITIGATES": "Mitigated by",
            "IN_TACTIC": "Belongs to tactic",
            "SUBTECHNIQUE_OF": "Parent technique",
            "DETECTS": "Detected by",
            "HAS_COMPONENT": "Has component",
            "ATTRIBUTED_TO": "Attributed to",
        }

        for edge_label, edges in edge_groups.items():
            display = EDGE_DISPLAY.get(edge_label, edge_label)

            # For USES edges, the center might be the target (technique used BY groups)
            names = []
            for e in edges:
                if e.source_name == self.center_node.name:
                    names.append(e.target_name)
                else:
                    names.append(e.source_name)

            lines.append(f"  ├── {display}: {', '.join(names)}")

            # Add detailed descriptions for key relationships
            for e in edges:
                if e.description:
                    desc_preview = e.description[:200].replace("\n", " ")
                    lines.append(f"  │   └── {desc_preview}...")

        return "\n".join(lines)


class GraphRetriever:
    """Expands subgraphs from Neo4j for GraphRAG context enrichment."""

    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        print(f"[GRAPH] Connected to {NEO4J_URI}")

    def close(self):
        self.driver.close()

    def expand(self, stix_ids: list[str]) -> list[SubgraphResult]:
        """Expand subgraphs for a list of STIX IDs.

        For each ID, fetches the center node and its immediate neighborhood.
        """
        results = []
        seen_ids = set()

        for stix_id in stix_ids:
            if stix_id in seen_ids:
                continue
            seen_ids.add(stix_id)

            subgraph = self._expand_single(stix_id)
            if subgraph and subgraph.center_node:
                results.append(subgraph)

        return results

    def _expand_single(self, stix_id: str) -> SubgraphResult:
        """Expand a single node's subgraph."""
        result = SubgraphResult()

        with self.driver.session() as session:
            # Get center node
            center = session.run(
                Query("""
                MATCH (n {stix_id: $stix_id})
                RETURN n, labels(n) AS labels
                """),
                stix_id=stix_id,
            ).single()

            if not center:
                return result

            node_data = dict(center["n"])
            labels = center["labels"]

            result.center_node = GraphNode(
                stix_id=node_data.get("stix_id", ""),
                name=node_data.get("name", ""),
                label=labels[0] if labels else "Unknown",
                attack_id=node_data.get("attack_id", ""),
                description=node_data.get("description", "")[:300],
            )

            # Get all outgoing relationships
            outgoing = session.run(
                Query("""
                MATCH (n {stix_id: $stix_id})-[r]->(m)
                RETURN type(r) AS rel_type, r.description AS rel_desc,
                       m.stix_id AS target_id, m.name AS target_name,
                       m.attack_id AS target_attack_id, labels(m) AS target_labels
                """),
                stix_id=stix_id,
            )

            for record in outgoing:
                target_label = (
                    record["target_labels"][0] if record["target_labels"] else "Unknown"
                )

                result.neighbors.append(
                    GraphNode(
                        stix_id=record["target_id"] or "",
                        name=record["target_name"] or "",
                        label=target_label,
                        attack_id=record["target_attack_id"] or "",
                    )
                )

                result.edges.append(
                    GraphEdge(
                        edge_label=record["rel_type"] or "",
                        source_name=result.center_node.name,
                        target_name=record["target_name"] or "",
                        description=record["rel_desc"] or "",
                    )
                )

            # Get all incoming relationships
            incoming = session.run(
                Query("""
                MATCH (m)-[r]->(n {stix_id: $stix_id})
                RETURN type(r) AS rel_type, r.description AS rel_desc,
                       m.stix_id AS source_id, m.name AS source_name,
                       m.attack_id AS source_attack_id, labels(m) AS source_labels
                """),
                stix_id=stix_id,
            )

            for record in incoming:
                source_label = (
                    record["source_labels"][0] if record["source_labels"] else "Unknown"
                )

                result.neighbors.append(
                    GraphNode(
                        stix_id=record["source_id"] or "",
                        name=record["source_name"] or "",
                        label=source_label,
                        attack_id=record["source_attack_id"] or "",
                    )
                )

                result.edges.append(
                    GraphEdge(
                        edge_label=record["rel_type"] or "",
                        source_name=record["source_name"] or "",
                        target_name=result.center_node.name,
                        description=record["rel_desc"] or "",
                    )
                )

        return result

    def query_cypher(self, cypher: str, params: Optional[dict] = None) -> list[dict]:
        """Execute an arbitrary Cypher query and return results as dicts."""
        with self.driver.session() as session:
            result = session.run(Query(cast(Any, cypher)), parameters=params or {})
            return [dict(record) for record in result]

    def get_multi_hop_path(
        self, start_name: str, end_name: str, max_hops: int = 4
    ) -> str:
        """Find paths between two named entities.

        Useful for questions like "What is the relationship between
        Lazarus Group and WannaCry?"
        """
        with self.driver.session() as session:
            query = f"""
                MATCH path = shortestPath(
                    (a {{name: $start_name}})-[*1..{max_hops}]-(b {{name: $end_name}})
                )
                RETURN [n IN nodes(path) | n.name] AS node_names,
                       [r IN relationships(path) | type(r)] AS rel_types
                LIMIT 3
                """
            result = session.run(
                Query(cast(Any, query)),
                start_name=start_name,
                end_name=end_name,
            )

            paths = []
            for record in result:
                names = record["node_names"]
                rels = record["rel_types"]
                # Format: "A -[USES]-> B -[SUBTECHNIQUE_OF]-> C"
                parts = []
                for i, name in enumerate(names):
                    parts.append(name)
                    if i < len(rels):
                        parts.append(f"-[{rels[i]}]->")
                paths.append(" ".join(parts))

            if paths:
                return "\n".join(paths)
            return f"No path found between '{start_name}' and '{end_name}'"
