"use client";

import { useParams } from "next/navigation";

import CaseIntakeWorkspace from "@/components/cases/CaseIntakeWorkspace";
import { getRouteParam } from "@/lib/routeParams";

export default function CaseIntakePage() {
  const params = useParams();
  const caseId = getRouteParam(params.caseId);

  return <CaseIntakeWorkspace caseId={caseId} />;
}
