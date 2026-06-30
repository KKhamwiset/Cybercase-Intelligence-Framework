from __future__ import annotations

from typing import Any

from .schemas import (
    EvidenceReference,
    ReportEntity,
    ReportEvidencePacket,
    ReportRelationship,
)


class ReportEvidenceMixin:
    def build_evidence_packet(
        self,
        query: str,
        context: str,
        rag_result: Any | None = None,
        report_type: str = "overview",
    ) -> ReportEvidencePacket:
        packet = ReportEvidencePacket(
            report_type=self._normalize_report_type(report_type),
            user_query=query,
            raw_context_excerpt=(context or "")[:3000],
        )

        if rag_result:
            self._add_vector_results(packet, getattr(rag_result, "vector_results", []))
            self._add_graph_results(packet, getattr(rag_result, "graph_results", []))

        candidate_entities = self._dedupe_entities(
            packet.semantic_matches
            + [
                entity
                for entity in packet.graph_entities
                if entity.source == "graph_center"
            ]
        )
        packet.ttp_candidates = [
            entity
            for entity in candidate_entities
            if self._is_technique(entity) and self._is_attack_technique_id(entity.attack_id)
        ][:10]
        return packet

    def build_evidence_registry(
        self,
        query: str,
        provided_evidence: list[EvidenceReference] | None,
        mitre_entities: list[ReportEntity],
    ) -> tuple[list[EvidenceReference], list[str], dict[str, str]]:
        registry: list[EvidenceReference] = []
        used_ids: set[str] = set()
        next_number = 1

        def next_evidence_id() -> str:
            nonlocal next_number
            while f"E-{next_number:03d}" in used_ids:
                next_number += 1
            evidence_id = f"E-{next_number:03d}"
            used_ids.add(evidence_id)
            next_number += 1
            return evidence_id

        for provided in provided_evidence or []:
            evidence_id = provided.evidence_id.strip()
            if not evidence_id or evidence_id in used_ids:
                evidence_id = next_evidence_id()
            else:
                used_ids.add(evidence_id)
            registry.append(
                EvidenceReference(
                    **{
                        **provided.model_dump(),
                        "evidence_id": evidence_id,
                        "excerpt": self._shorten(provided.excerpt or "", 1200)
                        or None,
                    }
                )
            )

        has_user_input = any(item.source_type == "user_input" for item in registry)
        if query.strip() and not has_user_input:
            registry.insert(
                0,
                EvidenceReference(
                    evidence_id=next_evidence_id(),
                    source_type="user_input",
                    source_name="Submitted case text",
                    excerpt=self._shorten(query, 1200),
                ),
            )
        if not registry:
            registry.append(
                EvidenceReference(
                    evidence_id=next_evidence_id(),
                    source_type="user_input",
                    source_name="Empty case input",
                    excerpt=None,
                )
            )

        base_evidence_ids = [
            item.evidence_id
            for item in registry
            if item.source_type in {"user_input", "uploaded_file", "log"}
        ]
        if not base_evidence_ids and registry:
            base_evidence_ids = [registry[0].evidence_id]

        mitre_evidence_ids: dict[str, str] = {}
        for entity in mitre_entities:
            if not entity.attack_id or entity.attack_id in mitre_evidence_ids:
                continue
            evidence_id = next_evidence_id()
            mitre_evidence_ids[entity.attack_id] = evidence_id
            registry.append(
                EvidenceReference(
                    evidence_id=evidence_id,
                    source_type="mitre_source",
                    source_name=f"{entity.attack_id} {entity.name}",
                    excerpt=self._shorten(entity.description, 1200) or None,
                    line_reference=entity.stix_id or None,
                )
            )

        return registry, base_evidence_ids, mitre_evidence_ids

    def _add_vector_results(self, packet: ReportEvidencePacket, vector_results: Any) -> None:
        for vector_result in list(vector_results)[:12]:
            entity = self._entity_from_vector_result(vector_result)
            if entity:
                self._append_entity(packet.semantic_matches, entity)
            relationship = self._relationship_from_vector_result(vector_result)
            if relationship:
                self._append_relationship(packet.relationships, relationship)

    def _add_graph_results(self, packet: ReportEvidencePacket, graph_results: Any) -> None:
        for subgraph in list(graph_results)[:6]:
            center_entity = self._entity_from_graph_node(
                getattr(subgraph, "center_node", None), "graph_center"
            )
            if center_entity:
                self._append_entity(packet.graph_entities, center_entity)

            for neighbor in getattr(subgraph, "neighbors", [])[:20]:
                neighbor_entity = self._entity_from_graph_node(neighbor, "graph_neighbor")
                if neighbor_entity:
                    self._append_entity(packet.graph_entities, neighbor_entity)

            for edge in getattr(subgraph, "edges", [])[:30]:
                relationship = ReportRelationship(
                    source=getattr(edge, "source_name", "") or "Unknown",
                    relationship=getattr(edge, "edge_label", "") or "RELATED_TO",
                    target=getattr(edge, "target_name", "") or "Unknown",
                    description=self._shorten(getattr(edge, "description", ""), 240),
                )
                self._append_relationship(packet.relationships, relationship)

    def _entity_from_vector_result(self, vector_result: Any) -> ReportEntity | None:
        metadata = getattr(vector_result, "metadata", {}) or {}
        if metadata.get("entity_type") == "Relationship":
            return None
        name = metadata.get("name") or metadata.get("node_label") or ""
        if not name:
            return None
        relevance = getattr(vector_result, "score", None)
        try:
            relevance = float(relevance) if relevance is not None else None
        except (TypeError, ValueError):
            relevance = None
        return ReportEntity(
            name=name,
            kind=metadata.get("node_label") or metadata.get("entity_type") or "Unknown",
            attack_id=metadata.get("attack_id") or "",
            stix_id=getattr(vector_result, "stix_id", "") or metadata.get("stix_id", ""),
            description=self._shorten(getattr(vector_result, "document", ""), 500),
            relevance=relevance,
            source="semantic_search",
        )

    def _relationship_from_vector_result(
        self, vector_result: Any
    ) -> ReportRelationship | None:
        metadata = getattr(vector_result, "metadata", {}) or {}
        if metadata.get("entity_type") != "Relationship":
            return None
        source = metadata.get("source_name") or ""
        target = metadata.get("target_name") or ""
        if not source or not target:
            return None
        return ReportRelationship(
            source=source,
            relationship=metadata.get("edge_label")
            or metadata.get("relationship_type")
            or "RELATED_TO",
            target=target,
            description=self._shorten(getattr(vector_result, "document", ""), 240),
        )

    def _entity_from_graph_node(
        self, graph_node: Any | None, source: str
    ) -> ReportEntity | None:
        if not graph_node:
            return None
        name = getattr(graph_node, "name", "") or ""
        if not name:
            return None
        return ReportEntity(
            name=name,
            kind=getattr(graph_node, "label", "") or "Unknown",
            attack_id=getattr(graph_node, "attack_id", "") or "",
            stix_id=getattr(graph_node, "stix_id", "") or "",
            description=self._shorten(getattr(graph_node, "description", ""), 500),
            source=source,
        )

    def _append_entity(self, items: list[ReportEntity], entity: ReportEntity) -> None:
        key = self._entity_key(entity)
        if any(self._entity_key(existing) == key for existing in items):
            return
        items.append(entity)

    @staticmethod
    def _append_relationship(
        items: list[ReportRelationship], relationship: ReportRelationship
    ) -> None:
        key = (
            relationship.source.lower(),
            relationship.relationship.lower(),
            relationship.target.lower(),
        )
        if any(
            (item.source.lower(), item.relationship.lower(), item.target.lower()) == key
            for item in items
        ):
            return
        items.append(relationship)

    @staticmethod
    def _entity_key(entity: ReportEntity) -> str:
        return entity.stix_id or f"{entity.kind.lower()}::{entity.name.lower()}::{entity.attack_id}"

    def _dedupe_entities(self, entities: list[ReportEntity]) -> list[ReportEntity]:
        deduped: list[ReportEntity] = []
        for entity in entities:
            self._append_entity(deduped, entity)
        return deduped
