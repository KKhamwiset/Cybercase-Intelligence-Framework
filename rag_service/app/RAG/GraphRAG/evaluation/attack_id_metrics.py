"""
ATT&CK ID-Based Generation Metrics
====================================
Deterministic metrics for scoring generated answers against gold
ATT&CK technique IDs — TRAM/CTIBench-style correctness scoring,
plus guard metrics for the Thai output contract.

Primary metric:
  - technique_set_score : precision/recall/F1 between the technique IDs
    found in an answer and the gold IDs, with same-family partial credit
    (answer T1566 vs gold T1566.002 scores 0.5).

Extraction:
  - extract_attack_ids       : regex over T####(.###)?, TA/G/S/M####.
    Works inside Thai prose (no \\b — Thai characters count as \\w,
    so lookarounds on Latin alphanumerics are used instead).
  - extract_technique_names  : whole-word match of canonical English
    technique names/aliases (alias_map exported from Neo4j) — catches
    answers that name a technique without citing its ID.

Guard metrics (language/structure contract):
  - thai_char_ratio     : Thai vs Latin letter ratio of the final answer.
  - structure_compliance: required section headings present?
  - id_survival         : technique IDs preserved across the translation
    stage; IDs *gained* in translation are flagged (potential
    translation-stage hallucination).

All functions are pure — no network, no models — and unit-testable.
"""

from __future__ import annotations

import re
from typing import Optional


# ──────────────────────────────────────────────────────────────────────────────
# Extraction
# ──────────────────────────────────────────────────────────────────────────────

# TA listed before T so the alternation reads unambiguously; Latin-alnum
# lookarounds instead of \b because Thai characters are \w in Unicode
# regex, which would make "ตรงกับT1566" fail a \b boundary.
_ATTACK_ID_RE = re.compile(
    r"(?<![A-Za-z0-9])(TA\d{4}|T\d{4}(?:\.\d{3})?|G\d{4}|S\d{4}|M\d{4})(?!\d)",
    re.IGNORECASE,
)

_THAI_RE = re.compile("[฀-๿]")
_LATIN_RE = re.compile(r"[A-Za-z]")


def extract_attack_ids(text: str) -> set[str]:
    """All MITRE ATT&CK IDs (any entity kind) in the text, uppercased."""
    return {m.group(1).upper() for m in _ATTACK_ID_RE.finditer(text or "")}


def extract_technique_ids(text: str) -> set[str]:
    """Technique IDs only (T####/T####.###), excluding tactics (TA####)."""
    return {
        aid for aid in extract_attack_ids(text)
        if aid.startswith("T") and not aid.startswith("TA")
    }


def extract_technique_names(text: str, alias_map: dict[str, str]) -> set[str]:
    """Technique IDs whose canonical name/alias appears in the text.

    alias_map: lowercased name/alias -> attack_id (exported from Neo4j).
    Matching is case-insensitive and whole-word on Latin boundaries, so
    English names embedded in Thai prose ("ใช้ Valid Accounts เข้าระบบ")
    are found. Aliases shorter than 4 characters are ignored to avoid
    noise. Curate the alias table to keep common English words (e.g.
    "Proxy") out of it or accept their false positives.
    """
    lower = (text or "").lower()
    found: set[str] = set()
    for name, attack_id in alias_map.items():
        name = name.strip().lower()
        if len(name) < 4 or name not in lower:
            continue
        pattern = r"(?<![a-z0-9])" + re.escape(name) + r"(?![a-z0-9])"
        if re.search(pattern, lower):
            found.add(attack_id.upper())
    return found


def extract_all_techniques(text: str, alias_map: Optional[dict[str, str]] = None) -> set[str]:
    """Union of ID-cited and name-cited techniques in the answer."""
    ids = extract_technique_ids(text)
    if alias_map:
        ids |= extract_technique_names(text, alias_map)
    return ids


# ──────────────────────────────────────────────────────────────────────────────
# Technique Set Scoring (with same-family partial credit)
# ──────────────────────────────────────────────────────────────────────────────

def _base_technique(attack_id: str) -> str:
    """T1566.002 -> T1566; T1566 -> T1566."""
    return attack_id.split(".")[0]


