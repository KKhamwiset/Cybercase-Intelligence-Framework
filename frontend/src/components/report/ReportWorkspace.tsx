"use client";

import Link from "next/link";
import { useEffect, useState, useMemo } from "react";
import CyberCaseShell from "@/components/CyberCaseShell";
import {
  listReports,
  getReport,
  updateReportReviewStatus,
  downloadReportExport,
} from "@/lib/api";
import type {
  ReportCompletedResponse,
  ReportWorkflowResponse,
  ReviewStatus,
  ReportRegistryItem,
} from "@/lib/api";
import ReportPreview from "@/components/report/ReportPreview";
import ReportCrudControls from "@/components/report/ReportCrudControls";
import { apiErrorMessage } from "@/lib/api-errors";

function formatReportDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not recorded";
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
}

export default function ReportWorkspace() {
  const [reportsList, setReportsList] = useState<ReportRegistryItem[]>([]);
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);
  const [detailedWorkflow, setDetailedWorkflow] = useState<ReportWorkflowResponse | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [isLoadingList, setIsLoadingList] = useState(true);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);
  const [isExporting, setIsExporting] = useState<"md" | "pdf" | null>(null);
  const [isCrudBusy, setIsCrudBusy] = useState(false);
  const [error, setError] = useState("");

  async function handleDownloadReport(format: "md" | "pdf") {
    if (!selectedReportId || !detailedWorkflow || detailedWorkflow.status !== "completed") return;
    setIsExporting(format);
    setError("");
    try {
      const blob = await downloadReportExport(selectedReportId, format);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `cybercase-report-${selectedReportId}.${format}`;
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
    async function loadList() {
      setIsLoadingList(true);
      setError("");
      try {
        const data = await listReports();
        setReportsList(data);
      } catch (err) {
        console.error("Failed to load reports registry:", err);
        setError(apiErrorMessage(err, "Could not load reports registry from backend database."));
      } finally {
        setIsLoadingList(false);
      }
    }
    loadList();
  }, []);

  async function handleSelectReport(reportId: string) {
    setSelectedReportId(reportId);
    setIsLoadingDetail(true);
    setDetailedWorkflow(null);
    setError("");
    try {
      const data = await getReport(reportId);
      setDetailedWorkflow(data);
    } catch (err) {
      console.error("Failed to load report details:", err);
      setError(apiErrorMessage(err, "Could not load full report details."));
    } finally {
      setIsLoadingDetail(false);
    }
  }

  async function handleReviewStatusChange(status: ReviewStatus) {
    if (!selectedReportId || !detailedWorkflow || detailedWorkflow.status !== "completed") return;

    setIsUpdatingStatus(true);
    setError("");
    try {
      const result = await updateReportReviewStatus(selectedReportId, status);
      setDetailedWorkflow(result);
      setReportsList((current) =>
        current.map((item) =>
          item.report_id === selectedReportId ? { ...item, review_status: status } : item,
        ),
      );
    } catch (err) {
      console.error("Failed to update review status:", err);
      setError(apiErrorMessage(err, "Could not update report review status."));
    } finally {
      setIsUpdatingStatus(false);
    }
  }

  const filteredReports = useMemo(() => {
    return reportsList.filter(
      (report) =>
        report.case_title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        report.case_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        report.report_id.toLowerCase().includes(searchQuery.toLowerCase()),
    );
  }, [reportsList, searchQuery]);

  const activeReport =
    detailedWorkflow?.status === "completed" && detailedWorkflow.report_id === selectedReportId
      ? detailedWorkflow.report
      : null;
  const completedWorkflow =
    detailedWorkflow?.status === "completed" && detailedWorkflow.report_id === selectedReportId
      ? detailedWorkflow
      : null;
  const actionsLocked = isUpdatingStatus || isExporting !== null || isCrudBusy;

  function handleReportUpdated(workflow: ReportCompletedResponse) {
    setDetailedWorkflow(workflow);
    setReportsList((current) =>
      current.map((item) =>
        item.report_id === workflow.report_id
          ? {
              ...item,
              executive_summary_preview: workflow.report.executive_case_summary.slice(0, 200),
              review_status: workflow.report.review_status,
              edit_metadata: workflow.edit_metadata,
              updated_at: workflow.edit_metadata.edited_at || item.updated_at,
            }
          : item,
      ),
    );
  }

  function handleReportDeleted() {
    if (!selectedReportId) return;
    setReportsList((current) => current.filter((item) => item.report_id !== selectedReportId));
    setSelectedReportId(null);
    setDetailedWorkflow(null);
  }

  return (
    <CyberCaseShell
      activeNav="Reports"
      eyebrow="Threat Intelligence & Documentation"
      title="Current Case Reports"
      subtitle="One current investigation report per case"
      actions={
        <Link
          href="/cases"
          className="border border-black/15 px-3 py-2 text-xs font-black transition hover:border-black hover:bg-black hover:text-white bg-white text-black"
        >
          Go to Cases
        </Link>
      }
    >
      <div className="flex h-full min-h-0 flex-col overflow-y-auto bg-[#FAF9F6] xl:flex-row xl:overflow-hidden">
        {/* Left Side: Current report list panel */}
        <aside className="flex max-h-80 shrink-0 flex-col overflow-y-auto border-b border-black/10 bg-[#F5F4F0] xl:h-full xl:max-h-none xl:w-[380px] xl:border-b-0 xl:border-r">
          <div className="border-b border-black/10 bg-surface p-4">
            <p className="mono-label text-accent">Current reports</p>
            <p className="mt-1 text-xs font-semibold leading-5 text-muted">
              Each case keeps one report. A successful replacement updates this entry.
            </p>
            <label htmlFor="search" className="sr-only">Search current reports</label>
            <input
              id="search"
              type="text"
              placeholder="Search current reports by case or ID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="mt-3 w-full border border-ink/15 bg-canvas px-3 py-2.5 text-xs text-ink transition-colors duration-150 placeholder:text-muted focus:border-accent focus:outline-none motion-reduce:transition-none"
            />
          </div>

          <div className="flex-1 overflow-y-auto">
            {isLoadingList ? (
              <div className="p-8 text-center text-xs font-black uppercase tracking-widest text-neutral">
                Loading Registry...
              </div>
            ) : filteredReports.length === 0 ? (
              <div className="p-8 text-center">
                <p className="text-sm font-black text-ink">No current reports found.</p>
                <p className="mt-2 text-xs font-semibold leading-5 text-muted">
                  Generate a report from an eligible case to add it here.
                </p>
              </div>
            ) : (
              <div className="divide-y divide-black/5">
                {filteredReports.map((item) => (
                  <button
                    key={item.report_id}
                    onClick={() => handleSelectReport(item.report_id)}
                    disabled={actionsLocked}
                    className={`w-full border-l-4 p-4 text-left transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-50 ${
                      selectedReportId === item.report_id
                        ? "border-black bg-white shadow-sm"
                        : "border-transparent hover:bg-white/50"
                    }`}
                  >
                    <div className="flex justify-between items-start gap-2">
                      <span className="text-[10px] font-black uppercase tracking-widest text-neutral-500">
                        {item.case_id}
                      </span>
                      <span className={`text-[8px] font-black uppercase tracking-widest px-1.5 py-0.5 border ${
                        item.severity === "high" || item.severity === "critical"
                          ? "border-red-500/30 bg-red-50 text-red-700"
                          : item.severity === "medium"
                          ? "border-amber-500/30 bg-amber-50 text-amber-700"
                          : "border-neutral-300 bg-neutral-50 text-neutral-700"
                      }`}>
                        {item.severity}
                      </span>
                    </div>

                    <h3 className="mt-1.5 text-sm font-black text-black leading-snug line-clamp-2">
                      {item.case_title}
                    </h3>

                    <p className="mt-2 text-xs text-neutral-600 line-clamp-2">
                      {item.executive_summary_preview}
                    </p>

                    <div className="mt-3.5 flex justify-between items-center gap-2 text-[9px] font-bold uppercase tracking-wider text-neutral-500">
                      <time dateTime={item.updated_at || item.created_at}>
                        Updated {formatReportDate(item.updated_at || item.created_at)}
                      </time>
                      <span className="border border-black/10 px-1 py-0.5 bg-neutral-100 text-[8px]">
                        {item.review_status}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </aside>

        {/* Right Side: Report Detail View */}
        <main className="flex flex-none flex-col overflow-visible p-4 sm:p-6 md:p-10 xl:min-h-0 xl:flex-1 xl:overflow-y-auto">
          {error && (
            <div role="alert" className="mb-6 border border-red-200 bg-red-50 p-4 text-xs font-semibold text-red-800">
              {error}
            </div>
          )}

          {isLoadingDetail ? (
            <div className="flex-1 flex flex-col items-center justify-center py-20">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-black border-t-transparent" />
              <p className="mt-4 text-xs font-black uppercase tracking-widest text-neutral">
                Retrieving Investigation Report...
              </p>
            </div>
          ) : detailedWorkflow?.status === "error" ||
            detailedWorkflow?.status === "context_expired" ? (
            <div className="flex-1 flex flex-col items-center justify-center border border-red-200 bg-white p-12 text-center">
              <h2 className="text-lg font-black text-red-800">
                Report details unavailable
              </h2>
              <p className="mt-3 max-w-md text-sm leading-6 text-red-700">
                {detailedWorkflow.message}
              </p>
            </div>
          ) : activeReport ? (
            <div className="flex-1 flex flex-col gap-6">
              {/* Action and Review Status Bar */}
              <div className="border border-black/10 bg-white p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div className="text-xs">
                  <span className="font-bold text-neutral-500">Persisted Report ID: </span>
                  <code className="bg-neutral-100 px-1 py-0.5 font-mono text-black font-semibold">
                    {activeReport.report_id}
                  </code>
                </div>

                <div className="flex flex-wrap items-center gap-3">
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

                  <div className="flex items-center gap-2">
                    <label htmlFor="review-status" className="text-xs font-bold text-neutral-700">
                      Review Status:
                    </label>
                    <select
                      id="review-status"
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
                  {completedWorkflow ? (
                    <ReportCrudControls
                      workflow={completedWorkflow}
                      disabled={actionsLocked && !isCrudBusy}
                      onBusyChange={setIsCrudBusy}
                      onUpdated={handleReportUpdated}
                      onDeleted={handleReportDeleted}
                    />
                  ) : null}
                </div>
              </div>

              {/* The Actual Report Preview */}
              {completedWorkflow ? <ReportPreview workflow={completedWorkflow} /> : null}
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center border-2 border-dashed border-black/10 rounded p-12 text-center bg-white/50">
              <svg
                className="h-12 w-12 text-neutral-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
              <h2 className="mt-4 text-lg font-black text-black">Current Case Reports</h2>
              <p className="mt-2 max-w-md text-xs leading-5 text-neutral-600">
                Select the current report for a case to examine its MITRE technique mappings, timeline events, evidence files, and legal assessments.
              </p>
            </div>
          )}
        </main>
      </div>
    </CyberCaseShell>
  );
}
