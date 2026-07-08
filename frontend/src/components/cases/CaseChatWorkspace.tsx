"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";

import CaseRouteState from "@/components/cases/CaseRouteState";
import CaseStageShell from "@/components/cases/CaseStageShell";
import CaseAnalysisAssistantPanel from "@/components/cases/CaseAnalysisAssistantPanel";
import CaseContextPanel from "@/components/cases/CaseContextPanel";
import { isNotFound, useCase } from "@/hooks/useCase";
import {
  startCaseAnalysis,
  getCaseAnalysis,
  submitCaseAnalysisFollowUp,
  generateCaseReport,
  CaseAnalysisResponse,
  ReportType,
} from "@/lib/api";

export default function CaseChatWorkspace({ caseId }: { caseId: string | null }) {
  const router = useRouter();
  const caseQuery = useCase(caseId);
  const loadedCase = caseQuery.data;

  const [workflow, setWorkflow] = useState<CaseAnalysisResponse | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [retrievalContextId, setRetrievalContextId] = useState<string | undefined>(undefined);
  const [followupAnswer, setFollowupAnswer] = useState("");
  const [reportType, setReportType] = useState<ReportType>("overview");
  const [legal, setLegal] = useState(false);
  const [error, setError] = useState("");

  function updateWorkflowAndContext(data: CaseAnalysisResponse) {
    setWorkflow(data);
    if (data.retrieval_context_id) {
      setRetrievalContextId(data.retrieval_context_id);
    }
  }

  useEffect(() => {
    if (!caseId) return;
    const activeCaseId = caseId;
    async function loadActiveWorkflow() {
      try {
        const data = await getCaseAnalysis(activeCaseId);
        updateWorkflowAndContext(data);
      } catch {
        console.log("No case analysis found for case " + activeCaseId);
      }
    }
    loadActiveWorkflow();
  }, [caseId]);

  async function handleGenerate() {
    if (!caseId) return;

    setIsGenerating(true);
    setError("");
    try {
      const result = await startCaseAnalysis(caseId, reportType, legal);
      updateWorkflowAndContext(result);
    } catch (err: unknown) {
      console.error("Failed to run case analysis:", err);
      setError("Failed to run case analysis. Make sure database and RAG systems are operational.");
    } finally {
      setIsGenerating(false);
    }
  }

  async function handleResume() {
    if (!caseId || workflow?.workflow_status !== "needs_followup" || !workflow.session_id) return;

    setIsGenerating(true);
    setError("");
    try {
      const result = await submitCaseAnalysisFollowUp(caseId, workflow.session_id, followupAnswer.trim());
      updateWorkflowAndContext(result);
      setFollowupAnswer("");
    } catch (err: unknown) {
      console.error("Failed to resume analysis:", err);
      setError("Could not submit follow-up response.");
    } finally {
      setIsGenerating(false);
    }
  }

  async function handleGenerateReport() {
    if (!caseId) return;

    setIsGenerating(true);
    setError("");
    try {
      await generateCaseReport(caseId, reportType, legal, true, retrievalContextId);
      const updated = await getCaseAnalysis(caseId);
      updateWorkflowAndContext(updated);
    } catch (err: unknown) {
      console.error("Failed to generate report:", err);
      setError("Report generation failed. Please try again.");
    } finally {
      setIsGenerating(false);
    }
  }

  if (!caseId) {
    return <CaseRouteState title="Case Assistant" message="No case ID was provided." />;
  }

  if (caseQuery.isLoading) {
    return <CaseRouteState title="Case Assistant" message={`Loading case ${caseId}.`} />;
  }

  if (isNotFound(caseQuery.error)) {
    return <CaseRouteState title="Case Assistant" message={`Case ${caseId} was not found.`} />;
  }

  if (caseQuery.error || !loadedCase) {
    return <CaseRouteState title="Case Assistant" message="Could not load this case." />;
  }

  const activeCompleteness = workflow?.completeness ?? null;

  return (
    <CaseStageShell activeStage="chat" caseData={loadedCase}>
      <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
        {error && (
          <div className="border border-red-500/20 bg-red-50 p-4 text-xs font-semibold text-red-700">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
          <div className="lg:col-span-2">
            {workflow?.workflow_status === "report_generated" ? (
              <div className="border border-black/10 bg-white p-6 md:p-8 flex flex-col justify-between min-h-[480px]">
                <div className="space-y-6">
                  <div className="flex items-center justify-between border-b border-black pb-4">
                    <div>
                      <span className="text-[10px] font-black uppercase tracking-widest text-neutral-500">
                        Investigation Agent
                      </span>
                      <h3 className="text-xl font-black text-black mt-1">
                        Analysis Complete
                      </h3>
                    </div>
                    <span className="inline-flex border border-emerald-500/20 bg-emerald-50 px-2 py-1 text-[8px] font-black uppercase tracking-widest text-emerald-700">
                      Sufficient
                    </span>
                  </div>

                  <div className="border border-emerald-500/10 bg-emerald-50/50 p-5 rounded-sm">
                    <p className="text-xs font-bold text-emerald-800 leading-relaxed">
                      Incident data readiness is sufficient. The preliminary cyber incident report has been generated successfully and maps associated threat activities to MITRE ATT&CK.
                    </p>
                  </div>

                  <div className="space-y-3">
                    <h4 className="text-xs font-black uppercase tracking-wider text-neutral-500">
                      Analysis Parameters
                    </h4>
                    <div className="grid grid-cols-2 gap-4 text-xs border border-neutral-100 p-4 bg-neutral-50 rounded-sm">
                      <div>
                        <p className="text-[9px] font-bold text-neutral-400 uppercase">Report Type</p>
                        <p className="font-bold text-neutral-800 capitalize">{reportType}</p>
                      </div>
                      <div>
                        <p className="text-[9px] font-bold text-neutral-400 uppercase">Thai Legal Assessment</p>
                        <p className="font-bold text-neutral-800">
                          {legal ? "Enabled" : "Disabled"}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="mt-8 pt-4 border-t border-black/5 flex justify-end">
                  <button
                    onClick={() => router.push(`/cases/${caseId}/report`)}
                    className="border border-black bg-black px-6 py-3 text-xs font-black text-white hover:bg-neutral-800 transition uppercase tracking-wider"
                  >
                    Go to Report Workspace
                  </button>
                </div>
              </div>
            ) : (
              <CaseAnalysisAssistantPanel
                caseData={loadedCase}
                workflow={workflow}
                reportType={reportType}
                legal={legal}
                followupAnswer={followupAnswer}
                isGenerating={isGenerating}
                onReportTypeChange={setReportType}
                onLegalChange={setLegal}
                onFollowupAnswerChange={setFollowupAnswer}
                onStartAnalysis={handleGenerate}
                onSubmitFollowup={handleResume}
                onForceGenerate={handleGenerateReport}
              />
            )}
          </div>

          <div className="lg:col-span-1">
            <CaseContextPanel
              caseData={loadedCase}
              workflow={workflow}
              reportType={reportType}
              legal={legal}
              completeness={activeCompleteness}
            />
          </div>
        </div>
      </div>
    </CaseStageShell>
  );
}
