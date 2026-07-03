"use client";

import { useParams } from "next/navigation";

import CaseEvidenceWorkspace from "@/components/cases/CaseEvidenceWorkspace";
import { getRouteParam } from "@/lib/routeParams";

export default function CaseEvidencePage() {
  const params = useParams();
  const caseId = getRouteParam(params.caseId);

  return <CaseEvidenceWorkspace caseId={caseId} />;
}
