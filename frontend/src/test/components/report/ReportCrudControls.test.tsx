import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ReportCrudControls from "@/components/report/ReportCrudControls";
import {
  deleteReport,
  updateReport,
  type ReportCompletedResponse,
} from "@/lib/api";
import { makeCompletedReport } from "@/test/reportWorkflow";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, updateReport: vi.fn(), deleteReport: vi.fn() };
});

function Harness({ initial = makeCompletedReport() }: { initial?: ReportCompletedResponse }) {
  const [workflow, setWorkflow] = useState(initial);
  return (
    <ReportCrudControls
      workflow={workflow}
      onUpdated={setWorkflow}
      onDeleted={vi.fn()}
    />
  );
}

describe("ReportCrudControls", () => {
  beforeEach(() => {
    vi.mocked(updateReport).mockReset();
    vi.mocked(deleteReport).mockReset();
  });

  it("supports Cancel and saves only allowlisted narrative changes with manual attribution", async () => {
    const edited = makeCompletedReport({
      report: { title: "Analyst title", investigation_next_steps: ["Contain affected mailbox"] },
      editMetadata: {
        origin: "manual_edit",
        edited_fields: ["title", "investigation_next_steps"],
        edited_at: "2026-07-10T01:00:00Z",
      },
    });
    vi.mocked(updateReport).mockResolvedValue(edited);
    render(<Harness />);

    fireEvent.click(screen.getByRole("button", { name: "Edit report" }));
    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Discarded title" } });
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(updateReport).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Edit report" }));
    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Analyst title" } });
    fireEvent.change(screen.getByLabelText(/Investigation next steps/), {
      target: { value: "Contain affected mailbox" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => {
      expect(updateReport).toHaveBeenCalledWith("REPORT-1", {
        title: "Analyst title",
        investigation_next_steps: ["Contain affected mailbox"],
      });
    });
    expect(await screen.findByText("Analyst edited")).toBeInTheDocument();
  });

  it("shows server validation errors without closing the editor", async () => {
    vi.mocked(updateReport).mockRejectedValue({
      isAxiosError: true,
      response: { data: { detail: [{ loc: ["body", "title"], msg: "Report narrative fields cannot be empty" }] } },
    });
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Edit report" }));
    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Changed title" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "title: Report narrative fields cannot be empty",
    );
    expect(screen.getByRole("dialog", { name: "Edit report" })).toBeInTheDocument();
  });

  it("requires delete confirmation and locks actions while deletion is pending", async () => {
    let resolveDelete: (() => void) | undefined;
    const deleted = vi.fn();
    const busy = vi.fn();
    vi.mocked(deleteReport).mockImplementation(
      () => new Promise<void>((resolve) => { resolveDelete = resolve; }),
    );
    render(
      <ReportCrudControls
        workflow={makeCompletedReport()}
        onUpdated={vi.fn()}
        onDeleted={deleted}
        onBusyChange={busy}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Delete report" }));
    const dialog = screen.getByRole("dialog", { name: "Delete report?" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Delete report" }));
    await waitFor(() => expect(deleteReport).toHaveBeenCalledWith("REPORT-1"));
    expect(within(dialog).getByRole("button", { name: "Deleting..." })).toBeDisabled();
    expect(within(dialog).getByRole("button", { name: "Cancel" })).toBeDisabled();
    expect(busy).toHaveBeenCalledWith(true);

    await act(async () => resolveDelete?.());
    await waitFor(() => expect(deleted).toHaveBeenCalled());
    expect(busy).toHaveBeenLastCalledWith(false);
  });
});
