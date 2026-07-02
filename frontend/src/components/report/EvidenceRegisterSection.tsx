import type { EvidenceItemView, ReportSection as ReportSectionView } from "@/lib/reports";
import ReportSection from "./ReportSection";
import { FindingStatusBadge } from "./status";

function isEvidence(value: unknown): value is EvidenceItemView {
  return typeof value === "object" && value !== null && "evidence_id" in value && "title" in value;
}

export default function EvidenceRegisterSection({ section }: { section: ReportSectionView }) {
  const evidence = Array.isArray(section.content.evidence)
    ? section.content.evidence.filter(isEvidence)
    : [];

  return (
    <ReportSection section={section}>
      {evidence.length ? (
        <div className="grid gap-3 md:grid-cols-2">
          {evidence.map((item) => (
            <div key={item.evidence_id} className="border border-black/10 p-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-black uppercase text-neutral">{item.evidence_id}</p>
                  <p className="font-black">{item.title}</p>
                </div>
                <FindingStatusBadge status={item.status} />
              </div>
              {item.description ? (
                <p className="mt-2 text-sm text-neutral-800">{item.description}</p>
              ) : null}
              <p className="mt-3 text-xs font-semibold text-neutral">
                Source: {item.source_type} | Confidence: {item.confidence}
              </p>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm font-semibold text-neutral">No evidence items available.</p>
      )}
    </ReportSection>
  );
}
