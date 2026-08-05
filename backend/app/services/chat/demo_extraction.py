"""Deterministic evidence and timeline candidates for the chat demo.

This deliberately stays small and transparent. It is retained for explicit
development fixtures and legacy metadata readability; the live chat worker
does not invoke it automatically.
"""

from __future__ import annotations

import re
from typing import Any


EXTRACTION_METADATA_KEY = "chat_extraction"
DEMO_EXTRACTION_VERSION = 1

_EVIDENCE_TERMS = re.compile(
    r"\b(?:alert|artifact|audit|breach|command|compromise|domain|download|email|"
    r"endpoint|event|file|hash|inbox\s+rule|ip|login|mfa|malware|packet|pcap|"
    r"phishing|powershell|process|ransomware|screenshot|sign[- ]?in|url)\b",
    re.IGNORECASE,
)
_INCIDENT_TERMS = re.compile(
    r"\b(?:attack|breach|compromise|incident|malware|phishing|ransomware|"
    r"suspicious|threat|victim|attacker|intrusion|login|event)\b",
    re.IGNORECASE,
)
_TEMPORAL_TERMS = re.compile(
    r"\b(?:after|before|first|finally|later|next|observed|occurred|reported|"
    r"then|today|yesterday)\b",
    re.IGNORECASE,
)
_TIMESTAMP = re.compile(
    r"\b(?:"
    r"\d{4}[-/]\d{1,2}[-/]\d{1,2}(?:[ T]\d{1,2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?)?"
    r"|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
    r"|(?:[01]?\d|2[0-3]):[0-5]\d(?:\s?[AP]M)?"
    r")\b",
    re.IGNORECASE,
)


def build_demo_chat_extraction(source_text: str) -> dict[str, Any]:
    """Return reported candidate evidence and timeline items from chat text."""

    segments = _segments(source_text)
    evidence_segments = [
        segment for segment in segments if _EVIDENCE_TERMS.search(segment)
    ]
    if not evidence_segments and segments and _INCIDENT_TERMS.search(source_text):
        evidence_segments = [segments[0]]

    evidence = [
        {
            "evidence_id": f"E-{index:03d}",
            "title": _shorten(segment, 96),
            "description": segment,
            "status": "reported",
            "confidence": "low",
            "source_type": "chat_text",
        }
        for index, segment in enumerate(_dedupe(evidence_segments)[:8], start=1)
    ]
    evidence_ids = [item["evidence_id"] for item in evidence]

    timeline: list[dict[str, Any]] = []
    for segment in segments:
        timestamp_match = _TIMESTAMP.search(segment)
        if timestamp_match is None and _TEMPORAL_TERMS.search(segment) is None:
            continue
        timeline.append(
            {
                "event_id": f"T-{len(timeline) + 1:03d}",
                "timestamp": timestamp_match.group(0) if timestamp_match else None,
                "event": segment,
                "status": "reported",
                "evidence_ids": evidence_ids[:3],
                "source_type": "chat_text",
            }
        )
        if len(timeline) >= 8:
            break

    return {
        "version": DEMO_EXTRACTION_VERSION,
        "mode": "deterministic_demo",
        "status": "candidate",
        "disclaimer": (
            "Demo candidates are extracted from chat text only. Verify them against "
            "the original logs or files before treating them as evidence."
        ),
        "evidence": evidence,
        "timeline": timeline,
    }


def add_demo_chat_extraction(
    metadata_json: dict[str, Any],
    source_text: str,
) -> dict[str, Any]:
    """Add the demo artifact without changing existing chat metadata."""

    metadata = dict(metadata_json)
    metadata[EXTRACTION_METADATA_KEY] = build_demo_chat_extraction(source_text)
    return metadata


def _segments(source_text: str) -> list[str]:
    segments: list[str] = []
    for line in source_text.splitlines():
        stripped = " ".join(line.split()).strip()
        if not stripped or _is_heading(stripped):
            continue
        if stripped.startswith(("- ", "* ", "\u2022 ")):
            segments.append(stripped[2:].strip())
            continue
        segments.extend(
            part.strip()
            for part in re.split(r"(?<=[.!?])\s+", stripped)
            if part.strip()
        )
    return _dedupe(segments)


def _is_heading(value: str) -> bool:
    normalized = value.rstrip(":").casefold()
    return normalized in {"evidence", "available evidence", "timeline"}


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _shorten(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."
