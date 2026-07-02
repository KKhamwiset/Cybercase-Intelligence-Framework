import type { ReportViewModel } from "@/lib/reports";

export default function ReportHeader({ report }: { report: ReportViewModel }) {
  return (
    <div className="border-b border-black/10 bg-white px-5 py-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="mono-label">Incident Analysis</p>
          <h1 className="mt-1 text-2xl font-black tracking-tight">
            Case {report.case_id}
          </h1>
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs font-bold text-neutral md:grid-cols-4">
          <span>Evidence {report.metadata.evidence_count}</span>
          <span>Gaps {report.metadata.gap_count}</span>
          <span>Candidate {report.metadata.candidate_findings}</span>
          <span>Generated {report.generated_at.slice(0, 10)}</span>
        </div>
      </div>
    </div>
  );
}
