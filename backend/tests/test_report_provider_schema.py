import unittest

from pydantic import ValidationError

from app.schemas.chat.reports import REPORT_SECTION_HEADINGS, REPORT_SECTION_IDS
from app.services.reports.report_provider_schema import (
    ProviderStructuredReport,
    provider_report_to_structured_report,
)
from app.services.llm.structured_output_router import structured_output_schema


class ReportProviderSchemaTests(unittest.TestCase):
    def test_claim_union_uses_any_of_without_discriminator(self) -> None:
        schema = ProviderStructuredReport.model_json_schema()
        claim_items = schema["properties"]["claims"]["items"]

        self.assertIn("anyOf", claim_items)
        self.assertEqual(len(claim_items["anyOf"]), 6)
        self._assert_absent_recursively(schema, {"oneOf", "discriminator"})

    def test_anthropic_and_openrouter_close_every_claim_branch(self) -> None:
        for provider in ("anthropic", "openrouter"):
            with self.subTest(provider=provider):
                schema = structured_output_schema(
                    ProviderStructuredReport,
                    provider=provider,
                )
                for name in self._claim_definition_names():
                    branch = schema["$defs"][name]
                    self.assertIs(branch["additionalProperties"], False)

    def test_openrouter_requires_every_branch_property(self) -> None:
        schema = structured_output_schema(
            ProviderStructuredReport,
            provider="openrouter",
        )

        for name in self._claim_definition_names():
            branch = schema["$defs"][name]
            self.assertEqual(branch["required"], list(branch["properties"].keys()))

    def test_branch_fields_reject_invalid_combinations(self) -> None:
        invalid_claims = (
            {
                **self._claim_base("incident_evidence"),
                "support_type": "user_reported",
                "timeline_event_id": "T-001",
            },
            {
                **self._claim_base("mitre_evidence"),
                "support_type": "mitre_mapping_candidate",
                "evidence_id": "E-001",
            },
            {
                **self._claim_base("general_technical_knowledge"),
                "support_type": "general_technical_knowledge",
                "evidence_id": "E-001",
            },
            {
                **self._claim_base("unknown"),
                "support_type": "user_reported",
            },
        )

        for claim in invalid_claims:
            with self.subTest(claim_kind=claim["claim_kind"]):
                payload = self._provider_payload([claim])
                with self.assertRaises(ValidationError):
                    ProviderStructuredReport.model_validate(payload)

    def test_all_scalar_branches_convert_exactly_to_public_arrays(self) -> None:
        provider_payload = self._provider_payload(
            [
                {
                    **self._claim_base("incident_evidence", "C-001"),
                    "support_type": "user_reported",
                    "evidence_id": "E-001",
                },
                {
                    **self._claim_base("incident_timeline", "C-002"),
                    "support_type": "extraction_candidate",
                    "timeline_event_id": "T-001",
                },
                {
                    **self._claim_base("mitre_evidence", "C-003"),
                    "support_type": "mitre_mapping_candidate",
                    "evidence_id": "E-002",
                    "mitre_technique_id": "T1059.001",
                },
                {
                    **self._claim_base("mitre_timeline", "C-004"),
                    "support_type": "mitre_mapping_candidate",
                    "timeline_event_id": "T-002",
                    "mitre_technique_id": "T1059.003",
                },
                {
                    **self._claim_base(
                        "general_technical_knowledge",
                        "C-005",
                    ),
                    "support_type": "general_technical_knowledge",
                },
                {
                    **self._claim_base("unknown", "C-006"),
                    "support_type": "unknown",
                },
            ]
        )
        provider_report = ProviderStructuredReport.model_validate(provider_payload)

        public_report = provider_report_to_structured_report(provider_report)

        expected_claims = [
            self._public_claim("C-001", "user_reported", ["E-001"]),
            self._public_claim(
                "C-002",
                "extraction_candidate",
                timeline_event_ids=["T-001"],
            ),
            self._public_claim(
                "C-003",
                "mitre_mapping_candidate",
                ["E-002"],
                mitre_technique_ids=["T1059.001"],
            ),
            self._public_claim(
                "C-004",
                "mitre_mapping_candidate",
                timeline_event_ids=["T-002"],
                mitre_technique_ids=["T1059.003"],
            ),
            self._public_claim("C-005", "general_technical_knowledge"),
            self._public_claim("C-006", "unknown"),
        ]
        self.assertEqual(
            public_report.model_dump(),
            {
                "report_version": provider_payload["report_version"],
                "status": provider_payload["status"],
                "title": provider_payload["title"],
                "sections": provider_payload["sections"],
                "claims": expected_claims,
                "limitations": provider_payload["limitations"],
            },
        )

    def _provider_payload(self, claims: list[dict[str, object]]) -> dict[str, object]:
        return {
            "report_version": "baseline_report_v1",
            "status": "provisional_unverified",
            "title": "Provisional report",
            "sections": [
                {
                    "section_id": section_id,
                    "heading": REPORT_SECTION_HEADINGS[section_id],
                    "paragraphs": ["Provisional content."],
                    "items": [],
                }
                for section_id in REPORT_SECTION_IDS
            ],
            "claims": claims,
            "limitations": ["Forensic verification remains required."],
        }

    def _claim_base(
        self,
        claim_kind: str,
        claim_id: str = "C-001",
    ) -> dict[str, object]:
        return {
            "claim_id": claim_id,
            "section_id": "evidence_findings",
            "text": "A bounded claim.",
            "claim_kind": claim_kind,
        }

    def _public_claim(
        self,
        claim_id: str,
        support_type: str,
        evidence_ids: list[str] | None = None,
        *,
        timeline_event_ids: list[str] | None = None,
        mitre_technique_ids: list[str] | None = None,
    ) -> dict[str, object]:
        return {
            "claim_id": claim_id,
            "section_id": "evidence_findings",
            "text": "A bounded claim.",
            "support_type": support_type,
            "evidence_ids": evidence_ids or [],
            "timeline_event_ids": timeline_event_ids or [],
            "mitre_technique_ids": mitre_technique_ids or [],
        }

    def _claim_definition_names(self) -> tuple[str, ...]:
        return (
            "ProviderGeneralTechnicalKnowledgeClaim",
            "ProviderIncidentEvidenceClaim",
            "ProviderIncidentTimelineClaim",
            "ProviderMitreEvidenceClaim",
            "ProviderMitreTimelineClaim",
            "ProviderUnknownClaim",
        )

    def _assert_absent_recursively(
        self,
        value: object,
        forbidden: set[str],
    ) -> None:
        if isinstance(value, dict):
            self.assertTrue(forbidden.isdisjoint(value))
            for child in value.values():
                self._assert_absent_recursively(child, forbidden)
        elif isinstance(value, list):
            for child in value:
                self._assert_absent_recursively(child, forbidden)


if __name__ == "__main__":
    unittest.main()
