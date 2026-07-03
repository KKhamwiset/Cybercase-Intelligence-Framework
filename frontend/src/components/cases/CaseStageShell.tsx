"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import CyberCaseShell from "@/components/CyberCaseShell";
import type { StructuredCase } from "@/lib/cases";

const STAGES = [
  { label: "Intake", href: "intake" },
  { label: "Gap Analysis", href: "gap-analysis" },
  { label: "ATT&CK Mapping", href: "attack-mapping" },
  { label: "Report", href: "report" },
];

export default function CaseStageShell({
  activeStage,
  caseData,
  children,
  actions,
}: {
  activeStage: string;
  caseData: StructuredCase;
  children: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <CyberCaseShell
      activeNav="Investigate"
      title={caseData.title}
      subtitle={`Case ${caseData.case_id}`}
      actions={actions}
    >
      <div className="h-full overflow-auto bg-neutral-100">
        <div className="border-b border-black/10 bg-white px-5 py-3">
          <nav className="flex flex-wrap gap-2 text-xs font-black">
            {STAGES.map((stage) => (
              <Link
                key={stage.href}
                href={`/cases/${caseData.case_id}/${stage.href}`}
                className={`border px-3 py-2 ${
                  activeStage === stage.href
                    ? "border-black bg-black text-white"
                    : "border-black/15 bg-white text-black hover:border-black"
                }`}
              >
                {stage.label}
              </Link>
            ))}
          </nav>
        </div>
        {children}
      </div>
    </CyberCaseShell>
  );
}
