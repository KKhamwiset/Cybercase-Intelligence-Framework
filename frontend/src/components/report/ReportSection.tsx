import type { ReactNode } from "react";

import type { ReportSection as ReportSectionView } from "@/lib/reports";
import { SectionStatusBadge } from "./status";

export default function ReportSection({
  section,
  children,
}: {
  section: ReportSectionView;
  children: ReactNode;
}) {
  return (
    <section className="border-b border-black/10 bg-white px-5 py-5">
      <div className="mb-4 flex items-start justify-between gap-3">
        <h2 className="text-base font-black">{section.title}</h2>
        <SectionStatusBadge status={section.status} />
      </div>
      {children}
    </section>
  );
}
