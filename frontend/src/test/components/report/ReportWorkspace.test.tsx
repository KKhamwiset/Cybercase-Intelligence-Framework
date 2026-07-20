import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ReportWorkspace from "@/components/report/ReportWorkspace";
import {
  deleteReport,
  getReport,
  listReports,
  updateReport,
  type ReportRegistryItem,
} from "@/lib/api";
import { renderWithQueryClient } from "@/test/renderWithQueryClient";
import { makeCompletedReport } from "@/test/reportWorkflow";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    listReports: vi.fn(),
    getReport: vi.fn(),
    updateReport: vi.fn(),
    deleteReport: vi.fn(),
    updateReportReviewStatus: vi.fn(),
    downloadReportExport: vi.fn(),
  };
});

const registryItem: ReportRegistryItem = {
  report_id: "REPORT-1",
  case_id: "CASE-1",
  case_title: "Mailbox compromise",
  case_status: "investigating",
  severity: "high",
  report_type: "overview",
  workflow_status: "completed",
  review_status: "draft",
  created_at: "2026-07-10T00:00:00Z",
  updated_at: "2026-07-10T00:00:00Z",
  executive_summary_preview: "Generated executive summary",
  edit_metadata: { origin: "generated", edited_fields: [], edited_at: null },
};

describe("ReportWorkspace CRUD", () => {
  beforeEach(() => {
    vi.mocked(listReports).mockReset();
    vi.mocked(getReport).mockReset();
    vi.mocked(updateReport).mockReset();
    vi.mocked(deleteReport).mockReset();
    vi.mocked(listReports).mockResolvedValue([registryItem]);
    vi.mocked(getReport).mockResolvedValue(makeCompletedReport());
  });

  it("edits with manual attribution and deletes with registry cleanup", async () => {
    const edited = makeCompletedReport({
      report: { executive_case_summary: "Analyst-updated summary" },
      editMetadata: {
        origin: "manual_edit",
        edited_fields: ["executive_case_summary"],
        edited_at: "2026-07-10T01:00:00Z",
      },
    });
    vi.mocked(updateReport).mockResolvedValue(edited);
    vi.mocked(deleteReport).mockResolvedValue();
    renderWithQueryClient(<ReportWorkspace />);

    expect(await screen.findByText("One current investigation report per case")).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: /Mailbox compromise/i }));
    expect(screen.getByText("Updated 10 Jul 2026")).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: "Edit report" }));
    fireEvent.change(screen.getByLabelText("Executive case summary"), {
      target: { value: "Analyst-updated summary" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByText("Analyst edited")).toBeInTheDocument();
    expect(updateReport).toHaveBeenCalledWith("REPORT-1", {
      executive_case_summary: "Analyst-updated summary",
    });

    fireEvent.click(screen.getByRole("button", { name: "Delete report" }));
    const dialog = screen.getByRole("dialog", { name: "Delete report?" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Delete report" }));

    await waitFor(() => expect(deleteReport).toHaveBeenCalledWith("REPORT-1"));
    expect(await screen.findByText("No current reports found.")).toBeInTheDocument();
    expect(screen.queryByText("Persisted Report ID:")).not.toBeInTheDocument();
  });
});
