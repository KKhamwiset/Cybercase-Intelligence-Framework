import type { ReportSection as ReportSectionView } from "@/lib/reports";
import ReportSection from "./ReportSection";

export default function ExecutiveSummarySection({ section }: { section: ReportSectionView }) {
  const summary = typeof section.content.summary === "string" ? section.content.summary : "";
  const severity = typeof section.content.severity === "string" ? section.content.severity : "unknown";
  const caseStatus = typeof section.content.case_status === "string" ? section.content.case_status : "unknown";

  return (
    <ReportSection section={section}>
      <p className="max-w-4xl text-sm leading-6 text-neutral-800">{summary}</p>
      <div className="mt-4 flex flex-wrap gap-2 text-[11px] font-black uppercase">
        <span className="border border-black/15 px-2 py-1">Severity: {severity}</span>
        <span className="border border-black/15 px-2 py-1">Status: {caseStatus}</span>
      </div>
    </ReportSection>
  );
}
