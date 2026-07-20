import type { ReportGap, ReportSection as ReportSectionView } from "@/lib/reports";
import ReportSection from "./ReportSection";

function isGap(value: unknown): value is ReportGap {
  return typeof value === "object" && value !== null && "gap_id" in value && "title" in value;
}

export default function GapsAndLimitationsSection({ section }: { section: ReportSectionView }) {
  const gaps = Array.isArray(section.content.gaps) ? section.content.gaps.filter(isGap) : [];
  const limitations = Array.isArray(section.content.limitations)
    ? section.content.limitations.filter((item): item is string => typeof item === "string")
    : [];

  return (
    <ReportSection section={section}>
      <details className="border border-black/10" open={gaps.length > 0}>
        <summary className="cursor-pointer bg-neutral-100 px-3 py-3 text-sm font-black">
          Evidence Gaps and Limitations
        </summary>
        <div className="space-y-4 p-3">
          {gaps.length ? (
            <div className="space-y-2">
              {gaps.map((gap) => (
                <div key={gap.gap_id} className="border border-black/10 p-3">
                  <p className="text-xs font-black uppercase text-neutral">{gap.priority} priority</p>
                  <p className="mt-1 font-black">{gap.title}</p>
                  <p className="mt-1 text-sm text-neutral-800">{gap.description}</p>
                </div>
              ))}
            </div>
          ) : null}
          {limitations.length ? (
            <ul className="space-y-2 text-sm font-semibold text-neutral">
              {limitations.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : null}
        </div>
      </details>
    </ReportSection>
  );
}
