"use client";

import { useParams } from "next/navigation";

import CaseChatWorkspace from "@/components/cases/CaseChatWorkspace";
import { getRouteParam } from "@/lib/routeParams";

export default function CaseChatPage() {
  const params = useParams();
  const caseId = getRouteParam(params.caseId);

  return <CaseChatWorkspace caseId={caseId} />;
}
