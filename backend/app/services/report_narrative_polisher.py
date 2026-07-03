from __future__ import annotations

from app.schemas.report import ReportViewModel


class ReportNarrativePolisher:
    def polish(self, report: ReportViewModel) -> ReportViewModel:
        # Future LLM polishing belongs here, after fact-preservation validation.
        return report
