import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CaseCrudControls from "@/components/cases/CaseCrudControls";
import { deleteCase, updateCase, type StructuredCase } from "@/lib/cases";
import { renderWithQueryClient } from "@/test/renderWithQueryClient";

const replace = vi.fn();
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, refresh }),
}));

vi.mock("@/lib/cases", async () => {
  const actual = await vi.importActual<typeof import("@/lib/cases")>("@/lib/cases");
  return { ...actual, updateCase: vi.fn(), deleteCase: vi.fn() };
});

function makeCase(overrides: Partial<StructuredCase> = {}): StructuredCase {
  return {
    case_id: "CASE-CRUD",
    case_version: 1,
    title: "Original case",
    case_type: "incident",
    status: "new",
    severity: "medium",
    incident_summary: "Saved narrative",
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
    ...overrides,
  };
}

describe("CaseCrudControls", () => {
  beforeEach(() => {
    replace.mockReset();
    refresh.mockReset();
    vi.mocked(updateCase).mockReset();
    vi.mocked(deleteCase).mockReset();
  });

  it("traps focus, cancels edits, and restores focus to the opener", async () => {
    renderWithQueryClient(<CaseCrudControls caseData={makeCase()} />);
    const opener = screen.getByRole("button", { name: "Edit case" });
    opener.focus();
    fireEvent.click(opener);

    const title = screen.getByLabelText("Title");
    await waitFor(() => expect(title).toHaveFocus());
    fireEvent.change(title, { target: { value: "Changed locally" } });
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(screen.getByRole("button", { name: "Save changes" })).toHaveFocus();
    fireEvent.keyDown(document, { key: "Escape" });

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await waitFor(() => expect(opener).toHaveFocus());
    expect(updateCase).not.toHaveBeenCalled();
  });

  it("saves only editable metadata and exposes backend validation details", async () => {
    vi.mocked(updateCase).mockResolvedValue(makeCase({ title: "Renamed case" }));
    renderWithQueryClient(<CaseCrudControls caseData={makeCase()} />);

    fireEvent.click(screen.getByRole("button", { name: "Edit case" }));
    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "  Renamed case  " } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => {
      expect(updateCase).toHaveBeenCalledWith("CASE-CRUD", {
        title: "Renamed case",
        case_type: "incident",
        status: "new",
        severity: "medium",
      });
    });

    vi.mocked(updateCase).mockRejectedValueOnce({
      isAxiosError: true,
      response: { data: { detail: [{ loc: ["body", "title"], msg: "String should have at most 255 characters" }] } },
    });
    fireEvent.click(screen.getByRole("button", { name: "Edit case" }));
    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Another title" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("title: String should have at most 255 characters");
  });

  it("confirms deletion, locks duplicate actions while pending, and navigates after success", async () => {
    let resolveDelete: (() => void) | undefined;
    vi.mocked(deleteCase).mockImplementation(
      () => new Promise<void>((resolve) => { resolveDelete = resolve; }),
    );
    renderWithQueryClient(<CaseCrudControls caseData={makeCase()} />);

    fireEvent.click(screen.getByRole("button", { name: "Delete case" }));
    const dialog = screen.getByRole("dialog", { name: "Delete case?" });
    expect(dialog).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "Delete case" }));

    await waitFor(() => expect(deleteCase).toHaveBeenCalledWith("CASE-CRUD"));
    expect(within(dialog).getByRole("button", { name: "Deleting..." })).toBeDisabled();
    expect(within(dialog).getByRole("button", { name: "Cancel" })).toBeDisabled();

    await act(async () => resolveDelete?.());
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/cases"));
    expect(refresh).toHaveBeenCalled();
  });
});
