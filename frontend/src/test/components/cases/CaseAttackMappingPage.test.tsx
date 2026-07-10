import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CaseAttackMappingPage from "@/app/cases/[caseId]/attack-mapping/page";
import { getCase, getCaseOutputs } from "@/lib/cases";
import { getCaseReportReadiness } from "@/lib/case-chat";
import { renderWithQueryClient } from "@/test/renderWithQueryClient";
import { makeCaseOutputs, makeOutputItem } from "@/test/caseOutputs";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => ({ caseId: "CASE-MAP" }),
  useRouter: () => ({ push }),
}));

vi.mock("@/lib/cases", async () => {
  const actual = await vi.importActual<typeof import("@/lib/cases")>("@/lib/cases");
  return { ...actual, getCase: vi.fn(), getCaseOutputs: vi.fn(), updateCase: vi.fn() };
});

vi.mock("@/lib/case-chat", async () => {
  const actual = await vi.importActual<typeof import("@/lib/case-chat")>("@/lib/case-chat");
  return { ...actual, getCaseReportReadiness: vi.fn() };
});

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, generateCaseReport: vi.fn() };
});

function makeCase() {
  return {
    case_id: "CASE-MAP",
    case_version: 1,
    title: "Mapping case",
    case_type: "incident",
    status: "investigating" as const,
    severity: "high" as const,
    incident_summary: "A saved phishing incident.",
    affected_users: [],
    affected_assets: [],
    timeline_events: [],
    evidence_items: [],
    attack_mappings: [{
      mapping_id: "MAP-1",
      technique_id: "T1566",
      technique_name: "Phishing",
      rationale: "Email lure reported in intake.",
      metadata: {
        status: "candidate" as const,
        confidence: "medium" as const,
        evidence_ids: [],
        source_type: "system_rule" as const,
        analyst_verified: false,
      },
    }],
    containment_actions: [],
    recommendations: [],
    gaps: [],
    limitations: [],
    analyst_notes: "",
  };
}

function readiness(overrides = {}) {
  return {
    case_id: "CASE-MAP",
    current_case_version: 1,
    current_case_snapshot_hash: "a".repeat(64),
    analysis_status: "missing" as const,
    report_eligible: false,
    reason: "analysis_required" as const,
    latest_analysis_turn_id: null,
    latest_retrieval_context_id: null,
    ...overrides,
  };
}

describe("CaseAttackMappingPage", () => {
  beforeEach(() => {
    push.mockReset();
    vi.mocked(getCase).mockReset();
    vi.mocked(getCaseOutputs).mockReset();
    vi.mocked(getCaseReportReadiness).mockReset();
    vi.mocked(getCase).mockResolvedValue(makeCase());
    vi.mocked(getCaseOutputs).mockResolvedValue(
      makeCaseOutputs("CASE-MAP", {
        attackMappings: [makeOutputItem({
          item_id: "T1566",
          title: "Phishing",
          description: "Email lure reported in intake.",
          source_type: "system_rule",
          analysis_run_id: null,
        })],
      }),
    );
  });

  it("labels saved mappings as intake-derived system-rule candidates", async () => {
    vi.mocked(getCaseReportReadiness).mockResolvedValue(readiness());
    renderWithQueryClient(<CaseAttackMappingPage />);

    expect(await screen.findByRole("heading", { name: "Intake-derived ATT&CK candidates" })).toBeInTheDocument();
    expect(screen.getByText(/Counts and items come from the backend lifecycle view/i)).toBeInTheDocument();
    expect(screen.getByText("Deterministic candidate")).toBeInTheDocument();
    expect(screen.getByText("Candidate - analyst review required")).toBeInTheDocument();
    expect(screen.getByText("No current RAG analysis for this case version")).toBeInTheDocument();
  });

  it("shows report generation when current analysis is available", async () => {
    vi.mocked(getCaseReportReadiness).mockResolvedValue(readiness({
      analysis_status: "completed",
      report_eligible: true,
      reason: "ready",
    }));
    vi.mocked(getCaseOutputs).mockResolvedValue(makeCaseOutputs("CASE-MAP", { status: "completed" }));
    renderWithQueryClient(<CaseAttackMappingPage />);

    expect(await screen.findByText("Current investigation analysis available")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate preliminary report" })).toBeEnabled();
  });
});
