import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CaseEvidenceWorkspace from "@/components/cases/CaseEvidenceWorkspace";
import { getCase, getCaseOutputs } from "@/lib/cases";
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
  };
});

function makeCase(overrides: Partial<StructuredCase> = {}): StructuredCase {
  return {
    case_id: "CASE-EVIDENCE",
    case_version: 1,
    title: "Evidence case",
    case_type: "incident",
    status: "new",
    severity: "medium",
    incident_summary: "Saved narrative",
    affected_users: [],
    affected_assets: [],
    timeline_events: [],
    evidence_items: [
      {
        evidence_id: "E-001",
        title: "Proxy log",
        description: "Outbound connection to suspicious domain.",
        source_type: "log",
        status: "confirmed",
        confidence: "high",
        analyst_verified: true,
        collected_at: "2026-07-03T10:00:00Z",
      },
    ],
    attack_mappings: [
      {
        mapping_id: "MAP-001",
        technique_id: "T1566",
        technique_name: "Phishing",
        tactic: "Initial Access",
        rationale: "User received a phishing email.",
        metadata: {
          status: "candidate",
          confidence: "medium",
          evidence_ids: ["E-001"],
          source_type: "system_rule",
          analyst_verified: false,
        },
      },
    ],
    containment_actions: [],
    recommendations: [
      {
        action_id: "REC-001",
        title: "Collect mailbox headers",
        description: "Export full headers for sender validation.",
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
    gaps: [],
    limitations: [],
    analyst_notes: "",
    ...overrides,
  };
}

describe("CaseEvidenceWorkspace", () => {
  beforeEach(() => {
    vi.mocked(getCase).mockReset();
    vi.mocked(getCaseOutputs).mockReset();
  });

  it("renders authoritative analyst evidence with related current outputs", async () => {
    vi.mocked(getCase).mockResolvedValue(makeCase());
    vi.mocked(getCaseOutputs).mockResolvedValue(
      makeCaseOutputs("CASE-EVIDENCE", {
        evidence: [makeOutputItem({
          item_id: "E-001",
          title: "Proxy log",
          description: "Outbound connection to suspicious domain.",
          source_type: "analyst_input",
          analysis_run_id: null,
          source_references: ["E-001"],
          status: "unknown",
        })],
        attackMappings: [makeOutputItem({
          item_id: "T1566",
          title: "Phishing",
          source_references: ["E-001"],
        })],
        recommendations: [makeOutputItem({
          item_id: "REC-001",
          title: "Collect mailbox headers",
          source_references: ["E-001"],
        })],
      }),
    );

    renderWithQueryClient(<CaseEvidenceWorkspace caseId="CASE-EVIDENCE" />);

    expect(await screen.findByText("Proxy log")).toBeInTheDocument();
    expect(screen.getByText("E-001")).toBeInTheDocument();
    expect(screen.getByText("Outbound connection to suspicious domain.")).toBeInTheDocument();
    expect(screen.getByText("T1566 Phishing")).toBeInTheDocument();
    expect(screen.getByText("Collect mailbox headers")).toBeInTheDocument();
    expect(screen.getAllByText("Analyst-provided intake").length).toBeGreaterThan(0);
    expect(screen.getByText(/analyst-provided, not system-confirmed/i)).toBeInTheDocument();
  });

  it("handles empty evidence cleanly", async () => {
    vi.mocked(getCase).mockResolvedValue(makeCase({ evidence_items: [] }));
    vi.mocked(getCaseOutputs).mockResolvedValue(makeCaseOutputs("CASE-EVIDENCE"));

    renderWithQueryClient(<CaseEvidenceWorkspace caseId="CASE-EVIDENCE" />);

    expect(
      await screen.findByText("No analyst-provided intake evidence is available for this case."),
    ).toBeInTheDocument();
  });
});
