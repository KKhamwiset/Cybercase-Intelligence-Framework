import type { ReportViewModel } from "@/lib/reports";

export default function ReportStatusBanner({ report }: { report: ReportViewModel }) {
  const text =
    report.report_status === "ready_for_review"
      ? "Ready for review"
      : report.report_status === "incomplete"
        ? "Incomplete: evidence gaps detected"
        : "Draft: awaiting analyst validation";

  return (
    <div className="border-b border-black/10 bg-neutral-100 px-5 py-3">
      <p className="text-sm font-black">{text}</p>
    </div>
  );
}
