from __future__ import annotations

import re
from copy import deepcopy
from typing import Any


SYSTEM_SOURCE = "system_rule"


def apply_case_intake_outputs(payload: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
    narrative = str(payload.get("incident_summary") or "").strip()
    if not narrative:
        return payload

    enriched = deepcopy(payload)
    evidence = _derive_evidence(narrative)
    evidence_ids = [item["evidence_id"] for item in evidence]

    _replace_if_system_owned(enriched, "evidence_items", evidence, force=force)
    _replace_if_system_owned(enriched, "timeline_events", _derive_timeline(narrative, evidence_ids), force=force)
    _replace_if_system_owned(enriched, "attack_mappings", _derive_attack_mappings(narrative, evidence_ids), force=force)
    _replace_if_system_owned(enriched, "containment_actions", _derive_containment(narrative, evidence_ids), force=force)
    _replace_if_system_owned(enriched, "recommendations", _derive_recommendations(narrative, evidence_ids), force=force)

    if force or not enriched.get("gaps"):
        enriched["gaps"] = _derive_gap_notes(narrative)
    if force or not enriched.get("affected_users"):
        enriched["affected_users"] = _derive_affected_users(narrative)
    if force or not enriched.get("affected_assets"):
        enriched["affected_assets"] = _derive_affected_assets(narrative)
    if force or not enriched.get("limitations"):
        enriched["limitations"] = [
            "Generated fields are draft outputs from the intake narrative and require analyst validation."
        ]

    return enriched


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
        if source_type != SYSTEM_SOURCE:
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
            "source_type": SYSTEM_SOURCE,
            "status": "candidate",
            "confidence": "medium",
            "analyst_verified": False,
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
