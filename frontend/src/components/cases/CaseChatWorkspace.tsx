"use client";

import { useMemo } from "react";

import CaseRouteState from "@/components/cases/CaseRouteState";
import CaseStageShell from "@/components/cases/CaseStageShell";
import {
  buildSavedCaseDisplayMessage,
  buildSavedCasePrompt,
  hasSavedIntakeNarrative,
} from "@/components/cases/savedCasePrompt";
import InvestigationWorkspace from "@/components/chat/InvestigationWorkspace";
import { isNotFound, useCase } from "@/hooks/useCase";

export default function CaseChatWorkspace({ caseId }: { caseId: string | null }) {
  const caseQuery = useCase(caseId);
  const loadedCase = caseQuery.data;

  const hasSavedIntake = loadedCase ? hasSavedIntakeNarrative(loadedCase) : false;
  const savedCasePrompt = useMemo(
    () => (loadedCase ? buildSavedCasePrompt(loadedCase) : ""),
    [loadedCase],
  );
  const savedCaseDisplayMessage = loadedCase
    ? buildSavedCaseDisplayMessage(loadedCase)
    : "";

  if (!caseId) {
    return <CaseRouteState title="Case Chat" message="No case ID was provided." />;
  }

  if (caseQuery.isLoading) {
    return <CaseRouteState title="Case Chat" message={`Loading case ${caseId}.`} />;
  }

  if (isNotFound(caseQuery.error)) {
    return <CaseRouteState title="Case Chat" message={`Case ${caseId} was not found.`} />;
  }

  if (caseQuery.error || !loadedCase) {
    return <CaseRouteState title="Case Chat" message="Could not load this case." />;
  }

  return (
    <CaseStageShell activeStage="chat" caseData={loadedCase}>
      <InvestigationWorkspace
        key={`${loadedCase.case_id}-${hasSavedIntake ? "saved" : "empty"}`}
        title={`Analyze ${loadedCase.title}`}
        subtitle={`RAG analysis for case ${loadedCase.case_id}`}
        emptyTitle={hasSavedIntake ? "Analyzing saved case." : "Save Intake first."}
        emptyDescription={
          hasSavedIntake
            ? "CyberCase is sending the saved case narrative, evidence, gaps, and mappings through the RAG pipeline."
            : "This case chat uses saved Intake context. Save the incident narrative before starting saved-case analysis."
        }
        showCaseList={false}
        initialPrompt={hasSavedIntake ? savedCasePrompt : ""}
        initialDisplayMessage={savedCaseDisplayMessage}
        autoRunInitialPrompt={hasSavedIntake}
        contextPrefix={hasSavedIntake ? savedCasePrompt : ""}
        caseId={loadedCase.case_id}
      />
    </CaseStageShell>
  );
}
