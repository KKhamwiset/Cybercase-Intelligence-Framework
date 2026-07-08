import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useCase, useUpdateCase } from "@/hooks/useCase";
import { getCase, updateCase } from "@/lib/cases";
import type { StructuredCase } from "@/lib/cases";
import { renderWithQueryClient } from "@/test/renderWithQueryClient";

vi.mock("@/lib/cases", async () => {
  const actual = await vi.importActual<typeof import("@/lib/cases")>("@/lib/cases");
  return {
    ...actual,
    getCase: vi.fn(),
    updateCase: vi.fn(),
  };
});

function makeCase(incidentSummary = ""): StructuredCase {
  return {
    case_id: "CASE-PERSIST",
    title: "Persistent case",
    case_type: "incident",
    status: "new",
    severity: "unknown",
    incident_summary: incidentSummary,
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

function IntakeHarness() {
  const query = useCase("CASE-PERSIST");
  const mutation = useUpdateCase("CASE-PERSIST");

  if (!query.data) {
    return <div>loading</div>;
  }

  return (
    <button
      type="button"
      onClick={() => mutation.mutate({ incident_summary: "Saved intake narrative" })}
    >
      Save Intake
    </button>
  );
}

function GapHarness() {
  const query = useCase("CASE-PERSIST");

  return <div>{query.data?.incident_summary || "No saved intake"}</div>;
}

describe("case workflow persistence", () => {
  beforeEach(() => {
    vi.mocked(getCase).mockReset();
    vi.mocked(updateCase).mockReset();
  });

  it("keeps saved intake data available after navigating to gap analysis", async () => {
    vi.mocked(getCase).mockResolvedValue(makeCase());
    vi.mocked(updateCase).mockResolvedValue(makeCase("Saved intake narrative"));

    const { rerender } = renderWithQueryClient(<IntakeHarness />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Save Intake" })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole("button", { name: "Save Intake" }));

    await waitFor(() => {
      expect(updateCase).toHaveBeenCalledWith("CASE-PERSIST", {
        incident_summary: "Saved intake narrative",
      });
    });

    rerender(<GapHarness />);

    await waitFor(() => {
      expect(screen.getByText("Saved intake narrative")).toBeInTheDocument();
    });
  });
});
