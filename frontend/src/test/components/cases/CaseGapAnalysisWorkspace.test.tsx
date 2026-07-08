import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CaseGapAnalysisWorkspace from "@/components/cases/CaseGapAnalysisWorkspace";
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

function makeCase(overrides: Partial<StructuredCase> = {}): StructuredCase {
  return {
    case_id: "CASE-GAP",
    title: "Gap case",
    case_type: "incident",
    status: "new",
    severity: "unknown",
    incident_summary: "Saved intake narrative",
    affected_users: [],
    affected_assets: [],
    timeline_events: [],
    evidence_items: [],
    attack_mappings: [],
    containment_actions: [],
    recommendations: [],
    gaps: ["Confirm the sender domain owner."],
    limitations: [],
    analyst_notes: "",
    ...overrides,
  };
}

describe("CaseGapAnalysisWorkspace", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    vi.mocked(getCase).mockReset();
    vi.mocked(updateCase).mockReset();
  });

  it("loads backend analyst notes into the draft without enabling a stale blank save", async () => {
    vi.mocked(getCase).mockResolvedValue(
      makeCase({ analyst_notes: "Loaded analyst notes" }),
    );

    renderWithQueryClient(<CaseGapAnalysisWorkspace caseId="CASE-GAP" />);

    expect(await screen.findByDisplayValue("Loaded analyst notes")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save Notes" })).toBeDisabled();
    expect(updateCase).not.toHaveBeenCalled();
  });
});
