import Link from "next/link";

import type {
  CaseAnalysisOutputStatus,
  CaseOutputItem,
  CaseOutputSourceType,
  CaseOutputsResponse,
} from "@/lib/cases";

export function outputSourceLabel(source: CaseOutputSourceType): string {
  switch (source) {
    case "analyst_input":
      return "Analyst-provided intake";
    case "user_input":
      return "User-provided input";
    case "log":
      return "Log evidence";
    case "document":
      return "Document evidence";
    case "system_rule":
      return "Deterministic candidate";
    case "rag":
      return "Analysis-derived";
    case "manual_edit":
      return "Analyst edited";
    case "legacy_unverified":
      return "Legacy / unverified";
  }
}

export function analysisStatusLabel(status: CaseAnalysisOutputStatus): string {
  switch (status) {
    case "not_started":
      return "Analysis not started";
    case "pending":
      return "Analysis pending";
    case "completed":
      return "Current analysis completed";
    case "stale":
      return "Analysis stale";
    case "failed":
      return "Analysis failed";
    case "expired":
      return "Analysis context expired";
  }
}

export function OutputProvenance({ item }: { item: CaseOutputItem }) {
  return (
    <div className="mt-3 flex flex-wrap gap-2 text-[10px] font-black uppercase tracking-wider text-neutral">
      <span className="border border-black/15 bg-white px-2 py-1">
        {outputSourceLabel(item.source_type)}
      </span>
      <span className="border border-black/15 bg-white px-2 py-1">
        {item.review_status.replaceAll("_", " ")}
      </span>
      <span className="border border-black/15 bg-white px-2 py-1">
        Case v{item.case_version}
      </span>
      {item.analysis_run_id ? (
        <span className="border border-black/15 bg-white px-2 py-1">
          Run {item.analysis_run_id.slice(-8)}
        </span>
      ) : null}
    </div>
  );
}

type SummaryTile = {
  title: string;
  count: number;
  status: string;
  preview: string;
  href?: string;
};

function emptyCopy(
  key: "evidence" | "gaps" | "attack_mappings" | "recommendations",
  status: CaseAnalysisOutputStatus,
): string {
  if (key === "gaps") {
    return status === "pending"
      ? "Analysis is running. Previous gaps are not counted as current."
      : "Run analysis to identify evidence gaps.";
  }
  if (key === "recommendations") {
    return status === "pending"
      ? "Analysis is running. Previous recommendations are not counted as current."
      : "Run analysis to generate recommendations.";
  }
  if (key === "attack_mappings") {
    return "No current ATT&CK candidates are available.";
  }
  return "No intake evidence has been recorded.";
}

export default function CaseOutputSummaryCards({ data }: { data: CaseOutputsResponse }) {
  const { outputs, analysis } = data;
  const evidenceSourceSummary = outputs.evidence.source_types
    .map(outputSourceLabel)
    .join(" / ");
  const tiles: SummaryTile[] = [
    {
      title: "Evidence",
      count: outputs.evidence.current_count,
      href: `/cases/${data.case_id}/evidence`,
      status: outputs.evidence.current_count
        ? evidenceSourceSummary || "Current evidence"
        : "No current evidence",
      preview: outputs.evidence.items[0]?.title || emptyCopy("evidence", analysis.status),
    },
    {
      title: "Gaps",
      count: outputs.gaps.current_count,
      href: `/cases/${data.case_id}/gap-analysis`,
      status: outputs.gaps.current_count ? "Current analysis output" : analysisStatusLabel(analysis.status),
      preview: outputs.gaps.items[0]?.title || emptyCopy("gaps", analysis.status),
    },
    {
      title: "ATT&CK Mapping",
      count: outputs.attack_mappings.current_count,
      href: `/cases/${data.case_id}/attack-mapping`,
      status: outputs.attack_mappings.current_count
        ? outputs.attack_mappings.source_types.includes("rag")
          ? "Analysis-derived candidates"
          : "Unreviewed intake candidates"
        : analysisStatusLabel(analysis.status),
      preview:
        outputs.attack_mappings.items[0]?.title || emptyCopy("attack_mappings", analysis.status),
    },
    {
      title: "Recommendations",
      count: outputs.recommendations.current_count,
      status: outputs.recommendations.current_count
        ? "Current analysis output"
        : analysisStatusLabel(analysis.status),
      preview:
        outputs.recommendations.items[0]?.title || emptyCopy("recommendations", analysis.status),
    },
  ];
  const historicalCount = Object.values(data.historical_outputs).reduce(
    (total, bucket) => total + bucket.historical_count,
    0,
  );

  return (
    <aside className="border border-black/10 bg-white p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="mono-label">Generated Case Outputs</p>
        <span className="border border-black/15 px-2 py-1 text-[10px] font-black uppercase tracking-wider">
          {analysisStatusLabel(analysis.status)}
        </span>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
        {tiles.map((tile) => {
          const content = (
            <>
              <div className="flex items-start justify-between gap-3">
                <h2 className="text-lg font-black">{tile.title}</h2>
                <span className="text-3xl font-black">{tile.count}</span>
              </div>
              <p className="mt-3 text-xs font-black uppercase text-neutral">{tile.status}</p>
              <p className="mt-2 line-clamp-3 text-sm font-semibold leading-6 text-neutral-900">
                {tile.preview}
              </p>
            </>
          );
          return tile.href ? (
            <Link
              key={tile.title}
              href={tile.href}
              className="block min-h-40 border border-black/10 bg-neutral-50 p-4 transition hover:border-black hover:bg-white"
            >
              {content}
            </Link>
          ) : (
            <article key={tile.title} className="min-h-40 border border-black/10 bg-neutral-50 p-4">
              {content}
            </article>
          );
        })}
      </div>
      {historicalCount ? (
        <p className="mt-4 border-t border-black/10 pt-3 text-xs font-semibold text-neutral">
          {historicalCount} historical output item(s) are retained for audit and excluded from current counts.
        </p>
      ) : null}
    </aside>
  );
}
