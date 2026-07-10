import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CaseGapAnalysisWorkspace from "@/components/cases/CaseGapAnalysisWorkspace";
import { getCase, getCaseOutputs, updateCase } from "@/lib/cases";
import type { StructuredCase } from "@/lib/cases";
import { renderWithQueryClient } from "@/test/renderWithQueryClient";
import { makeCaseOutputs } from "@/test/caseOutputs";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), refresh: vi.fn() }),
}));

vi.mock("@/lib/cases", async () => {
  const actual = await vi.importActual<typeof import("@/lib/cases")>("@/lib/cases");
  return {
    ...actual,
    getCase: vi.fn(),
    getCaseOutputs: vi.fn(),
    updateCase: vi.fn(),
  };
});

function makeCase(overrides: Partial<StructuredCase> = {}): StructuredCase {
  return {
    case_id: "CASE-GAP",
    case_version: 1,
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
    vi.mocked(getCaseOutputs).mockReset();
    vi.mocked(updateCase).mockReset();
    vi.mocked(getCaseOutputs).mockResolvedValue(makeCaseOutputs("CASE-GAP"));
  });

  it("loads backend analyst notes into the draft without enabling a stale blank save", async () => {
    vi.mocked(getCase).mockResolvedValue(
      makeCase({ analyst_notes: "Loaded analyst notes" }),
    );

    renderWithQueryClient(<CaseGapAnalysisWorkspace caseId="CASE-GAP" />);

    expect(await screen.findByDisplayValue("Loaded analyst notes")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save Notes" })).toBeDisabled();
    expect(screen.getByText("Run analysis to identify evidence gaps.")).toBeInTheDocument();
    expect(updateCase).not.toHaveBeenCalled();
  });
});
