"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import CyberCaseShell from "@/components/CyberCaseShell";
import type { StructuredCase } from "@/lib/cases";

const STAGES = [
  { label: "Intake", href: "intake" },
  { label: "Chat", href: "chat" },
  { label: "Evidence", href: "evidence" },
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
      <div className="flex h-full flex-col overflow-hidden bg-neutral-100">
        <div className="shrink-0 border-b border-black/10 bg-white px-5 py-3">
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
        <div className="min-h-0 flex-1 overflow-auto">{children}</div>
      </div>
    </CyberCaseShell>
  );
}
