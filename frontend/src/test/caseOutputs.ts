import type {
  CaseAnalysisOutputStatus,
  CaseOutputItem,
  CaseOutputSourceType,
  CaseOutputsResponse,
} from "@/lib/cases";

export function makeOutputItem(overrides: Partial<CaseOutputItem> = {}): CaseOutputItem {
  return {
    item_id: "OUT-001",
    title: "Output item",
    description: "",
    source_type: "rag",
    analysis_run_id: "CCT-analysis",
    case_version: 1,
    generated_at: "2026-07-10T00:00:00Z",
    source_references: [],
    review_status: "unreviewed",
    status: "candidate",
    details: {},
    ...overrides,
  };
}

function sourceTypes(items: CaseOutputItem[]): CaseOutputSourceType[] {
  return [...new Set(items.map((item) => item.source_type))];
}

export function makeCaseOutputs(
  caseId: string,
  options: {
    status?: CaseAnalysisOutputStatus;
    evidence?: CaseOutputItem[];
    gaps?: CaseOutputItem[];
    attackMappings?: CaseOutputItem[];
    recommendations?: CaseOutputItem[];
  } = {},
): CaseOutputsResponse {
  const evidence = options.evidence ?? [];
  const gaps = options.gaps ?? [];
  const attackMappings = options.attackMappings ?? [];
  const recommendations = options.recommendations ?? [];
  const bucket = (items: CaseOutputItem[]) => ({
    current_count: items.length,
    items,
    source_types: sourceTypes(items),
  });
  const historical = () => ({ historical_count: 0, items: [] });
  return {
    case_id: caseId,
    case_version: 1,
    analysis: {
      status: options.status ?? "not_started",
      analysis_run_id: options.status === "completed" ? "CCT-analysis" : null,
      analyzed_case_version: options.status === "completed" ? 1 : null,
      analyzed_snapshot_hash: options.status === "completed" ? "a".repeat(64) : null,
    },
    outputs: {
      evidence: bucket(evidence),
      gaps: bucket(gaps),
      attack_mappings: bucket(attackMappings),
      recommendations: bucket(recommendations),
    },
    historical_outputs: {
      evidence: historical(),
      gaps: historical(),
      attack_mappings: historical(),
      recommendations: historical(),
    },
  };
}
