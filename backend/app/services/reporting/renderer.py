from __future__ import annotations

from .schemas import CyberCaseReport


class ReportMarkdownRendererMixin:
    def render_report_markdown(self, report: CyberCaseReport) -> str:
        indicators = "\n".join(
            f"- {item.indicator_type.upper()}: {item.value} {self._format_evidence_citations(item.evidence_ids)}"
            for item in report.evidence_and_indicators_table
        ) or "- Unknown / missing information"
        timeline = "\n".join(
            f"- {event.timestamp or 'Unknown time'}: {event.event} {self._format_evidence_citations(event.evidence_ids)}"
            for event in report.incident_timeline
        ) or "- Unknown / missing information"
        mitre = "\n".join(
            f"- {item.technique_id} {item.technique_name}: {item.justification}"
            for item in report.mitre_attack_assessment
        ) or "- Unknown / missing information"
        legal = "\n".join(
            f"- {item.provision_reference}: {item.preliminary_relevance} {item.disclaimer}"
            for item in report.legal_assessments
        ) or "- Not requested"
        missing = "\n".join(f"- {item}" for item in report.evidence_still_required)
        limitations = "\n".join(f"- {item}" for item in report.limitations_and_disclaimers)
        return (
            f"# {report.title}\n\n"
            f"## Executive case summary\n{report.executive_case_summary}\n\n"
            "## Case-information completeness\n"
            f"{report.case_information_completeness.percentage}% - {report.case_information_completeness.status}\n\n"
            f"## Evidence and indicators\n{indicators}\n\n"
            f"## Incident timeline\n{timeline}\n\n"
            f"## MITRE ATT&CK assessment\n{mitre}\n\n"
            f"## Evidence still required / next steps\n{missing}\n\n"
            f"## Optional preliminary legal relevance\n{legal}\n\n"
            f"## Limitations and disclaimers\n{limitations}\n\n"
            f"## Review status\n{report.review_status}"
        )
