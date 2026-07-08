import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import CaseStageShell from "@/components/cases/CaseStageShell";
import type { StructuredCase } from "@/lib/cases";

function makeCase(): StructuredCase {
  return {
    case_id: "CASE-NAV",
    title: "Navigation case",
    case_type: "incident",
    status: "new",
    severity: "unknown",
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
  };
}

describe("CaseStageShell", () => {
  it("shows the case stages with Chat and Evidence after Intake", () => {
    render(
      <CaseStageShell activeStage="chat" caseData={makeCase()}>
        <div>Stage content</div>
      </CaseStageShell>,
    );

    const stageLabels = screen
      .getAllByRole("link")
      .map((link) => link.textContent)
      .filter((text) =>
        ["Intake", "Chat", "Evidence", "Gap Analysis", "ATT&CK Mapping", "Report"].includes(
          text || "",
        ),
      );

    expect(stageLabels).toEqual([
      "Intake",
      "Chat",
      "Evidence",
      "Gap Analysis",
      "ATT&CK Mapping",
      "Report",
    ]);
    expect(screen.queryByRole("button", { name: "Analyze" })).not.toBeInTheDocument();
  });
});
