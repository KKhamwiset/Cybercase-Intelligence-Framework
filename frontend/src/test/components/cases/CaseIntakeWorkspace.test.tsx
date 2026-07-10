import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CaseIntakeWorkspace from "@/components/cases/CaseIntakeWorkspace";
import { getCase, getCaseOutputs, updateCase } from "@/lib/cases";
import type { StructuredCase } from "@/lib/cases";
import { renderWithQueryClient } from "@/test/renderWithQueryClient";
import { makeCaseOutputs, makeOutputItem } from "@/test/caseOutputs";

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
    case_id: "CASE-INTAKE",
    case_version: 1,
    title: "Intake case",
    case_type: "incident",
    status: "new",
    severity: "unknown",
    incident_summary: "",
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

describe("CaseIntakeWorkspace", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    vi.mocked(getCase).mockReset();
    vi.mocked(getCaseOutputs).mockReset();
    vi.mocked(updateCase).mockReset();
    vi.mocked(getCaseOutputs).mockResolvedValue(makeCaseOutputs("CASE-INTAKE"));
  });

  it("keeps the saved narrative editable and uses authoritative pre-analysis output counts", async () => {
    vi.mocked(getCase).mockResolvedValue(makeCase());
    vi.mocked(getCaseOutputs).mockResolvedValue(
      makeCaseOutputs("CASE-INTAKE", {
        evidence: [
          makeOutputItem({
            item_id: "E-001",
            title: "Original phishing email",
            source_type: "analyst_input",
            analysis_run_id: null,
            status: "unknown",
          }),
        ],
        attackMappings: [
          makeOutputItem({
            item_id: "T1566",
            title: "Phishing",
            source_type: "system_rule",
            analysis_run_id: null,
          }),
        ],
      }),
    );
    vi.mocked(updateCase).mockResolvedValue(
      makeCase({
        incident_summary: "Finance phishing narrative",
        evidence_items: [
          {
            evidence_id: "E-001",
            title: "Original phishing email",
            description: "Original phishing email",
            source_type: "system_rule",
            status: "candidate",
            confidence: "medium",
            analyst_verified: false,
          },
        ],
        gaps: ["Confirm fraudulent payment status."],
        attack_mappings: [
          {
            mapping_id: "MAP-001",
            technique_id: "T1566",
            technique_name: "Phishing",
            tactic: "Initial Access",
            rationale: "Phishing narrative.",
            metadata: {
              status: "candidate",
              confidence: "high",
              evidence_ids: ["E-001"],
              source_type: "system_rule",
              analyst_verified: false,
            },
          },
        ],
        recommendations: [
          {
            action_id: "REC-001",
            title: "Validate payments",
            description: "Review payment approvals.",
            status: "candidate",
            metadata: {
              status: "candidate",
              confidence: "medium",
              evidence_ids: ["E-001"],
              source_type: "system_rule",
              analyst_verified: false,
            },
          },
        ],
      }),
    );

    renderWithQueryClient(<CaseIntakeWorkspace caseId="CASE-INTAKE" />);

    const narrativeBox = await screen.findByPlaceholderText(/Describe what happened/);
    fireEvent.change(narrativeBox, { target: { value: "Finance phishing narrative" } });
    fireEvent.click(screen.getByRole("button", { name: "Save Intake" }));

    await waitFor(() => {
      expect(updateCase).toHaveBeenCalledWith("CASE-INTAKE", {
        incident_summary: "Finance phishing narrative",
      });
    });
    expect(await screen.findByText("Generated Case Outputs")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Finance phishing narrative")).toBeInTheDocument();
    expect(
      screen
        .getAllByRole("link", { name: /Evidence/i })
        .some((link) => link.getAttribute("href") === "/cases/CASE-INTAKE/evidence"),
    ).toBe(true);
    expect(
      screen
        .getAllByRole("link", { name: /Gaps/i })
        .some((link) => link.getAttribute("href") === "/cases/CASE-INTAKE/gap-analysis"),
    ).toBe(true);
    expect(
      screen
        .getAllByRole("link", { name: /ATT&CK Mapping/i })
        .some(
          (link) => link.getAttribute("href") === "/cases/CASE-INTAKE/attack-mapping",
        ),
    ).toBe(true);
    expect(screen.getByText("Unreviewed intake candidates")).toBeInTheDocument();
    expect(screen.getByText("Run analysis to identify evidence gaps.")).toBeInTheDocument();
    expect(screen.getByText("Run analysis to generate recommendations.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open investigation chat" })).toHaveAttribute(
      "href", "/cases/CASE-INTAKE/chat",
    );
  });

  it("loads a saved backend narrative into the editable draft when no tab draft exists", async () => {
    vi.mocked(getCase).mockResolvedValue(
      makeCase({
        incident_summary: "Saved backend narrative",
        gaps: ["Confirm recipient account."],
      }),
    );

    renderWithQueryClient(<CaseIntakeWorkspace caseId="CASE-INTAKE" />);

    expect(await screen.findByDisplayValue("Saved backend narrative")).toBeInTheDocument();
    expect(screen.getByText("Generated Case Outputs")).toBeInTheDocument();
    expect(screen.getAllByText("Evidence").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Gaps").length).toBeGreaterThan(0);
    expect(screen.getAllByText("ATT&CK Mapping").length).toBeGreaterThan(0);
    expect(screen.getByText("Recommendations")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save Intake" })).toBeDisabled();
  });

  it("preserves an intentional blank session draft over a saved backend narrative", async () => {
    window.sessionStorage.setItem(
      "cybercase:CASE-INTAKE:incident_summary",
      JSON.stringify(""),
    );
    vi.mocked(getCase).mockResolvedValue(
      makeCase({ incident_summary: "Saved backend narrative" }),
    );

    renderWithQueryClient(<CaseIntakeWorkspace caseId="CASE-INTAKE" />);

    const narrativeBox = await screen.findByPlaceholderText(/Describe what happened/);
    expect(narrativeBox).toHaveValue("");
    expect(screen.getByRole("button", { name: "Save Intake" })).toBeDisabled();
  });
});
