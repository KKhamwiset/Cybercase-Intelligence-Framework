from __future__ import annotations

import re
from copy import deepcopy
from typing import Any


SYSTEM_SOURCE = "system_rule"
ANALYST_SOURCE = "analyst_input"


def apply_case_intake_outputs(
    payload: dict[str, Any],
    *,
    force: bool = False,
    previous_payload: dict[str, Any] | None = None,
    explicit_fields: set[str] | None = None,
) -> dict[str, Any]:
    narrative = str(payload.get("incident_summary") or "").strip()
    enriched = deepcopy(payload)
    if previous_payload is not None:
        return _reconcile_intake_outputs(
            enriched,
            narrative=narrative,
            previous_payload=previous_payload,
            force=force,
            explicit_fields=explicit_fields or set(),
        )
    if not narrative:
        return enriched

    evidence = _derive_evidence(narrative)
    evidence_ids = [item["evidence_id"] for item in evidence]

    _replace_if_system_owned(enriched, "evidence_items", evidence, force=force)
    _replace_if_system_owned(enriched, "timeline_events", _derive_timeline(narrative, evidence_ids), force=force)
    _replace_if_system_owned(enriched, "attack_mappings", _derive_attack_mappings(narrative, evidence_ids), force=force)
    _replace_if_system_owned(enriched, "containment_actions", _derive_containment(narrative, evidence_ids), force=force)

    # Gaps and recommendations are analysis results, not intake defaults.
    # Preserve pre-migration values as history in the stored case payload, but
    # never create or refresh them from the narrative here.
    if force or not enriched.get("affected_users"):
        enriched["affected_users"] = _derive_affected_users(narrative)
    if force or not enriched.get("affected_assets"):
        enriched["affected_assets"] = _derive_affected_assets(narrative)

    return enriched


def _reconcile_intake_outputs(
    payload: dict[str, Any],
    *,
    narrative: str,
    previous_payload: dict[str, Any],
    force: bool,
    explicit_fields: set[str],
) -> dict[str, Any]:
    previous_narrative = str(previous_payload.get("incident_summary") or "").strip()
    previous_users = _derive_affected_users(previous_narrative) if previous_narrative else []
    previous_assets = _derive_affected_assets(previous_narrative) if previous_narrative else []

    if "evidence_items" in explicit_fields:
        evidence = list(payload.get("evidence_items") or [])
    else:
        preserved_evidence = _manual_items(payload.get("evidence_items"), force=force)
        generated_evidence = _derive_evidence(narrative) if narrative else []
        evidence = _merge_with_unique_ids(
            preserved_evidence,
            generated_evidence,
            id_field="evidence_id",
            prefix="E",
        )
        payload["evidence_items"] = evidence

    evidence_ids = [
        str(item.get("evidence_id"))
        for item in evidence
        if isinstance(item, dict) and item.get("evidence_id")
    ] or (["INTAKE-NARRATIVE"] if narrative else [])

    generated_collections = {
        "timeline_events": _derive_timeline(narrative, evidence_ids) if narrative else [],
        "attack_mappings": _derive_attack_mappings(narrative, evidence_ids) if narrative else [],
        "containment_actions": _derive_containment(narrative, evidence_ids) if narrative else [],
    }
    id_fields = {
        "timeline_events": ("event_id", "TL"),
        "attack_mappings": ("mapping_id", "MAP"),
        "containment_actions": ("action_id", "ACT"),
    }
    for field, generated in generated_collections.items():
        if field in explicit_fields:
            continue
        id_field, prefix = id_fields[field]
        payload[field] = _merge_with_unique_ids(
            _manual_items(payload.get(field), force=force),
            generated,
            id_field=id_field,
            prefix=prefix,
        )

    if "affected_users" not in explicit_fields:
        payload["affected_users"] = _reconcile_derived_strings(
            payload.get("affected_users"),
            previous_users,
            _derive_affected_users(narrative) if narrative else [],
            force=force,
        )
    if "affected_assets" not in explicit_fields:
        payload["affected_assets"] = _reconcile_derived_strings(
            payload.get("affected_assets"),
            previous_assets,
            _derive_affected_assets(narrative) if narrative else [],
            force=force,
        )
    return payload


def _manual_items(items: Any, *, force: bool) -> list[dict[str, Any]]:
    if force or not isinstance(items, list):
        return []
    return [
        deepcopy(item)
        for item in items
        if isinstance(item, dict) and not _is_intake_owned(item)
    ]


def _is_intake_owned(item: dict[str, Any]) -> bool:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    source_type = item.get("source_type") or metadata.get("source_type")
    return bool(item.get("intake_derived") or source_type == SYSTEM_SOURCE)


