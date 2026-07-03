"use client";

import { useParams } from "next/navigation";

import CaseTextWorkflow from "@/components/cases/CaseTextWorkflow";
import { getRouteParam } from "@/lib/routeParams";

export default function CaseIntakePage() {
  const params = useParams();
  const caseId = getRouteParam(params.caseId);

  return (
    <CaseTextWorkflow
      caseId={caseId}
      activeStage="intake"
      heading="Case Intake"
      config={{
        field: "incident_summary",
        label: "Incident narrative",
        description:
          "Capture the analyst-provided incident narrative. This is persisted to the backend case record and reloaded from the case URL.",
        placeholder: "Describe what happened, who was affected, and what evidence exists.",
        autosave: true,
      }}
    />
  );
}
