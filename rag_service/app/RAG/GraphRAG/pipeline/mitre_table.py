"""
MITRE Mapping Table Builder
============================
Converts a raw ``GraphRAGResult`` into a structured MITRE ATT&CK mapping
table for the backend/frontend, filtering out retrieval noise.

Raw retrieval is noisy: vector top-K includes semantically-similar-but-
irrelevant techniques, and 2-hop graph expansion drags in unrelated
neighbors. Two filters are combined:

1. **Answer-grounded relevance** — the reasoning LLM already read the full
   context and chose which techniques to use in its answer. Entities whose
   ATT&CK ID or name appears in the final answer are marked
   ``cited_in_answer`` and always kept (a free relevance judgment, no extra
   LLM call).
2. **Rerank score threshold** — uncited vector hits below
   ``MITRE_TABLE_SCORE_THRESHOLD`` are dropped; uncited graph-only entities
   (expansion neighbors) are always dropped.
"""

from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel

from ..config import MITRE_TABLE_SCORE_THRESHOLD

# Rows the table is capped at — cited rows are never truncated in practice
# (an answer cites a handful of techniques), this guards payload size.
_MAX_ROWS = 25

# ATT&CK IDs as they appear in answers: T1566, T1566.001, TA0001, G0016,
# S0002, M1032, DS0026, C0011.
_ATTACK_ID_PATTERN = re.compile(
    r"\b(?:TA\d{4}|T\d{4}(?:\.\d{3})?|G\d{4}|S\d{4}|M\d{4}|DS\d{4}|C\d{4})\b",
    re.IGNORECASE,
)

_MITRE_URL_PATHS = {
    "TA": "tactics",
    "T": "techniques",
    "G": "groups",
    "S": "software",
    "M": "mitigations",
    "DS": "datasources",
    "C": "campaigns",
}


class MitreTableRow(BaseModel):
    """One entry of the MITRE mapping table exposed to the backend."""

    technique_id: str = ""  # ATT&CK ID (T1566, TA0001, G0016, …); may be empty
    name: str
    entity_type: str = ""  # Technique | Subtechnique | Tactic | Group | Software | …
    tactic: Optional[str] = None  # From IN_TACTIC graph edges, when available
    score: Optional[float] = None  # Rerank score; None for graph-only rows
    source: str = "vector"  # "vector" | "graph"
    relevance: str = "retrieved_only"  # "cited_in_answer" | "retrieved_only"
    description: str = ""
    mitre_url: Optional[str] = None


def build_mitre_table(
    rag_result,
    answer: str,
    score_threshold: Optional[float] = None,
) -> list[MitreTableRow]:
    """Build the filtered MITRE mapping table from raw retrieval results.

    Args:
        rag_result: ``GraphRAGResult`` (or None) attached to the agent response.
        answer: Final LLM answer used for answer-grounded filtering. Thai
            answers keep ATT&CK IDs and English technique names, so matching
            works cross-lingually.
        score_threshold: Override for ``MITRE_TABLE_SCORE_THRESHOLD``.

    Returns:
        Rows sorted cited-first then by score descending. Empty when there is
        no retrieval result or no answer (e.g. follow-up pauses).
    """
    if rag_result is None or not answer:
        return []

    threshold = (
        score_threshold if score_threshold is not None else MITRE_TABLE_SCORE_THRESHOLD
    )

    tactic_by_technique = _tactic_map(rag_result)
    candidates = _collect_candidates(rag_result)

    cited_ids = {m.upper() for m in _ATTACK_ID_PATTERN.findall(answer)}
    answer_lower = answer.lower()

    rows: list[MitreTableRow] = []
    for cand in candidates.values():
        cited = _is_cited(cand["technique_id"], cand["name"], cited_ids, answer_lower)
        if cited:
            relevance = "cited_in_answer"
        elif cand["source"] == "vector" and (cand["score"] or 0.0) >= threshold:
            relevance = "retrieved_only"
        else:
            continue

        rows.append(
            MitreTableRow(
                technique_id=cand["technique_id"],
                name=cand["name"],
                entity_type=cand["entity_type"],
                tactic=tactic_by_technique.get(cand["name"]),
                score=cand["score"],
                source=cand["source"],
                relevance=relevance,
                description=cand["description"],
                mitre_url=_mitre_url(cand["technique_id"]),
            )
        )

    rows.sort(key=lambda r: (r.relevance != "cited_in_answer", -(r.score or 0.0)))
    return rows[:_MAX_ROWS]


def _collect_candidates(rag_result) -> dict[str, dict]:
    """Gather unique entities from vector hits, graph seeds, and neighbors."""
    candidates: dict[str, dict] = {}

    for vr in rag_result.vector_results:
        md = vr.metadata or {}
        if md.get("entity_type") != "Node":
            continue  # Relationship docs are not entities; they surface as edges
        name = md.get("name", "")
        if not name:
            continue
        key = vr.stix_id or f"{md.get('node_label', '')}:{name}"
        existing = candidates.get(key)
        if existing is None or (existing["score"] or 0.0) < vr.score:
            candidates[key] = {
                "technique_id": md.get("attack_id", "") or "",
                "name": name,
                "entity_type": md.get("node_label", "") or "",
                "score": float(vr.score),
                "source": "vector",
                "description": (vr.document or "")[:300],
            }

    for sg in rag_result.graph_results:
        for node in filter(None, [sg.center_node, *sg.neighbors]):
            if not node.name:
                continue
            key = node.stix_id or f"{node.label}:{node.name}"
            if key not in candidates:
                candidates[key] = {
                    "technique_id": node.attack_id or "",
                    "name": node.name,
                    "entity_type": node.label or "",
                    "score": None,
                    "source": "graph",
                    "description": (node.description or "")[:300],
                }

    return candidates


def _tactic_map(rag_result) -> dict[str, str]:
    """Map technique name → tactic name from IN_TACTIC graph edges."""
    tactic_by_technique: dict[str, str] = {}
    for sg in rag_result.graph_results:
        for edge in sg.edges:
            if edge.edge_label == "IN_TACTIC" and edge.source_name:
                tactic_by_technique.setdefault(edge.source_name, edge.target_name)
    return tactic_by_technique


def _is_cited(
    attack_id: str, name: str, cited_ids: set[str], answer_lower: str
) -> bool:
    if attack_id:
        rid = attack_id.upper()
        if rid in cited_ids:
            return True
        # Parent technique counts as cited when a subtechnique is cited.
        if any(cited.startswith(rid + ".") for cited in cited_ids):
            return True

    # Name match: MITRE names stay in English even inside Thai answers.
    # Guard short names against false positives and require word boundaries.
    if name and len(name) >= 4:
        pattern = r"(?<!\w)" + re.escape(name.lower()) + r"(?!\w)"
        if re.search(pattern, answer_lower):
            return True

    return False


def _mitre_url(attack_id: str) -> Optional[str]:
    if not attack_id:
        return None
    rid = attack_id.upper()
    match = re.match(r"^(TA|T|G|S|M|DS|C)\d+", rid)
    if not match:
        return None
    path = _MITRE_URL_PATHS.get(match.group(1))
    if not path:
        return None
    # Subtechnique T1566.001 → techniques/T1566/001/
    return f"https://attack.mitre.org/{path}/{rid.replace('.', '/')}/"