def _merge_with_unique_ids(
    preserved: list[dict[str, Any]],
    generated: list[dict[str, Any]],
    *,
    id_field: str,
    prefix: str,
) -> list[dict[str, Any]]:
    used = {str(item.get(id_field)) for item in preserved if item.get(id_field)}
    merged = list(preserved)
    next_index = 1
    for raw in generated:
        item = deepcopy(raw)
        candidate = str(item.get(id_field) or "")
        while not candidate or candidate in used:
            candidate = f"{prefix}-{next_index:03d}"
            next_index += 1
        item[id_field] = candidate
        used.add(candidate)
        merged.append(item)
    return merged


def _reconcile_derived_strings(
    current: Any,
    previous_generated: list[str],
    next_generated: list[str],
    *,
    force: bool,
) -> list[str]:
    prior = {item.strip().casefold() for item in previous_generated}
    preserved = [] if force or not isinstance(current, list) else [
        str(item).strip()
        for item in current
        if str(item).strip() and str(item).strip().casefold() not in prior
    ]
    seen = {item.casefold() for item in preserved}
    for item in next_generated:
        normalized = item.strip()
        if normalized and normalized.casefold() not in seen:
            preserved.append(normalized)
            seen.add(normalized.casefold())
    return preserved


def _replace_if_system_owned(
    payload: dict[str, Any],
    key: str,
    replacement: list[dict[str, Any]],
    *,
    force: bool,
) -> None:
    existing = payload.get(key)
    if force or not existing or _all_system_owned(existing):
        payload[key] = replacement


def _all_system_owned(items: Any) -> bool:
    if not isinstance(items, list):
        return False
    if not items:
        return True
    for item in items:
        if not isinstance(item, dict):
            return False
        source_type = item.get("source_type") or item.get("metadata", {}).get("source_type")
        if source_type != SYSTEM_SOURCE and not item.get("intake_derived"):
            return False
    return True


def _metadata(evidence_ids: list[str], confidence: str = "medium") -> dict[str, Any]:
    return {
        "status": "candidate",
        "confidence": confidence,
        "evidence_ids": evidence_ids[:3],
        "source_type": SYSTEM_SOURCE,
        "analyst_verified": False,
    }


def _derive_evidence(narrative: str) -> list[dict[str, Any]]:
    bullets = _available_evidence_bullets(narrative)
    if not bullets:
        bullets = [
            "Analyst-provided incident narrative",
            *_sentences_matching(
                narrative,
                ("phishing", "sign-in", "login", "inbox rule", "sharepoint", "download", "containment"),
            )[:5],
        ]

    return [
        {
            "evidence_id": f"E-{index:03d}",
            "title": bullet[:96],
            "description": bullet,
            "source_type": ANALYST_SOURCE,
            "status": "unknown",
            "confidence": "low",
            "analyst_verified": False,
            "intake_derived": True,
        }
        for index, bullet in enumerate(_dedupe(bullets), start=1)
    ][:10]


def _available_evidence_bullets(narrative: str) -> list[str]:
    if "Available Evidence" not in narrative:
        return []
    after_heading = narrative.split("Available Evidence", 1)[1]
    before_next_heading = re.split(r"\n\s*##\s+", after_heading, maxsplit=1)[0]
    bullets = []
    for line in before_next_heading.splitlines():
        stripped = line.strip()
        if stripped.startswith(("* ", "- ")):
            bullets.append(stripped[2:].strip())
    return bullets


def _derive_timeline(narrative: str, evidence_ids: list[str]) -> list[dict[str, Any]]:
    events = []
    for index, sentence in enumerate(_sentences_matching(narrative, (r"\d{1,2}:\d{2}",)), start=1):
        time_match = re.search(r"\b(\d{1,2}:\d{2})\b", sentence)
        title = f"{time_match.group(1)} event" if time_match else f"Timeline event {index}"
        events.append(
            {
                "event_id": f"TL-{index:03d}",
                "title": title,
                "description": sentence,
                "metadata": _metadata(evidence_ids, "medium"),
            }
        )
    return events[:12]


