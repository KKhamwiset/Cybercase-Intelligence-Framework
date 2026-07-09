import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CaseChatWorkspace from "./CaseChatWorkspace";
import { getCase } from "@/lib/cases";
import { getCaseChat, postCaseChatMessage } from "@/lib/case-chat";
import type { StructuredCase } from "@/lib/cases";
import { renderWithQueryClient } from "@/test/renderWithQueryClient";

vi.mock("@/lib/cases", async () => {
  const actual = await vi.importActual<typeof import("@/lib/cases")>("@/lib/cases");
  return { ...actual, getCase: vi.fn() };
});
vi.mock("@/lib/case-chat", () => ({ getCaseChat: vi.fn(), postCaseChatMessage: vi.fn() }));
vi.mock("@/lib/api", () => ({ generateCaseReport: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

function makeCase(): StructuredCase {
  return {
    case_id: "CASE-CHAT", title: "Chat case", case_type: "incident", status: "new", severity: "high",
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

describe("CaseChatWorkspace", () => {
  beforeEach(() => {
    vi.mocked(getCase).mockReset();
    vi.mocked(getCaseChat).mockReset();
    vi.mocked(postCaseChatMessage).mockReset();
    vi.mocked(getCase).mockResolvedValue(makeCase());
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
});
