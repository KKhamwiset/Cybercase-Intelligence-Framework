import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CaseChatWorkspace from "@/components/cases/CaseChatWorkspace";
import {
  generateCaseReport,
  getCaseAnalysis,
  startCaseAnalysis,
  submitCaseAnalysisFollowUp,
} from "@/lib/api";
import { getCase } from "@/lib/cases";
import type { CaseAnalysisResponse, CyberCaseReport } from "@/lib/api";
import type { StructuredCase } from "@/lib/cases";
import { renderWithQueryClient } from "@/test/renderWithQueryClient";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

vi.mock("@/lib/cases", async () => {
  const actual = await vi.importActual<typeof import("@/lib/cases")>("@/lib/cases");
  return {
    ...actual,
    getCase: vi.fn(),
  };
});

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    generateCaseReport: vi.fn(),
    getCaseAnalysis: vi.fn(),
    startCaseAnalysis: vi.fn(),
    submitCaseAnalysisFollowUp: vi.fn(),
  };
});

function makeCase(overrides: Partial<StructuredCase> = {}): StructuredCase {
  return {
    case_id: "CASE-CHAT",
    title: "Chat case",
    case_type: "incident",
    status: "new",
    severity: "high",
    incident_summary: "Finance reported a phishing email and payment redirect.",
    affected_users: ["finance@example.com"],
    affected_assets: ["mailbox-finance"],
    timeline_events: [],
    evidence_items: [
      {
        evidence_id: "E-001",
        title: "Phishing email",
        description: "Message asking finance to approve a payment.",
        source_type: "user_input",
        status: "candidate",
        confidence: "medium",
        analyst_verified: false,
      },
    ],
    attack_mappings: [],
    containment_actions: [],
    recommendations: [],
    gaps: ["Confirm sender infrastructure."],
    limitations: [],
    analyst_notes: "Awaiting mailbox headers.",
    ...overrides,
  };
}

function analysisState(
  overrides: Partial<CaseAnalysisResponse> = {},
): CaseAnalysisResponse {
  return {
    case_id: "CASE-CHAT",
    session_id: null,
    workflow_status: "case_saved",
    retrieval_context_id: null,
    completeness: null,
    missing_information: [],
    followup_question: null,
    mitre_preview: [],
    created_at: null,
    updated_at: null,
    ...overrides,
  };
}

function makeReport(): CyberCaseReport {
  const completeness = {
    percentage: 100,
    status: "Sufficient for preliminary report" as const,
    missing_fields: [],
    fields: [],
  };
  return {
    report_id: "rep-analysis-1",
    title: "Analysis report",
    report_type: "overview",
    executive_case_summary: "Summary",
    case_information_completeness: completeness,
    evidence_and_indicators_table: [],
    incident_timeline: [],
    mitre_attack_assessment: [],
    evidence_still_required: [],
    investigation_next_steps: [],
    legal_assessments: [],
    limitations_and_disclaimers: [],
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
    created_at: "2026-07-08T00:00:00Z",
  };
}

describe("CaseChatWorkspace", () => {
  beforeEach(() => {
    vi.mocked(getCase).mockReset();
    vi.mocked(generateCaseReport).mockReset();
    vi.mocked(getCaseAnalysis).mockReset();
    vi.mocked(startCaseAnalysis).mockReset();
    vi.mocked(submitCaseAnalysisFollowUp).mockReset();
    push.mockReset();
  });

  it("loads cached analysis on mount and starts analysis only after the user clicks", async () => {
    vi.mocked(getCase).mockResolvedValue(makeCase());
    vi.mocked(getCaseAnalysis).mockResolvedValue(analysisState());
    vi.mocked(startCaseAnalysis).mockResolvedValue(
      analysisState({
        session_id: "session-1",
        workflow_status: "needs_followup",
        retrieval_context_id: "ctx-analysis-1",
        followup_question: "When did the suspicious login occur?",
        completeness: {
          percentage: 20,
          status: "Incomplete - follow-up required",
          missing_fields: ["incident date/time"],
          fields: [],
        },
        missing_information: ["incident date/time"],
      }),
    );

    renderWithQueryClient(<CaseChatWorkspace caseId="CASE-CHAT" />);

    expect(await screen.findByText("Case Analysis Assistant")).toBeInTheDocument();
    await waitFor(() => {
      expect(getCaseAnalysis).toHaveBeenCalledWith("CASE-CHAT");
    });
    expect(startCaseAnalysis).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /start case analysis/i }));

    expect(await screen.findByText("When did the suspicious login occur?")).toBeInTheDocument();
    expect(startCaseAnalysis).toHaveBeenCalledWith("CASE-CHAT", "overview", false);
  });

  it("submits follow-up answers through the backend session endpoint", async () => {
    vi.mocked(getCase).mockResolvedValue(makeCase());
    vi.mocked(getCaseAnalysis).mockResolvedValue(
      analysisState({
        session_id: "session-1",
        workflow_status: "needs_followup",
        retrieval_context_id: "ctx-analysis-1",
        followup_question: "When did the suspicious login occur?",
      }),
    );
    vi.mocked(submitCaseAnalysisFollowUp).mockResolvedValue(
      analysisState({
        session_id: "session-1",
        workflow_status: "ready_for_report",
        retrieval_context_id: "ctx-analysis-2",
        completeness: {
          percentage: 100,
          status: "Sufficient for preliminary report",
          missing_fields: [],
          fields: [],
        },
      }),
    );

    renderWithQueryClient(<CaseChatWorkspace caseId="CASE-CHAT" />);

    expect(await screen.findByText("When did the suspicious login occur?")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/your answer/i), {
      target: { value: "2026-07-07 at 09:30 UTC" },
    });
    fireEvent.click(screen.getByRole("button", { name: /submit answer/i }));

    await waitFor(() => {
      expect(submitCaseAnalysisFollowUp).toHaveBeenCalledWith(
        "CASE-CHAT",
        "session-1",
        "2026-07-07 at 09:30 UTC",
      );
    });
    expect(await screen.findByRole("button", { name: /generate report/i })).toBeInTheDocument();
  });

  it("generates the report using the cached retrieval context", async () => {
    vi.mocked(getCase).mockResolvedValue(makeCase());
    vi.mocked(getCaseAnalysis)
      .mockResolvedValueOnce(
        analysisState({
          session_id: "session-1",
          workflow_status: "ready_for_report",
          retrieval_context_id: "ctx-analysis-2",
        }),
      )
      .mockResolvedValueOnce(
        analysisState({
          workflow_status: "report_generated",
          retrieval_context_id: "ctx-analysis-2",
        }),
      );
    vi.mocked(generateCaseReport).mockResolvedValue({
      status: "completed",
      report_id: "rep-analysis-1",
      answer: "# Report",
      retrieval_context_id: "ctx-analysis-2",
      report: makeReport(),
    });

    renderWithQueryClient(<CaseChatWorkspace caseId="CASE-CHAT" />);

    fireEvent.click(await screen.findByRole("button", { name: /generate report/i }));

    await waitFor(() => {
      expect(generateCaseReport).toHaveBeenCalledWith(
        "CASE-CHAT",
        "overview",
        false,
        true,
        "ctx-analysis-2",
      );
    });
    expect(await screen.findByText("Analysis Complete")).toBeInTheDocument();
  });
});