def _derive_attack_mappings(narrative: str, evidence_ids: list[str]) -> list[dict[str, Any]]:
    text = narrative.lower()
    rules = [
        (
            ("phishing", "fake microsoft", "login page"),
            "T1566",
            "Phishing",
            "Initial Access",
            "The narrative describes a vendor-themed phishing message and fake Microsoft 365 login page.",
            "high",
        ),
        (
            ("mfa", "push notification", "authentication requests"),
            "T1621",
            "Multi-Factor Authentication Request Generation",
            "Credential Access",
            "The attacker relied on repeated MFA push prompts before successful account access.",
            "medium",
        ),
        (
            ("inbox rule", "rss feeds", "mailbox search"),
            "T1114",
            "Email Collection",
            "Collection",
            "The compromised mailbox was searched and an inbox rule hid payment-related messages.",
            "medium",
        ),
        (
            ("internal phishing", "sent phishing emails", "compromised employee"),
            "T1534",
            "Internal Spearphishing",
            "Lateral Movement",
            "Phishing messages were sent from a trusted internal mailbox to additional employees.",
            "medium",
        ),
        (
            ("sharepoint", "download"),
            "T1213",
            "Data from Information Repositories",
            "Collection",
            "The attacker accessed and downloaded files from a SharePoint repository.",
            "medium",
        ),
    ]

    mappings = []
    for index, (keywords, technique_id, technique_name, tactic, rationale, confidence) in enumerate(rules, start=1):
        if any(keyword in text for keyword in keywords):
            mappings.append(
                {
                    "mapping_id": f"MAP-{index:03d}",
                    "technique_id": technique_id,
                    "technique_name": technique_name,
                    "tactic": tactic,
                    "rationale": rationale,
                    "metadata": _metadata(evidence_ids, confidence),
                }
            )
    return mappings


def _derive_containment(narrative: str, evidence_ids: list[str]) -> list[dict[str, Any]]:
    actions = []
    candidates = [
        ("disable", "Disable compromised account"),
        ("password reset", "Reset account password"),
        ("revoked", "Revoke active sessions and tokens"),
        ("inbox-rule deletion", "Remove malicious inbox rules"),
        ("blocked", "Block phishing domain"),
    ]
    text = narrative.lower()
    for index, (keyword, title) in enumerate(candidates, start=1):
        if keyword in text:
            actions.append(
                {
                    "action_id": f"ACT-{index:03d}",
                    "title": title,
                    "description": "Derived from containment actions described in the intake narrative.",
                    "status": "candidate",
                    "metadata": _metadata(evidence_ids, "medium"),
                }
            )
    return actions


def _derive_recommendations(narrative: str, evidence_ids: list[str]) -> list[dict[str, Any]]:
    text = narrative.lower()
    recommendations = [
        ("REC-001", "Validate whether fraudulent payments were initiated", "Review payment approvals, vendor-bank changes, and pending transfers."),
        ("REC-002", "Harden MFA approval controls", "Require number matching, impossible-travel review, and user reporting for repeated push requests."),
        ("REC-003", "Audit mailbox rules and forwarding settings", "Search for suspicious rules across finance and procurement mailboxes."),
    ]
    if "sharepoint" in text or "download" in text:
        recommendations.append(
            ("REC-004", "Review document access and data exposure", "Confirm which SharePoint files were downloaded and whether notification is required.")
        )
    return [
        {
            "action_id": action_id,
            "title": title,
            "description": description,
            "status": "candidate",
            "metadata": _metadata(evidence_ids, "medium"),
        }
        for action_id, title, description in recommendations
    ]


def _derive_gap_notes(narrative: str) -> list[str]:
    text = narrative.lower()
    gaps = []
    if "no confirmed fraudulent transaction" in text:
        gaps.append("Confirm whether any fraudulent payment or vendor-bank change was initiated.")
    if "may have been accessed" in text or "potential risk" in text:
        gaps.append("Determine exact document exposure and affected data elements.")
    if "foreign ip" in text or "unusual" in text:
        gaps.append("Attribute suspicious sign-in details to source IP, ASN, device, and session artifacts.")
    if not gaps:
        gaps.append("Validate all generated findings against source evidence before report finalization.")
    return gaps


def _derive_affected_users(narrative: str) -> list[str]:
    text = narrative.lower()
    users = []
    if "finance employee" in text or "finance department" in text:
        users.append("Finance department employee account")
    match = re.search(r"\b(six|\d+)\s+internal\s+(?:finance and procurement\s+)?employees", text)
    if match:
        users.append(f"{match.group(1).capitalize()} internal recipients")
    return users


def _derive_affected_assets(narrative: str) -> list[str]:
    assets = []
    text = narrative.lower()
    if "microsoft 365" in text:
        assets.append("Microsoft 365 mailbox/account")
    if "sharepoint" in text:
        assets.append("Finance SharePoint folder")
    if "vendor payment" in text or "bank account" in text:
        assets.append("Vendor payment and financial records")
    return assets


def _sentences_matching(narrative: str, patterns: tuple[str, ...]) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", " ".join(narrative.split()))
    matches = []
    for sentence in sentences:
        lowered = sentence.lower()
        if any(re.search(pattern, lowered) for pattern in patterns):
            matches.append(sentence.strip())
    return matches


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    deduped = []
    for item in items:
        normalized = item.strip()
        key = normalized.lower()
        if normalized and key not in seen:
            seen.add(key)
            deduped.append(normalized)
    return deduped
