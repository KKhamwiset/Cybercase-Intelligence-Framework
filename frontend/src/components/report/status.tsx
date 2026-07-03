import type { FindingStatus, ReportSectionStatus } from "@/lib/reports";

export function FindingStatusBadge({ status }: { status: FindingStatus }) {
  const label =
    status === "confirmed"
      ? "Confirmed"
      : status === "candidate"
        ? "Candidate"
        : "Unknown";
  const className =
    status === "confirmed"
      ? "border-black bg-black text-white"
      : status === "candidate"
        ? "border-black/40 bg-white text-black"
        : "border-black/15 bg-neutral-100 text-neutral";

  return (
    <span className={`inline-flex shrink-0 border px-2 py-1 text-[10px] font-black uppercase ${className}`}>
      {label}
    </span>
  );
}

export function SectionStatusBadge({ status }: { status: ReportSectionStatus }) {
  const label =
    status === "complete" ? "Complete" : status === "partial" ? "Partial" : "Missing";
  const className =
    status === "complete"
      ? "bg-black text-white"
      : status === "partial"
        ? "border border-black/30 bg-white text-black"
        : "bg-neutral-100 text-neutral";

  return (
    <span className={`inline-flex shrink-0 px-2 py-1 text-[10px] font-black uppercase ${className}`}>
      {label}
    </span>
  );
}