def technique_set_score(predicted: set[str], gold: set[str]) -> dict:
    """Soft precision/recall/F1 between predicted and gold technique IDs.

    Greedy one-to-one matching, exact matches first:
      - exact ID match                      -> 1.0
      - same base technique (parent/child
        or sibling sub-technique)           -> 0.5
    Each predicted ID consumes at most one gold ID and vice versa, so
    one parent mention cannot claim credit for several gold children.

    precision = score / |predicted|, recall = score / |gold|.
    """
    predicted = {p.upper() for p in predicted}
    gold = {g.upper() for g in gold}

    if not predicted or not gold:
        return {
            "precision": 0.0, "recall": 0.0, "f1": 0.0,
            "exact": sorted(predicted & gold),
            "partial": [], "spurious": sorted(predicted - gold),
            "missed": sorted(gold - predicted),
        }

    exact = predicted & gold
    remaining_pred = sorted(predicted - exact)
    remaining_gold = sorted(gold - exact)

    partial_pairs: list[tuple[str, str]] = []
    for p in remaining_pred:
        for g in remaining_gold:
            if _base_technique(p) == _base_technique(g):
                partial_pairs.append((p, g))
                remaining_gold.remove(g)
                break

    matched_preds = exact | {p for p, _ in partial_pairs}
    score = len(exact) + 0.5 * len(partial_pairs)
    precision = score / len(predicted)
    recall = score / len(gold)
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall > 0 else 0.0
    )

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "exact": sorted(exact),
        "partial": partial_pairs,
        "spurious": sorted(set(remaining_pred) - matched_preds),
        "missed": sorted(remaining_gold),
    }


def tactic_level_score(
    predicted: set[str],
    gold: set[str],
    technique_to_tactics: dict[str, list[str]],
) -> dict:
    """Set precision/recall/F1 at the tactic level (coarser credit).

    technique_to_tactics: attack_id -> tactic shortnames (from Neo4j
    IN_TACTIC). Lookup falls back to the base technique so sub-technique
    IDs resolve through their parent's tactic membership.
    """
    def tactics_of(ids: set[str]) -> set[str]:
        out: set[str] = set()
        for aid in ids:
            aid = aid.upper()
            hit = technique_to_tactics.get(aid) or technique_to_tactics.get(
                _base_technique(aid)
            )
            if hit:
                out.update(hit)
        return out

    pred_tactics = tactics_of(predicted)
    gold_tactics = tactics_of(gold)

    if not pred_tactics or not gold_tactics:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0,
                "predicted_tactics": sorted(pred_tactics),
                "gold_tactics": sorted(gold_tactics)}

    inter = pred_tactics & gold_tactics
    precision = len(inter) / len(pred_tactics)
    recall = len(inter) / len(gold_tactics)
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall > 0 else 0.0
    )
    return {"precision": precision, "recall": recall, "f1": f1,
            "predicted_tactics": sorted(pred_tactics),
            "gold_tactics": sorted(gold_tactics)}


# ──────────────────────────────────────────────────────────────────────────────
# Guard Metrics (Thai output contract)
# ──────────────────────────────────────────────────────────────────────────────

def thai_char_ratio(text: str) -> float:
    """Thai letters / (Thai + Latin letters). Digits/punctuation ignored.

    The output contract is Thai prose with English technical terms, so a
    healthy answer sits well above 0.5; a ratio near 0 means the
    translation stage failed or was skipped.
    """
    text = text or ""
    thai = len(_THAI_RE.findall(text))
    latin = len(_LATIN_RE.findall(text))
    total = thai + latin
    return thai / total if total else 0.0


def structure_compliance(text: str, required_headings: list[str]) -> dict:
    """Which required section headings appear in the answer (case-insensitive)."""
    lower = (text or "").lower()
    present = {h: h.lower() in lower for h in required_headings}
    found = sum(present.values())
    return {
        "present": present,
        "complete": found == len(required_headings) and bool(required_headings),
        "score": found / len(required_headings) if required_headings else 0.0,
    }


def id_survival(source_text: str, translated_text: str) -> dict:
    """Technique IDs preserved across the translation stage.

    survival_rate is 1.0 when the source cites no IDs (nothing to lose).
    `gained` lists IDs present only in the translation — a red flag for
    translation-stage hallucination that set-level F1 cannot see.
    """
    src = extract_technique_ids(source_text)
    dst = extract_technique_ids(translated_text)
    survived = src & dst
    return {
        "survival_rate": len(survived) / len(src) if src else 1.0,
        "survived": sorted(survived),
        "lost": sorted(src - dst),
        "gained": sorted(dst - src),
    }
