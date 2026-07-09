import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CaseReportWorkspace from "@/components/cases/CaseReportWorkspace";
import { getCase } from "@/lib/cases";
import { generateCaseReport, getLatestCaseReport } from "@/lib/api";
import { getCaseReportReadiness } from "@/lib/case-chat";
import { renderWithQueryClient } from "@/test/renderWithQueryClient";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => ({ caseId: "CASE-REPORT" }),
  useRouter: () => ({ push }),
}));

vi.mock("@/lib/cases", async () => {
  const actual = await vi.importActual<typeof import("@/lib/cases")>("@/lib/cases");
  return { ...actual, getCase: vi.fn() };
});

vi.mock("@/lib/case-chat", async () => {
  const actual = await vi.importActual<typeof import("@/lib/case-chat")>("@/lib/case-chat");
  return { ...actual, getCaseReportReadiness: vi.fn() };
});

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    generateCaseReport: vi.fn(),
    getLatestCaseReport: vi.fn(),
    updateReportReviewStatus: vi.fn(),
    downloadReportExport: vi.fn(),
  };
});

function makeCase() {
  return {
    case_id: "CASE-REPORT",
    title: "Report case",
    case_type: "incident",
    status: "investigating" as const,
    severity: "high" as const,
    incident_summary: "A saved phishing incident.",
    affected_users: [],
    affected_assets: [],
    timeline_events: [],
    evidence_items: [],
    attack_mappings: [],
    containment_actions: [],
    recommendations: [],
    gaps: [],
    limitations: [],
    analyst_notes: "",
  };
}

function readiness(overrides = {}) {
  return {
    case_id: "CASE-REPORT",
    current_case_version: 2,
    current_case_snapshot_hash: "a".repeat(64),
    analysis_status: "missing" as const,
    report_eligible: false,
    reason: "analysis_required" as const,
    latest_analysis_turn_id: null,
    latest_retrieval_context_id: null,
    ...overrides,
  };
}

describe("CaseReportWorkspace readiness", () => {
  beforeEach(() => {
    push.mockReset();
    vi.mocked(getCase).mockReset();
    vi.mocked(getCaseReportReadiness).mockReset();
    vi.mocked(getLatestCaseReport).mockReset();
    vi.mocked(generateCaseReport).mockReset();
    vi.mocked(getCase).mockResolvedValue(makeCase());
    vi.mocked(getLatestCaseReport).mockRejectedValue({ response: { status: 404 } });
  });

  it("enables generation from a current completed analysis without passing a context ID", async () => {
    vi.mocked(getCaseReportReadiness).mockResolvedValue(readiness({
      analysis_status: "completed",
      report_eligible: true,
      reason: "ready",
      latest_retrieval_context_id: "ctx-opaque",
    }));
    vi.mocked(generateCaseReport).mockResolvedValue({
      status: "analysis_required",
      error_code: "analysis_required",
      message: "test response",
    });

    renderWithQueryClient(<CaseReportWorkspace />);

    fireEvent.click(await screen.findByRole("button", { name: "Generate preliminary report" }));
    await waitFor(() => {
      expect(generateCaseReport).toHaveBeenCalledWith("CASE-REPORT", "overview", false, false);
    });
  });

  it("shows the analysis prerequisite when no analysis exists", async () => {
    vi.mocked(getCaseReportReadiness).mockResolvedValue(readiness());
    renderWithQueryClient(<CaseReportWorkspace />);

    expect(await screen.findByText("Analysis required before report generation")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open investigation chat" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: "Generate preliminary report" })).not.toBeInTheDocument();
  });

  it.each([
    ["stale", "analysis_stale", "Case changed after the last analysis"],
    ["expired", "context_expired", "Analysis context expired"],
    ["pending", "analysis_pending", "Analysis in progress"],
    ["failed", "analysis_failed", "Analysis failed"],
  ] as const)("renders the %s readiness state", async (analysisStatus, reason, expectedText) => {
    vi.mocked(getCaseReportReadiness).mockResolvedValue(readiness({
      analysis_status: analysisStatus,
      reason,
    }));
    renderWithQueryClient(<CaseReportWorkspace />);

    expect((await screen.findAllByText(expectedText)).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Open investigation chat" })).toBeEnabled();
  });
});
