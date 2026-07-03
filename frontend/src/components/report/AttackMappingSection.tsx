import type {
  AttackTacticGroupView,
  ReportSection as ReportSectionView,
} from "@/lib/reports";
import ReportSection from "./ReportSection";
import { FindingStatusBadge } from "./status";

function isTacticGroup(value: unknown): value is AttackTacticGroupView {
  return typeof value === "object" && value !== null && "tactic" in value && "mappings" in value;
}

export default function AttackMappingSection({ section }: { section: ReportSectionView }) {
  const tactics = Array.isArray(section.content.tactics)
    ? section.content.tactics.filter(isTacticGroup)
    : [];

  return (
    <ReportSection section={section}>
      {tactics.length ? (
        <div className="space-y-4">
          {tactics.map((group) => (
            <div key={group.tactic} className="border border-black/10">
              <div className="border-b border-black/10 bg-neutral-100 px-3 py-2 text-xs font-black uppercase">
                {group.tactic}
              </div>
              <div className="divide-y divide-black/10">
                {group.mappings.map((mapping) => (
                  <div key={mapping.mapping_id} className="grid gap-3 px-3 py-3 md:grid-cols-[170px_1fr_120px]">
                    <div>
                      <p className="font-black">{mapping.technique_id}</p>
                      <p className="text-xs font-semibold text-neutral">{mapping.technique_name}</p>
                    </div>
                    <div>
                      <p className="text-sm text-neutral-800">{mapping.rationale || "No rationale recorded."}</p>
                      <p className="mt-2 text-xs font-semibold text-neutral">
                        Evidence: {mapping.evidence_ids.join(", ") || "None"}
                      </p>
                      {mapping.status === "candidate" ? (
                        <p className="mt-2 text-xs font-black uppercase">Analyst validation required</p>
                      ) : null}
                    </div>
                    <FindingStatusBadge status={mapping.status} />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm font-semibold text-neutral">No ATT&CK mappings available.</p>
      )}
    </ReportSection>
  );
}
