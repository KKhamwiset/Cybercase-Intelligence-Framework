from __future__ import annotations

import re

from .schemas import (
    COMPLETENESS_THRESHOLD,
    INCOMPLETE_LABEL,
    LEGAL_DISCLAIMER,
    SUFFICIENT_LABEL,
    CaseFact,
    CaseFactPack,
    CaseInformationCompleteness,
    CompletenessField,
    EvidenceReference,
    Indicator,
    IndicatorType,
    LegalRelevanceAssessment,
    MitreAssessment,
    ReportEntity,
    ReviewStatus,
    TimelineEvent,
)


class DeterministicFactPackMixin:
    def _build_deterministic_case_fact_pack(
        self,
        query: str,
        evidence_registry: list[EvidenceReference],
        base_evidence_ids: list[str],
        mitre_evidence_ids: dict[str, str],
        allowed_techniques: list[ReportEntity],
        legal: bool,
    ) -> CaseFactPack:
        source_ids = base_evidence_ids or [evidence_registry[0].evidence_id]
        indicators = self._extract_indicators(query, source_ids)
        timeline = self._extract_timeline_events(query, source_ids)
        facts = self._extract_case_facts(query, indicators, source_ids)
        completeness = self.calculate_completeness(
            query=query,
            evidence_registry=evidence_registry,
            indicators=indicators,
            timeline=timeline,
            base_evidence_ids=source_ids,
        )
        missing_information = list(completeness.missing_fields)
        limitations = self._build_limitations(completeness, indicators, allowed_techniques)

        mitre_assessments: list[MitreAssessment] = []
        for entity in allowed_techniques[:6]:
            mitre_evidence_id = mitre_evidence_ids.get(entity.attack_id)
            if not mitre_evidence_id:
                continue
            evidence_ids = [source_ids[0], mitre_evidence_id]
            if entity.source.startswith("mitre_table:"):
                justification = (
                    f"The filtered MITRE table from the RAG service returned "
                    f"{entity.attack_id} {entity.name} "
                    f"as a candidate MITRE ATT&CK technique. The mapping is "
                    f"preliminary and must be checked against observed behavior "
                    f"and source evidence [{source_ids[0]}] [{mitre_evidence_id}]."
                )
            else:
                justification = (
                    f"Hybrid retrieval returned {entity.attack_id} {entity.name} "
                    f"as a candidate MITRE ATT&CK technique. The mapping is "
                    f"preliminary and must be checked against observed behavior "
                    f"and source evidence [{source_ids[0]}] [{mitre_evidence_id}]."
                )
            mitre_assessments.append(
                MitreAssessment(
                    technique_id=entity.attack_id,
                    technique_name=entity.name,
                    mapping_status="inferred",
                    justification=justification,
                    evidence_ids=evidence_ids,
                )
            )

        legal_assessments = self._build_legal_assessments(legal, source_ids)
        review_status: ReviewStatus = "draft"
        return CaseFactPack(
            facts=facts,
            evidence_registry=evidence_registry,
            indicators=indicators,
            timeline=timeline,
            mitre_assessments=mitre_assessments,
            legal_assessments=legal_assessments,
            missing_information=missing_information,
            limitations=limitations,
            completeness_percentage=completeness.percentage,
            completeness=completeness,
            review_status=review_status,
        )

    def calculate_completeness(
        self,
        query: str,
        evidence_registry: list[EvidenceReference],
        indicators: list[Indicator],
        timeline: list[TimelineEvent],
        base_evidence_ids: list[str],
    ) -> CaseInformationCompleteness:
        text = (query or "").lower()
        evidence_ids = base_evidence_ids[:1]

        date_present = bool(timeline) or bool(
            re.search(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", text)
        )
        asset_present = bool(
            re.search(
                r"\b(asset|system|server|endpoint|workstation|account|database|website|domain|cloud|email|bank|host)\b",
                text,
            )
        )
        behavior_present = bool(
            re.search(
                r"\b(phishing|sql injection|malware|ransomware|exploit|port|credential|login|exfiltrat|unauthorized|privilege|lateral|command|c2|payload|attack|compromise)\b",
                text,
            )
        ) or bool(indicators)
        evidence_present = any(
            item.source_type in {"uploaded_file", "log"} for item in evidence_registry
        ) or bool(
            re.search(
                r"\b(log|evidence|file|upload|ocr|email header|screenshot|siem|dns|proxy|endpoint|pcap|hash)\b",
                text,
            )
        )
        impact_present = bool(
            re.search(
                r"\b(impact|loss|damage|stolen|theft|fraud|transferred|exfiltrat|data leak|encrypted|downtime|unauthorized transaction|outcome)\b",
                text,
            )
        )

        fields = [
            CompletenessField(
                field_id="incident_date_time",
                label="incident date/time",
                present=date_present,
                evidence_ids=evidence_ids if date_present else [],
            ),
            CompletenessField(
                field_id="affected_asset_system",
                label="affected asset/system",
                present=asset_present,
                evidence_ids=evidence_ids if asset_present else [],
            ),
            CompletenessField(
                field_id="observed_behavior_attack_vector",
                label="observed behavior or attack vector",
                present=behavior_present,
                evidence_ids=evidence_ids if behavior_present else [],
            ),
            CompletenessField(
                field_id="available_evidence_log_source",
                label="available evidence/log source",
                present=evidence_present,
                evidence_ids=evidence_ids if evidence_present else [],
            ),
            CompletenessField(
                field_id="impact_suspected_outcome",
                label="impact or suspected outcome",
                present=impact_present,
                evidence_ids=evidence_ids if impact_present else [],
            ),
        ]
        present_count = sum(1 for field in fields if field.present)
        percentage = int(round((present_count / len(fields)) * 100))
        missing = [field.label for field in fields if not field.present]
        status = SUFFICIENT_LABEL if percentage >= COMPLETENESS_THRESHOLD else INCOMPLETE_LABEL
        return CaseInformationCompleteness(
            percentage=percentage,
            status=status,
            missing_fields=missing,
            fields=fields,
        )

    def _extract_case_facts(
        self,
        query: str,
        indicators: list[Indicator],
        base_evidence_ids: list[str],
    ) -> list[CaseFact]:
        facts: list[CaseFact] = []
        excerpt = self._shorten(query, 600)
        if excerpt:
            facts.append(
                CaseFact(
                    fact_id="F-001",
                    statement=(
                        f"User reported case details: {excerpt} "
                        f"{self._format_evidence_citations(base_evidence_ids)}"
                    ),
                    category="case_summary",
                    status="reported",
                    confidence="medium",
                    evidence_ids=base_evidence_ids,
                )
            )
        for index, indicator in enumerate(indicators[:10], start=len(facts) + 1):
            facts.append(
                CaseFact(
                    fact_id=f"F-{index:03d}",
                    statement=(
                        f"Reported indicator {indicator.indicator_type}: {indicator.value} "
                        f"{self._format_evidence_citations(indicator.evidence_ids)}"
                    ),
                    category="indicator",
                    status="reported",
                    confidence="medium",
                    evidence_ids=indicator.evidence_ids,
                )
            )
        return facts

    def _extract_indicators(self, text: str, evidence_ids: list[str]) -> list[Indicator]:
        patterns: list[tuple[IndicatorType, re.Pattern[str]]] = [
            ("url", re.compile(r"https?://[^\s<>()\]\}]+", re.IGNORECASE)),
            (
                "email",
                re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"),
            ),
            (
                "ip",
                re.compile(
                    r"\b(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}\b"
                ),
            ),
            ("cve", re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)),
            ("hash", re.compile(r"\b[a-fA-F0-9]{32,64}\b")),
            (
                "domain",
                re.compile(
                    r"\b(?:[a-zA-Z0-9-]+\.)+(?:com|net|org|io|co|th|go\.th|ac\.th|gov|edu|info|biz|xyz|site|online|ru|cn|jp|sg|uk|us)\b",
                    re.IGNORECASE,
                ),
            ),
        ]
        seen: set[str] = set()
        indicators: list[Indicator] = []
        for indicator_type, pattern in patterns:
            for match in pattern.finditer(text or ""):
                value = match.group(0).strip(".,;:)]}>\"'")
                if not value or "attack.mitre.org" in value.lower():
                    continue
                key = f"{indicator_type}:{value.lower()}"
                if key in seen:
                    continue
                seen.add(key)
                indicators.append(
                    Indicator(
                        indicator_id=f"I-{len(indicators) + 1:03d}",
                        indicator_type=indicator_type,
                        value=value,
                        status="reported",
                        evidence_ids=evidence_ids,
                    )
                )
        return indicators

    def _extract_timeline_events(self, query: str, evidence_ids: list[str]) -> list[TimelineEvent]:
        events: list[TimelineEvent] = []
        temporal_markers = (
            "after",
            "before",
            "then",
            "later",
            "time",
            "date",
            "found",
            "reported",
            "on ",
            "at ",
            "\u0e2b\u0e25\u0e31\u0e07",
            "\u0e01\u0e48\u0e2d\u0e19",
            "\u0e08\u0e32\u0e01\u0e19\u0e31\u0e49\u0e19",
            "\u0e15\u0e48\u0e2d\u0e21\u0e32",
            "\u0e40\u0e27\u0e25\u0e32",
            "\u0e27\u0e31\u0e19\u0e17\u0e35\u0e48",
            "\u0e40\u0e21\u0e37\u0e48\u0e2d",
            "\u0e1e\u0e1a",
        )
        timestamp_pattern = re.compile(
            r"\b\d{4}-\d{2}-\d{2}(?:[T ][0-9:]+Z?)?\b|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"
        )
        for part in re.split(r"[\n.;]", query or ""):
            sentence = " ".join(part.split())
            if not sentence:
                continue
            lower = sentence.lower()
            timestamp_match = timestamp_pattern.search(sentence)
            if timestamp_match or any(marker in lower for marker in temporal_markers):
                events.append(
                    TimelineEvent(
                        event_id=f"T-{len(events) + 1:03d}",
                        timestamp=timestamp_match.group(0) if timestamp_match else None,
                        event=f"Reported event: {self._shorten(sentence, 240)}",
                        status="reported",
                        evidence_ids=evidence_ids,
                    )
                )
            if len(events) >= 8:
                break
        return events

    def _build_legal_assessments(
        self, legal: bool, evidence_ids: list[str]
    ) -> list[LegalRelevanceAssessment]:
        if not legal:
            return []
        return [
            LegalRelevanceAssessment(
                enabled=True,
                provision_reference="Unknown / missing legal provision",
                preliminary_relevance=(
                    "The reported conduct may have legal relevance, but no specific legal provision "
                    "was supplied by retrieved legal sources. This requires investigator/legal review "
                    "before any charging, admissibility, or liability assessment."
                ),
                status="unknown",
                evidence_ids=evidence_ids,
                disclaimer=LEGAL_DISCLAIMER,
            )
        ]

    def _build_limitations(
        self,
        completeness: CaseInformationCompleteness,
        indicators: list[Indicator],
        allowed_techniques: list[ReportEntity],
    ) -> list[str]:
        limitations = [
            "This report is preliminary investigation support and requires investigator/legal review.",
            "It does not determine guilt or innocence, court admissibility, attribution, or final legal conclusions.",
        ]
        if completeness.percentage < COMPLETENESS_THRESHOLD:
            limitations.append(
                "Missing information limits the report: "
                + ", ".join(completeness.missing_fields)
                + "."
            )
        if not indicators:
            limitations.append("No explicit indicator was confirmed from the submitted case information.")
        if not allowed_techniques:
            limitations.append("No MITRE ATT&CK technique was validated from retrieved MITRE data.")
        return limitations
