import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import InvestigationWorkspace from "./InvestigationWorkspace";
import {
  chatContinue,
  generateReport,
  queryRagFile,
  resumeRag,
  resumeReport,
} from "@/lib/api";
import type { CyberCaseReport } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  chatContinue: vi.fn(),
  generateReport: vi.fn(),
  queryRagFile: vi.fn(),
  resumeRag: vi.fn(),
  resumeReport: vi.fn(),
}));

function submitChatInput(value: string) {
  const input = screen.getByPlaceholderText(
    /Describe the incident, provide evidence, or ask a question/,
  );
  fireEvent.change(input, { target: { value } });
  fireEvent.submit(input.closest("form") as HTMLFormElement);
}

function makeReport(): CyberCaseReport {
  const completeness = {
    percentage: 100,
    status: "Sufficient for preliminary report" as const,
    missing_fields: [],
    fields: [],
  };

  return {
    report_id: "report-1",
    title: "Preliminary report",
    report_type: "overview",
    executive_case_summary: "Report generated",
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

describe("InvestigationWorkspace follow-up progression", () => {
  beforeEach(() => {
    Element.prototype.scrollIntoView = vi.fn();
    vi.mocked(chatContinue).mockReset();
    vi.mocked(generateReport).mockReset();
    vi.mocked(queryRagFile).mockReset();
    vi.mocked(resumeRag).mockReset();
    vi.mocked(resumeReport).mockReset();
  });

  it("handles nested follow-ups, marks retrieval refresh, and regenerates with the latest context", async () => {
    vi.mocked(chatContinue)
      .mockResolvedValueOnce({
        status: "completed",
        answer: "Initial analysis",
        retrieval_context_id: "CTX-1",
      })
      .mockResolvedValueOnce({
        status: "followup",
        answer: "",
        followup_question: "Which mailbox received the email?",
        session_id: "SESSION-1",
      });
    vi.mocked(resumeRag)
      .mockResolvedValueOnce({
        status: "followup",
        answer: "",
        followup_question: "Which source IP was observed?",
        session_id: "SESSION-2",
      })
      .mockResolvedValueOnce({
        status: "completed",
        answer: "Final analysis after follow-up",
        retrieval_context_id: "CTX-2",
      });
    vi.mocked(generateReport).mockResolvedValue({
      status: "completed",
      report_id: "report-1",
      report: makeReport(),
      answer: "Report generated",
    });

    render(<InvestigationWorkspace showCaseList={false} />);

    submitChatInput("Initial phishing narrative");

    expect(await screen.findByText("Initial analysis")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Generate from investigation" }));

    await waitFor(() => {
      expect(generateReport).toHaveBeenLastCalledWith(
        expect.any(String),
        "overview",
        false,
        false,
        "CTX-1",
      );
    });

    submitChatInput("Add missing mailbox detail");

    expect(
      await screen.findByText("Which mailbox received the email?"),
    ).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("Type your answer here..."), {
      target: { value: "finance@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send Answer" }));

    expect(await screen.findByText("Which source IP was observed?")).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("Type your answer here..."), {
      target: { value: "10.0.0.5" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send Answer" }));

    expect(await screen.findByText("Final analysis after follow-up")).toBeInTheDocument();
    expect(screen.getByText("Retrieval refreshed")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Regenerate from refreshed context" }),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: "Regenerate from refreshed context" }),
    );

    await waitFor(() => {
      expect(generateReport).toHaveBeenLastCalledWith(
        expect.any(String),
        "overview",
        false,
        false,
        "CTX-2",
      );
    });
  });
});
