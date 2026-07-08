from __future__ import annotations

from .schemas import CyberCaseReport


INDICATOR_PLACEHOLDER = (
    "No explicit indicators were extracted from the submitted case information."
)
EVIDENCE_PLACEHOLDER = (
    "No additional required evidence was identified for this preliminary report. "
    "Analyst review is still recommended."
)
LIMITATION_PLACEHOLDER = (
    "This report is AI-assisted preliminary investigation support and requires analyst review."
)


class ReportMarkdownRendererMixin:
    def render_report_markdown(self, report: CyberCaseReport) -> str:
        case_readiness = (
            f"Case readiness: {report.case_information_completeness.percentage}% - "
            f"{report.case_information_completeness.status}."
        )
        if report.case_information_completeness.missing_fields:
            case_readiness += (
                " Missing information: "
                + ", ".join(report.case_information_completeness.missing_fields)
                + "."
            )

        return (
            "# CyberCase Investigation Report\n\n"
            f"## 1. Case Summary\n{report.executive_case_summary}\n\n"
            f"{case_readiness}\n\n"
            f"## 2. Found Indicators\n{self._render_indicators(report)}\n\n"
            f"## 3. MITRE ATT&CK Mapping\n{self._render_mitre_mapping(report)}\n\n"
            f"## 4. Mapping Rationale\n{self._render_mitre_rationale(report)}\n\n"
            f"## 5. Evidence That Should Be Checked\n{self._render_list(report.evidence_still_required, EVIDENCE_PLACEHOLDER)}\n\n"
            f"## 6. Preliminary Recommendations\n{self._render_list(report.investigation_next_steps, 'No preliminary recommendations were generated. Analyst review is still recommended.')}\n\n"
            f"## 7. System Limitations\n{self._render_limitations(report)}"
        )

    def _render_indicators(self, report: CyberCaseReport) -> str:
        if not report.evidence_and_indicators_table:
            return INDICATOR_PLACEHOLDER
        return "\n".join(
            f"- {item.indicator_type.upper()}: {item.value} "
            f"{self._format_evidence_citations(item.evidence_ids)}"
            for item in report.evidence_and_indicators_table
        )

    def _render_mitre_mapping(self, report: CyberCaseReport) -> str:
        if not report.mitre_attack_assessment:
            return (
                "No MITRE ATT&CK technique mappings were generated from the available evidence."
            )
        return "\n".join(
            f"- {item.technique_id} - {item.technique_name}; "
            f"status: {item.mapping_status}; "
            f"evidence: {self._format_evidence_citations(item.evidence_ids)}"
            for item in report.mitre_attack_assessment
        )

    def _render_mitre_rationale(self, report: CyberCaseReport) -> str:
        if not report.mitre_attack_assessment:
            return (
                "No mapping rationale is available because no MITRE ATT&CK mapping was generated."
            )
        return "\n".join(
            f"- {item.technique_id} - {item.technique_name}: {item.justification}\n"
            f"  Evidence IDs: {', '.join(item.evidence_ids)}.\n"
            "  Analyst verification: Confirm the observed behavior and source evidence "
            "before treating this mapping as confirmed."
            for item in report.mitre_attack_assessment
        )

    @staticmethod
    def _render_list(items: list[str], empty_placeholder: str) -> str:
        return "\n".join(f"- {item}" for item in items) if items else empty_placeholder

    @staticmethod
    def _render_limitations(report: CyberCaseReport) -> str:
        limitations = list(report.limitations_and_disclaimers)
        if LIMITATION_PLACEHOLDER not in limitations:
            limitations.insert(0, LIMITATION_PLACEHOLDER)
        return "\n".join(f"- {item}" for item in limitations)
