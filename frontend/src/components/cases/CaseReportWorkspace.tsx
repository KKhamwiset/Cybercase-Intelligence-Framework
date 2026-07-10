"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import AccessibleDialog from "@/components/AccessibleDialog";
import CaseRouteState from "@/components/cases/CaseRouteState";
import CaseStageShell from "@/components/cases/CaseStageShell";
import { useCase } from "@/hooks/useCase";
import { getRouteParam } from "@/lib/routeParams";
import {
  generateCaseReport,
  getLatestCaseReport,
  updateReportReviewStatus,
  downloadReportExport,
} from "@/lib/api";
import {
  caseAnalysisKeys,
  getCaseReportReadiness,
  type CaseReportReadiness,
} from "@/lib/case-chat";
import type {
  ReportWorkflowResponse,
  ReviewStatus,
  ReportType,
} from "@/lib/api";
import ReportPreview from "@/components/report/ReportPreview";
import ReportCrudControls from "@/components/report/ReportCrudControls";
import { apiErrorMessage } from "@/lib/api-errors";

function getHttpStatus(error: unknown): number | undefined {
  if (typeof error !== "object" || error === null || !("response" in error)) {
    return undefined;
  }

  const response = (error as { response?: { status?: number } }).response;
  return response?.status;
}

function readinessPresentation(readiness: CaseReportReadiness) {
  switch (readiness.analysis_status) {
    case "stale":
      return {
        title: "Analysis stale",
        headline: "Case changed after the last analysis",
        description: "Refresh analysis before generating a report.",
      };
    case "expired":
      return {
        title: "Analysis context expired",
        headline: "Analysis context expired",
        description: "Refresh analysis before generating a report.",
      };
    case "pending":
      return {
        title: "Analysis in progress",
        headline: "Analysis in progress",
        description: "Report generation is unavailable until the current investigation analysis completes.",
      };
    case "failed":
      return {
        title: "Analysis failed",
        headline: "Analysis required before report generation",
        description: "The last analysis did not complete. Refresh analysis to try again.",
      };
    default:
      return {
        title: "Analysis required",
        headline: "Analysis required before report generation",
        description: "No current investigation analysis exists for this case version.",
      };
  }
}

