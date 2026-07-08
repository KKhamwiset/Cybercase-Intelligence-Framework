import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CaseChatWorkspace from "./CaseChatWorkspace";
import { chatContinue, generateCaseReport, queryRagFile, resumeCaseReport, resumeRag } from "@/lib/api";
import { getCase } from "@/lib/cases";
import type { StructuredCase } from "@/lib/cases";
import { renderWithQueryClient } from "@/test/renderWithQueryClient";

vi.mock("@/lib/cases", async () => {
  const actual = await vi.importActual<typeof import("@/lib/cases")>("@/lib/cases");
  return {
    ...actual,
    getCase: vi.fn(),
  };
});

vi.mock("@/lib/api", () => ({
  chatContinue: vi.fn(),
  generateCaseReport: vi.fn(),
  queryRagFile: vi.fn(),
  resumeRag: vi.fn(),
  resumeCaseReport: vi.fn(),
}));

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

function submitChatInput(value: string) {
  const input = screen.getByPlaceholderText(
    /Describe the incident, provide evidence, or ask a question/,
  );
  fireEvent.change(input, { target: { value } });
  fireEvent.submit(input.closest("form") as HTMLFormElement);
}

describe("CaseChatWorkspace", () => {
  beforeEach(() => {
    Element.prototype.scrollIntoView = vi.fn();
    vi.mocked(getCase).mockReset();
    vi.mocked(chatContinue).mockReset();
    vi.mocked(generateCaseReport).mockReset();
    vi.mocked(queryRagFile).mockReset();
    vi.mocked(resumeRag).mockReset();
    vi.mocked(resumeCaseReport).mockReset();
  });

  it("auto-runs a saved case and prefixes later non-resume turns without showing hidden context", async () => {
    vi.mocked(getCase).mockResolvedValue(makeCase());
    vi.mocked(chatContinue)
      .mockResolvedValueOnce({
        status: "completed",
        answer: "Saved case analysis",
        retrieval_context_id: "CTX-CHAT-1",
      })
      .mockResolvedValueOnce({
        status: "completed",
        answer: "Later analysis",
        retrieval_context_id: "CTX-CHAT-2",
      });

    renderWithQueryClient(<CaseChatWorkspace caseId="CASE-CHAT" />);

    expect(
      await screen.findByText("Analyze saved case CASE-CHAT: Chat case"),
    ).toBeInTheDocument();
    expect(await screen.findByText("Saved case analysis")).toBeInTheDocument();

    await waitFor(() => {
      expect(chatContinue).toHaveBeenCalledWith(
        expect.stringContaining("evidence_items:"),
        expect.any(Array),
      );
    });

    submitChatInput("What evidence should I collect next?");

    await waitFor(() => {
      expect(chatContinue).toHaveBeenLastCalledWith(
        expect.stringContaining("Current analyst message:\nWhat evidence should I collect next?"),
        expect.any(Array),
      );
    });
    expect(await screen.findByText("Later analysis")).toBeInTheDocument();
    expect(screen.getByText("What evidence should I collect next?")).toBeInTheDocument();
    expect(screen.queryByText(/evidence_items:/)).not.toBeInTheDocument();
  });

  it("does not auto-run when the case has no saved intake narrative", async () => {
    vi.mocked(getCase).mockResolvedValue(makeCase({ incident_summary: "" }));

    renderWithQueryClient(<CaseChatWorkspace caseId="CASE-CHAT" />);

    expect(await screen.findByText("Save Intake first.")).toBeInTheDocument();
    expect(chatContinue).not.toHaveBeenCalled();
  });
});
