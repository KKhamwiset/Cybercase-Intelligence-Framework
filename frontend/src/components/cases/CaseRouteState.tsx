"use client";

import CyberCaseShell from "@/components/CyberCaseShell";

export default function CaseRouteState({
  title,
  message,
}: {
  title: string;
  message: string;
}) {
  return (
    <CyberCaseShell activeNav="Investigate" title={title}>
      <div className="h-full overflow-auto bg-neutral-100 p-5">
        <div className="border border-black/10 bg-white p-5 text-sm font-semibold">
          {message}
        </div>
      </div>
    </CyberCaseShell>
  );
}
