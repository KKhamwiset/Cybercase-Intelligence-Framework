import type {
  CyberCaseReport,
  ReportCompletedResponse,
  ReportEditMetadata,
} from "@/lib/api";

export function makeCyberCaseReport(overrides: Partial<CyberCaseReport> = {}): CyberCaseReport {
  const completeness = {
    percentage: 100,
    status: "Sufficient for preliminary report" as const,
    missing_fields: [],
    fields: [],
  };
  return {
    report_id: "REPORT-1",
    title: "Preliminary investigation report",
    report_type: "overview",
    executive_case_summary: "Generated executive summary",
    case_information_completeness: completeness,
    evidence_and_indicators_table: [],
    incident_timeline: [],
    mitre_attack_assessment: [],
    evidence_still_required: ["Collect mailbox headers"],
    investigation_next_steps: ["Review suspicious sign-ins"],
    legal_assessments: [],
    limitations_and_disclaimers: ["Preliminary analysis only"],
    review_status: "draft",
    case_fact_pack: {
      facts: [],
      evidence_registry: [],
      indicators: [],
      timeline: [],
      mitre_assessments: [],
      legal_assessments: [],
      missing_information: [],
      limitations: [],
      completeness_percentage: 100,
      completeness,
      review_status: "draft",
    },
    created_at: "2026-07-10T00:00:00Z",
    ...overrides,
  };
}

export function makeCompletedReport(
  options: {
    report?: Partial<CyberCaseReport>;
    editMetadata?: Partial<ReportEditMetadata>;
    answer?: string;
  } = {},
): ReportCompletedResponse {
  const report = makeCyberCaseReport(options.report);
  return {
    status: "completed",
    report_id: report.report_id,
    report,
    answer: options.answer ?? "# Preliminary investigation report\n\nGenerated executive summary",
    retrieval_context_id: "CTX-1",
    edit_metadata: {
      origin: "generated",
      edited_fields: [],
      edited_at: null,
      ...options.editMetadata,
    },
  };
}