export default function CaseReportWorkspace() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const params = useParams();
  const caseId = getRouteParam(params.caseId);
  const caseQuery = useCase(caseId);

  const [workflow, setWorkflow] = useState<ReportWorkflowResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);
  const [isExporting, setIsExporting] = useState<"md" | "pdf" | null>(null);
  const [isCrudBusy, setIsCrudBusy] = useState(false);
  const [isReplaceDialogOpen, setIsReplaceDialogOpen] = useState(false);

  function updateWorkflow(data: ReportWorkflowResponse) {
    setWorkflow(data);
  }

  const readinessQuery = useQuery({
    queryKey: caseId
      ? caseAnalysisKeys.readiness(caseId)
      : ["cases", "missing", "report-readiness"],
    queryFn: ({ signal }) => {
      if (!caseId) throw new Error("caseId is required");
      return getCaseReportReadiness(caseId, signal);
    },
    enabled: Boolean(caseId),
    retry: 1,
  });
  const [reportType, setReportType] = useState<ReportType>("overview");
  const [legal, setLegal] = useState(false);
  const [error, setError] = useState("");

  async function handleDownloadReport(format: "md" | "pdf") {
    if (!workflow || workflow.status !== "completed" || !workflow.report_id) return;
    setIsExporting(format);
    setError("");
    try {
      const blob = await downloadReportExport(workflow.report_id, format);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `cybercase-report-${workflow.report_id}.${format}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err: unknown) {
      console.error(`Failed to export report in format ${format}:`, err);
      setError(apiErrorMessage(err, `Failed to export report as ${format.toUpperCase()}.`));
    } finally {
      setIsExporting(null);
    }
  }

  useEffect(() => {
    if (!caseId) return;
    const activeCaseId = caseId;

    async function loadLatestReport() {
      setIsLoading(true);
      setError("");
      try {
        const data = await getLatestCaseReport(activeCaseId);
        updateWorkflow(data);
      } catch (err: unknown) {
        // If 404, it means no report has been generated yet, which is expected
        if (getHttpStatus(err) !== 404) {
          console.error("Failed to load case report:", err);
          setError("Could not retrieve existing case report.");
        }
      } finally {
        setIsLoading(false);
      }
    }
    loadLatestReport();
  }, [caseId]);

  async function handleGenerate(force: boolean = false) {
    if (!caseId || !readinessQuery.data?.report_eligible) return;

    const isReplacingCurrentReport = workflow?.status === "completed";
    setIsGenerating(true);
    setError("");
    try {
      const result = await generateCaseReport(caseId, reportType, legal, force);
      if (!isReplacingCurrentReport || result.status === "completed") {
        updateWorkflow(result);
      } else {
        const detail = "message" in result ? `${result.message} ` : "";
        setError(`${detail}The current report was kept unchanged.`);
      }
      await queryClient.invalidateQueries({ queryKey: caseAnalysisKeys.readiness(caseId) });
    } catch (err: unknown) {
      console.error("Failed to generate case report:", err);
      setError(apiErrorMessage(err, "Failed to generate report. Make sure database and RAG systems are operational."));
    } finally {
      setIsGenerating(false);
    }
  }

  async function handleReviewStatusChange(status: ReviewStatus) {
    if (!workflow || workflow.status !== "completed" || !workflow.report_id) return;

    setIsUpdatingStatus(true);
    setError("");
    try {
      const result = await updateReportReviewStatus(workflow.report_id, status);
      updateWorkflow(result);
    } catch (err) {
      console.error("Failed to update review status:", err);
      setError(apiErrorMessage(err, "Could not update review status."));
    } finally {
      setIsUpdatingStatus(false);
    }
  }

  if (!caseId) {
    return <CaseRouteState title="Case Report" message="No case ID provided." />;
  }

  if (caseQuery.isLoading || readinessQuery.isLoading) {
    return <CaseRouteState title="Case Report" message={`Loading case ${caseId}...`} />;
  }

  if (caseQuery.error || readinessQuery.error || !caseQuery.data || !readinessQuery.data) {
    return <CaseRouteState title="Case Report" message="Could not load this case." />;
  }

  const readiness = readinessQuery.data;
  const prerequisite = readinessPresentation(readiness);
  const activeReport = workflow?.status === "completed" ? workflow.report : null;
  const completedWorkflow = workflow?.status === "completed" ? workflow : null;
  const workflowError = workflow && "message" in workflow ? workflow : null;
  const actionsLocked = isGenerating || isUpdatingStatus || isExporting !== null || isCrudBusy;

  return (
    <CaseStageShell activeStage="report" caseData={caseQuery.data}>
      <div className="bg-[#FAF9F6] min-h-[600px] p-6">
        {error && (
          <div role="alert" className="mb-6 mx-auto max-w-5xl border border-red-200 bg-red-50 p-4 text-xs font-semibold text-red-800">
            {error}
          </div>
        )}

        {isLoading ? (
          <div className="flex flex-col items-center justify-center py-20">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-black border-t-transparent" />
            <p className="mt-4 text-xs font-black uppercase tracking-widest text-neutral">
              Retrieving Case Report...
            </p>
          </div>
        ) : !readiness.report_eligible ? (
          <div
            role="status"
            aria-live="polite"
            className="mx-auto max-w-2xl border border-black/15 bg-white p-6 md:p-8"
          >
            <p className="mono-label">{prerequisite.title}</p>
            <h2 className="mt-3 text-2xl font-black text-black">{prerequisite.headline}</h2>
            <p className="mt-3 text-sm font-semibold leading-6 text-neutral-800">
              {prerequisite.description}
            </p>
            <p className="mt-3 text-xs font-semibold text-neutral">
              Current case version: {readiness.current_case_version}
            </p>
            <button
              type="button"
              onClick={() => router.push(`/cases/${caseId}/chat`)}
              className="btn-primary mt-6"
            >
              Open investigation chat
            </button>
          </div>
        ) : workflowError ? (
          <div className="mx-auto max-w-2xl border border-red-200 bg-white p-6 text-center">
            <h3 className="text-base font-black text-red-800">
              Report generation could not complete
            </h3>
            <p className="mt-3 text-sm leading-6 text-red-700">
              {workflowError.message}
            </p>
          </div>
        ) : workflow?.status === "completed" && activeReport ? (
          <div className="mx-auto max-w-5xl space-y-6">
            {isGenerating ? (
              <div
                role="status"
                aria-live="polite"
                className="flex items-center gap-3 border border-amber-300 bg-amber-50 px-4 py-3 text-xs font-bold text-amber-900"
              >
                <span className="h-3 w-3 shrink-0 animate-spin rounded-full border-2 border-amber-900 border-t-transparent motion-reduce:animate-none" />
                Replacing the current report. The existing report stays available until the replacement succeeds.
              </div>
            ) : null}
            {/* Header / Actions Bar */}
            <div className="border border-black/10 bg-white p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div className="flex flex-col gap-1">
                <span className="text-[10px] font-black uppercase tracking-widest text-neutral-500">
                  Report ID: {activeReport.report_id}
                </span>
                <span className="text-xs text-neutral-800">
                  Linked to Case: <strong className="font-bold">{caseQuery.data.title}</strong>
                </span>
              </div>

              <div className="flex flex-wrap items-center gap-4">
                <div className="flex items-center gap-2">
                  <label htmlFor="review-status-select" className="text-xs font-bold text-neutral-700">
                    Review Status:
                  </label>
                  <select
                    id="review-status-select"
                    value={activeReport.review_status}
                    disabled={actionsLocked}
                    onChange={(e) => handleReviewStatusChange(e.target.value as ReviewStatus)}
                    className="border border-black/15 bg-white px-2.5 py-1.5 text-xs font-semibold text-black focus:outline-none focus:border-black"
                  >
                    <option value="draft">Draft</option>
                    <option value="ai_generated">AI Generated</option>
                    <option value="reviewed">Reviewed</option>
                    <option value="approved">Approved</option>
                  </select>
                </div>

                <button
                  onClick={() => handleDownloadReport("md")}
                  disabled={actionsLocked}
                  className="border border-black bg-white px-4 py-1.5 text-xs font-black text-black hover:bg-neutral-50 disabled:opacity-40 transition"
                >
                  {isExporting === "md" ? "Exporting..." : "Download Markdown"}
                </button>

                <button
                  onClick={() => handleDownloadReport("pdf")}
                  disabled={actionsLocked}
                  className="border border-black bg-white px-4 py-1.5 text-xs font-black text-black hover:bg-neutral-50 disabled:opacity-40 transition"
                >
                  {isExporting === "pdf" ? "Exporting..." : "Download PDF"}
                </button>

                <button
                  type="button"
                  onClick={() => setIsReplaceDialogOpen(true)}
                  disabled={actionsLocked}
                  className="border border-accent bg-accent px-4 py-1.5 text-xs font-black text-white transition-colors duration-150 hover:bg-red-800 disabled:opacity-40 motion-reduce:transition-none"
                >
                  Replace current report
                </button>
                {completedWorkflow ? (
                  <ReportCrudControls
                    workflow={completedWorkflow}
                    disabled={actionsLocked && !isCrudBusy}
                    onBusyChange={setIsCrudBusy}
                    onUpdated={updateWorkflow}
                    onDeleted={() => {
                      setWorkflow(null);
                      void readinessQuery.refetch();
                    }}
                  />
                ) : null}
              </div>
            </div>

            {/* Preview */}
            {completedWorkflow ? <ReportPreview workflow={completedWorkflow} /> : null}
          </div>
        ) : isGenerating && !completedWorkflow ? (
          <div
            role="status"
            aria-label="Generating report"
            aria-live="polite"
            className="flex flex-col items-center justify-center py-20"
          >
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-black border-t-transparent motion-reduce:animate-none" />
            <p className="mt-4 text-xs font-black uppercase tracking-widest text-neutral">
              Generating the CyberCase report from the current investigation analysis...
            </p>
          </div>
        ) : (
          <div className="mx-auto max-w-3xl border border-black/10 bg-white p-6 md:p-8 flex flex-col justify-between min-h-[380px]">
            <div className="space-y-6">
              <div className="flex items-center justify-between border-b border-black pb-4">
                <div>
                  <span className="text-[10px] font-black uppercase tracking-widest text-neutral-500">
                    Incident Report Workspace
                  </span>
                  <h3 className="text-xl font-black text-black mt-1">
                    Analysis current
                  </h3>
                </div>
                <span className="inline-flex border border-black bg-black px-2 py-1 text-[8px] font-black uppercase tracking-widest text-white">
                  Ready for report
                </span>
              </div>

              <div className="border border-neutral-100 bg-neutral-50 p-5 rounded-sm">
                <p className="text-xs font-semibold text-neutral-700 leading-relaxed">
                  A completed investigation analysis is available for case version {readiness.current_case_version}. Generate the preliminary report from that backend-selected analysis context.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                <div>
                  <label htmlFor="report-type-select" className="text-[10px] font-black uppercase tracking-wider text-neutral-500 block mb-1">
                    Report Type
                  </label>
                  <select
                    id="report-type-select"
                    value={reportType}
                    onChange={(e) => setReportType(e.target.value as ReportType)}
                    className="w-full border border-black/15 bg-white px-2.5 py-1.5 text-xs font-semibold text-black focus:outline-none focus:border-black"
                  >
                    <option value="overview">Case Overview</option>
                    <option value="subject">Evidence & Indicators</option>
                    <option value="timeline">Incident Timeline</option>
                    <option value="vulnerability">Exposure & Risk</option>
                  </select>
                </div>

                <div className="flex flex-col justify-end pb-1.5 pt-2">
                  <label htmlFor="legal-assessment-checkbox" className="flex items-center gap-2 cursor-pointer select-none">
                    <input
                      id="legal-assessment-checkbox"
                      type="checkbox"
                      checked={legal}
                      onChange={(e) => setLegal(e.target.checked)}
                      className="accent-black h-4 w-4"
                    />
                    <span className="text-xs font-semibold text-neutral-800">
                      Include Thai Legal Assessment
                    </span>
                  </label>
                </div>
              </div>
            </div>

            <div className="mt-8 pt-6 border-t border-black/5 flex flex-col sm:flex-row justify-end gap-4">
              <button
                onClick={() => handleGenerate(false)}
                disabled={actionsLocked}
                className="border border-black bg-black px-6 py-3 text-xs font-black text-white hover:bg-neutral-800 transition uppercase tracking-wider text-center"
              >
                Generate preliminary report
              </button>
            </div>
          </div>
        )}

        {isReplaceDialogOpen ? (
          <AccessibleDialog
            titleId="replace-current-report-title"
            onClose={() => setIsReplaceDialogOpen(false)}
          >
            <div className="border-b border-ink/10 bg-subdued/35 px-5 py-4 sm:px-6">
              <p className="mono-label text-accent">Confirm replacement</p>
              <h2 id="replace-current-report-title" className="mt-1.5 text-xl font-black text-ink">
                Replace current report?
              </h2>
            </div>
            <div className="px-5 py-5 sm:px-6">
              <p className="text-sm font-semibold leading-6 text-muted">
                A successful replacement will overwrite the current generated content and clear analyst edits and review status for this case.
              </p>
              <p className="mt-3 text-sm font-semibold leading-6 text-ink">
                If generation fails, the current report will remain unchanged.
              </p>
              <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                <button
                  type="button"
                  onClick={() => setIsReplaceDialogOpen(false)}
                  className="btn-secondary"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setIsReplaceDialogOpen(false);
                    void handleGenerate(true);
                  }}
                  className="bg-accent px-5 py-2.5 text-sm font-black text-white transition-colors duration-150 hover:bg-red-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent motion-reduce:transition-none"
                >
                  Replace report
                </button>
              </div>
            </div>
          </AccessibleDialog>
        ) : null}
      </div>
    </CaseStageShell>
  );
}
