"""Canonical, backend-owned case context used by investigation chat.

The payload in this module is deliberately the *only* representation that is
hashed and sent to the RAG service.  Keeping the serializer pure makes case
versions stable across API workers and makes it impossible for a browser-only
prompt to silently diverge from the persisted case.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from copy import deepcopy
from typing import Any, Mapping


class CaseContextService:
    """Build stable, investigation-relevant case context without I/O."""

    _CONTEXT_KEYS = (
        "title",
        "case_type",
        "status",
        "severity",
        "incident_summary",
        "affected_users",
        "affected_assets",
        "timeline_events",
        "evidence_items",
        "attack_mappings",
        "containment_actions",
        "recommendations",
        "gaps",
        "limitations",
        "analyst_notes",
    )
    _ARRAY_SORT_FIELDS: dict[str, tuple[str, ...]] = {
        "timeline_events": ("event_id", "title", "timestamp"),
        "evidence_items": ("evidence_id", "title", "description"),
        "attack_mappings": ("mapping_id", "technique_id", "technique_name"),
        "containment_actions": ("action_id", "title", "description"),
        "recommendations": ("action_id", "title", "description"),
    }

    @staticmethod
    def _normalise(value: Any) -> Any:
        if isinstance(value, str):
            # Preserve intentional paragraph breaks while eliminating process /
            # platform differences that must not create a new case snapshot.
            value = unicodedata.normalize("NFKC", value).replace("\r\n", "\n").replace("\r", "\n")
            return "\n".join(line.rstrip() for line in value.strip().split("\n"))
        if isinstance(value, Mapping):
            return {
                str(key): CaseContextService._normalise(item)
                for key, item in value.items()
                if item is not None
            }
        if isinstance(value, (list, tuple, set)):
            return [CaseContextService._normalise(item) for item in value]
        return value

    @classmethod
    def _sort_records(cls, values: list[Any], fields: tuple[str, ...]) -> list[Any]:
        def key(item: Any) -> tuple[str, ...]:
            if not isinstance(item, Mapping):
                return (str(item),)
            return tuple(str(item.get(field, "")) for field in fields)

        return sorted(values, key=key)

    @classmethod
    def build_payload_from_values(
        cls,
        *,
        title: str,
        status: str,
        severity: str,
        data: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        """Return the context fields actually passed to RAG, in stable order.

        Record timestamps, UI state, transient RAG IDs, and case IDs are not
        included.  Timestamps inside evidence/timeline records remain because
        they are investigation facts, rather than persistence metadata.
        """
        source = deepcopy(dict(data or {}))
        source["title"] = title
        source["status"] = status
        source["severity"] = severity
        payload: dict[str, Any] = {}
        for field in cls._CONTEXT_KEYS:
            value = source.get(field, [] if field in cls._ARRAY_SORT_FIELDS else "")
            value = cls._normalise(value)
            if field in cls._ARRAY_SORT_FIELDS:
                if not isinstance(value, list):
                    value = []
                value = cls._sort_records(value, cls._ARRAY_SORT_FIELDS[field])
            elif field in {"affected_users", "affected_assets", "gaps", "limitations"}:
                if not isinstance(value, list):
                    value = []
                value = sorted(value, key=lambda item: str(item))
            payload[field] = value
        return payload

    @classmethod
    def build_payload_for_case(cls, case: Any) -> dict[str, Any]:
        return cls.build_payload_from_values(
            title=str(case.title or ""),
            status=str(case.status or ""),
            severity=str(case.severity or ""),
            data=case.data,
        )

    @staticmethod
    def canonical_json(payload: Mapping[str, Any]) -> str:
        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    @classmethod
    def snapshot_hash(cls, payload: Mapping[str, Any]) -> str:
        return hashlib.sha256(cls.canonical_json(payload).encode("utf-8")).hexdigest()

    @classmethod
    def hash_for_case(cls, case: Any) -> str:
        return cls.snapshot_hash(cls.build_payload_for_case(case))

    @classmethod
    def render_rag_prompt(
        cls,
        payload: Mapping[str, Any],
        *,
        action: str,
        visible_message: str = "",
    ) -> str:
        instruction = (
            "Analyze the saved cyber incident case. Separate reported facts, "
            "candidate inferences, and missing information. Ground MITRE ATT&CK "
            "mappings in the supplied evidence."
            if action == "analyze"
            else "Answer the analyst's visible question using the saved case context. "
            "Separate reported facts, candidate inferences, and missing information."
        )
        parts = [instruction, "Canonical saved case context:", cls.canonical_json(payload)]
        if visible_message.strip() and action != "analyze":
            parts.extend(["Analyst question:", cls._normalise(visible_message)])
        return "\n\n".join(parts)


__all__ = ["CaseContextService"]
