"use client";

import { useParams } from "next/navigation";

import CaseGapAnalysisWorkspace from "@/components/cases/CaseGapAnalysisWorkspace";
import { getRouteParam } from "@/lib/routeParams";

export default function CaseGapAnalysisPage() {
  const params = useParams();
  const caseId = getRouteParam(params.caseId);

  return <CaseGapAnalysisWorkspace caseId={caseId} />;
}
