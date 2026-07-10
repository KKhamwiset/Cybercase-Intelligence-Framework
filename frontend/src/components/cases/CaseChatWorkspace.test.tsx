import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CaseChatWorkspace from "./CaseChatWorkspace";
import { getCase, getCaseOutputs } from "@/lib/cases";
import {
  getCaseChat,
  getCaseReportReadiness,
  postCaseChatMessage,
} from "@/lib/case-chat";
import { generateCaseReport } from "@/lib/api";
import type { StructuredCase } from "@/lib/cases";
import { renderWithQueryClient } from "@/test/renderWithQueryClient";
import { makeCaseOutputs } from "@/test/caseOutputs";

vi.mock("@/lib/cases", async () => {
  const actual = await vi.importActual<typeof import("@/lib/cases")>("@/lib/cases");
  return { ...actual, getCase: vi.fn(), getCaseOutputs: vi.fn() };
});
vi.mock("@/lib/case-chat", async () => {
  const actual = await vi.importActual<typeof import("@/lib/case-chat")>("@/lib/case-chat");
  return {
    ...actual,
    getCaseChat: vi.fn(),
    getCaseReportReadiness: vi.fn(),
    postCaseChatMessage: vi.fn(),
  };
});
vi.mock("@/lib/api", () => ({ generateCaseReport: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

function makeCase(): StructuredCase {
  return {
    case_id: "CASE-CHAT", case_version: 1, title: "Chat case", case_type: "incident", status: "new", severity: "high",
    incident_summary: "Finance reported a phishing email.", affected_users: [], affected_assets: [],
    timeline_events: [], evidence_items: [], attack_mappings: [], containment_actions: [],
    recommendations: [], gaps: [], limitations: [], analyst_notes: "",
  };
}

function workspace(overrides = {}) {
  return {
    case_id: "CASE-CHAT",
    context: {
      title: "Chat case", incident_summary: "Finance reported a phishing email.",
      case_version: 1, case_snapshot_hash: "a".repeat(64), evidence_count: 1, gap_count: 1, attack_mapping_count: 0,
      gaps: ["Confirm sender"], attack_candidates: [], updated_at: null,
    },
    turns: [], status: "idle" as const, requires_followup: false,
    active_session_id: null, latest_retrieval_context_id: null,
    analysis_case_version: null, analysis_snapshot_hash: null, report_eligible: false,
    ...overrides,
  };
}

function readiness(overrides = {}) {
  return {
    case_id: "CASE-CHAT",
    current_case_version: 1,
    current_case_snapshot_hash: "a".repeat(64),
    analysis_status: "missing" as const,
    report_eligible: false,
    reason: "analysis_required" as const,
    latest_analysis_turn_id: null,
    latest_retrieval_context_id: null,
    ...overrides,
  };
}

describe("CaseChatWorkspace", () => {
  beforeEach(() => {
    vi.mocked(getCase).mockReset();
    vi.mocked(getCaseOutputs).mockReset();
    vi.mocked(getCaseChat).mockReset();
    vi.mocked(getCaseReportReadiness).mockReset();
    vi.mocked(postCaseChatMessage).mockReset();
    vi.mocked(generateCaseReport).mockReset();
    vi.mocked(getCase).mockResolvedValue(makeCase());
    vi.mocked(getCaseOutputs).mockResolvedValue(makeCaseOutputs("CASE-CHAT"));
    vi.mocked(getCaseReportReadiness).mockResolvedValue(readiness());
  });

  it("loads saved context without auto-running retrieval", async () => {
    vi.mocked(getCaseChat).mockResolvedValue(workspace());
    renderWithQueryClient(<CaseChatWorkspace caseId="CASE-CHAT" />);

    expect(await screen.findByText("Pinned saved case context")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Analyze saved case" })).toBeEnabled();
    expect(postCaseChatMessage).not.toHaveBeenCalled();
  });

  it("sends only the visible question and an idempotency key", async () => {
    vi.mocked(getCaseChat).mockResolvedValue(workspace());
    vi.mocked(postCaseChatMessage).mockResolvedValue({
      status: "completed", turn_status: "completed", turn_type: "question", message: "done",
      case_version: 1, case_snapshot_hash: "a".repeat(64), report_eligible: false,
      requires_followup: false, idempotent: false,
    });
    renderWithQueryClient(<CaseChatWorkspace caseId="CASE-CHAT" />);

    const input = await screen.findByPlaceholderText("Ask an investigation question");
    fireEvent.change(input, { target: { value: "What evidence should I collect?" } });
    fireEvent.submit(input.closest("form") as HTMLFormElement);

    await waitFor(() => {
      expect(postCaseChatMessage).toHaveBeenCalledWith(
        "CASE-CHAT",
        { action: "question", message: "What evidence should I collect?" },
        expect.any(String),
      );
    });
    expect(JSON.stringify(vi.mocked(postCaseChatMessage).mock.calls[0])).not.toContain("incident_summary");
  });

  it("requires intake before analysis", async () => {
    vi.mocked(getCase).mockResolvedValue({ ...makeCase(), incident_summary: "" });
    vi.mocked(getCaseChat).mockResolvedValue(workspace({ context: { ...workspace().context, incident_summary: "" } }));
    renderWithQueryClient(<CaseChatWorkspace caseId="CASE-CHAT" />);
    expect(await screen.findByText(/Save Intake first\./)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Analyze saved case" })).toBeDisabled();
  });

  it("shows report generation instead of a duplicate Analyze action when analysis is current", async () => {
    vi.mocked(getCaseChat).mockResolvedValue(workspace({
      status: "completed",
      report_eligible: true,
      latest_retrieval_context_id: "ctx-current",
    }));
    vi.mocked(getCaseReportReadiness).mockResolvedValue(readiness({
      analysis_status: "completed",
      report_eligible: true,
      reason: "ready",
      latest_retrieval_context_id: "ctx-current",
    }));

    renderWithQueryClient(<CaseChatWorkspace caseId="CASE-CHAT" />);

    expect(await screen.findByText("Analysis current")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Analyze saved case" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate preliminary report" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Refresh analysis" })).toBeEnabled();
  });

  it("uses the explicit refresh_analysis action for intentional reruns", async () => {
    vi.mocked(getCaseChat).mockResolvedValue(workspace({ status: "completed", report_eligible: true }));
    vi.mocked(getCaseReportReadiness).mockResolvedValue(readiness({
      analysis_status: "completed",
      report_eligible: true,
      reason: "ready",
    }));
    vi.mocked(postCaseChatMessage).mockResolvedValue({
      status: "completed",
      turn_status: "completed",
      turn_type: "analysis",
      message: "refreshed",
      case_version: 1,
      case_snapshot_hash: "a".repeat(64),
      report_eligible: true,
      requires_followup: false,
      idempotent: false,
    });

    renderWithQueryClient(<CaseChatWorkspace caseId="CASE-CHAT" />);
    fireEvent.click(await screen.findByRole("button", { name: "Refresh analysis" }));

    await waitFor(() => {
      expect(postCaseChatMessage).toHaveBeenCalledWith(
        "CASE-CHAT",
        { action: "refresh_analysis", message: "" },
        expect.any(String),
      );
    });
  });

  it("disables analysis and the composer while an analysis run is pending", async () => {
    vi.mocked(getCaseChat).mockResolvedValue(workspace({ status: "pending" }));
    vi.mocked(getCaseReportReadiness).mockResolvedValue(readiness({
      analysis_status: "pending",
      reason: "analysis_pending",
    }));

    renderWithQueryClient(<CaseChatWorkspace caseId="CASE-CHAT" />);

    expect(await screen.findByRole("button", { name: "Analysis in progress" })).toBeDisabled();
    expect(screen.getByPlaceholderText("Ask an investigation question")).toBeDisabled();
  });

  it("keeps older turns visible while requiring refresh after a case edit", async () => {
    vi.mocked(getCaseChat).mockResolvedValue(workspace({
      status: "stale",
      turns: [{
        turn_id: "CCT-old",
        role: "assistant",
        content: "Analysis for the previous case version",
        turn_type: "analysis",
        turn_status: "completed",
        case_version: 1,
        case_snapshot_hash: "a".repeat(64),
      }],
      context: { ...workspace().context, case_version: 2, case_snapshot_hash: "b".repeat(64) },
    }));
    vi.mocked(getCaseReportReadiness).mockResolvedValue(readiness({
      current_case_version: 2,
      current_case_snapshot_hash: "b".repeat(64),
      analysis_status: "stale",
      reason: "analysis_stale",
    }));

    renderWithQueryClient(<CaseChatWorkspace caseId="CASE-CHAT" />);

    expect(await screen.findByText("Refresh analysis required")).toBeInTheDocument();
    expect(screen.getByText("Analysis for the previous case version")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Refresh analysis" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: "Generate preliminary report" })).not.toBeInTheDocument();
  });
});
