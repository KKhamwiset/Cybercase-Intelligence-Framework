"use client";

import { useParams } from "next/navigation";

import CaseTextWorkflow from "@/components/cases/CaseTextWorkflow";
import { getRouteParam } from "@/lib/routeParams";

export default function CaseGapAnalysisPage() {
  const params = useParams();
  const caseId = getRouteParam(params.caseId);

  return (
    <CaseTextWorkflow
      caseId={caseId}
      activeStage="gap-analysis"
      heading="Gap Analysis"
      config={{
        field: "analyst_notes",
        label: "Gap analysis notes",
        description:
          "Record missing facts, analyst answers, and validation concerns. These notes remain attached to the case across workflow pages.",
        placeholder: "List missing timestamps, evidence, affected scope, containment status, or analyst follow-up answers.",
      }}
    />
  );
}
