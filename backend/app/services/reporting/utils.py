from __future__ import annotations

import re

from .schemas import CaseFactPack, REPORT_TYPES, ReportEntity, ReportType


class ReportUtilityMixin:
    @staticmethod
    def _normalize_report_type(report_type: str) -> ReportType:
        normalized = (report_type or "overview").strip().lower()
        if normalized not in REPORT_TYPES:
            return "overview"
        return normalized  # type: ignore[return-value]

    @staticmethod
    def _is_attack_technique_id(attack_id: str) -> bool:
        return bool(re.fullmatch(r"T\d{4}(?:\.\d{3})?", attack_id or ""))

    @staticmethod
    def _is_technique(entity: ReportEntity) -> bool:
        kind = entity.kind.lower().replace(" ", "")
        return (
            ReportUtilityMixin._is_attack_technique_id(entity.attack_id)
            or "technique" in kind
            or "attackpattern" in kind
        )

    @staticmethod
    def _shorten(value: str, limit: int) -> str:
        cleaned = " ".join((value or "").split())
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[: limit - 3].rstrip() + "..."

    @staticmethod
    def _append_unique(items: list[str], value: str) -> None:
        if value and value not in items:
            items.append(value)

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

    @staticmethod
    def _format_evidence_citations(evidence_ids: list[str]) -> str:
        return " ".join(f"[{evidence_id}]" for evidence_id in evidence_ids)

    @staticmethod
    def _primary_case_evidence_id(case_fact_pack: CaseFactPack) -> str:
        for evidence in case_fact_pack.evidence_registry:
            if evidence.source_type in {"user_input", "uploaded_file", "log"}:
                return evidence.evidence_id
        return case_fact_pack.evidence_registry[0].evidence_id
