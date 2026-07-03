"use client";

import CyberCaseShell from "@/components/CyberCaseShell";
import InvestigationWorkspace from "@/components/chat/InvestigationWorkspace";

export default function ChatPage() {
  return (
    <CyberCaseShell
      activeNav="Investigate"
      title="CyberCase Investigate"
      subtitle="Evidence-led cyber investigation workspace"
    >
      <InvestigationWorkspace />
    </CyberCaseShell>
  );
}
