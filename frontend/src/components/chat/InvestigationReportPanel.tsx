"use client";

import type { ReactNode } from "react";

import type {
  CaseInformationCompleteness,
  CyberCaseReport,
  ReportType,
  ReportWorkflowResponse,
} from "@/lib/api";

export const REPORT_TYPES: { value: ReportType; label: string }[] = [
  { value: "overview", label: "Overview" },
  { value: "subject", label: "Subject" },
  { value: "timeline", label: "Timeline" },
  { value: "vulnerability", label: "Vulnerability" },
];

export function reportCompleteness(
  reportWorkflow: ReportWorkflowResponse | null,
): CaseInformationCompleteness | null {
  const report =
    reportWorkflow?.status === "completed" ? (reportWorkflow.report ?? null) : null;
  if (report) {
    return (
      report.case_information_completeness ??
      report.case_fact_pack?.completeness ??
      null
    );
  }

  if (!reportWorkflow || reportWorkflow.status !== "followup") {
    return null;
  }

  return (
    reportWorkflow.completeness
  );
}

function statusClass(value: string): string {
  if (value === "confirmed" || value === "approved") {
    return "border-black bg-black text-white";
  }

  if (
    value === "reported" ||
    value === "reviewed" ||
    value === "ai_generated"
  ) {
    return "border-black/30 bg-white text-black";
  }

  if (value === "inferred") {
    return "border-black/20 bg-neutral-100 text-neutral-700";
  }

  return "border-black/10 bg-neutral-50 text-neutral-500";
}

function StatusBadge({ value }: { value: string }) {
  return (
    <span
      className={`inline-flex rounded-md border px-2 py-1 text-[11px] font-bold uppercase ${statusClass(
        value,
      )}`}
    >
      {value.replace("_", " ")}
    </span>
  );
}

function ReportSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="border-t border-black/10 px-4 py-4">
      <h3 className="mb-3 text-[11px] font-black uppercase text-neutral">
        {title}
      </h3>
      {children}
    </section>
  );
}

function EmptyReportState() {
  return (
    <div className="flex min-h-64 items-center justify-center px-6 text-center">
      <div>
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-lg border border-black bg-white text-xs font-black text-black">
          CC
        </div>
        <p className="mt-4 text-sm font-black text-black">
          No CyberCase report yet.
        </p>
        <p className="mt-1 text-xs leading-5 text-neutral">
          Build an investigation transcript, then generate a report from the
          collected evidence.
        </p>
      </div>
    </div>
  );
}

function ReportContent({ report }: { report: CyberCaseReport }) {
  return (
    <div>
      <section className="px-4 pb-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-[11px] font-black uppercase text-neutral">
              CyberCase {report.report_type} report
            </p>
            <h2 className="mt-2 text-lg font-black leading-snug text-black">
              {report.title}
            </h2>
          </div>

          <StatusBadge value={report.review_status} />
        </div>

        <p className="mt-4 text-sm leading-6 text-secondary">
          {report.executive_case_summary}
        </p>
      </section>

      <ReportSection title="Case Completeness">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-bold text-black">
              {report.case_information_completeness.status}
            </p>
            <p className="mt-1 text-xs leading-5 text-neutral">
              {report.case_information_completeness.missing_fields.length
                ? report.case_information_completeness.missing_fields.join(", ")
                : "All required preliminary fields are present."}
            </p>
          </div>

          <span className="text-3xl font-black text-black">
            {report.case_information_completeness.percentage}%
          </span>
        </div>

        <div className="mt-4 h-2 overflow-hidden rounded bg-neutral-200">
          <div
            className="h-full bg-black"
            style={{
              width: `${report.case_information_completeness.percentage}%`,
            }}
          />
        </div>
      </ReportSection>

      <ReportSection title="Evidence & Indicators">
        {report.evidence_and_indicators_table.length ? (
          <div className="space-y-3">
            {report.evidence_and_indicators_table
              .slice(0, 6)
              .map((indicator) => (
                <div
                  key={indicator.indicator_id}
                  className="border border-black/10 bg-white p-3"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[11px] font-black uppercase text-neutral">
                      {indicator.indicator_type}
                    </span>
                    <StatusBadge value={indicator.status} />
                  </div>

                  <p className="mt-2 break-all text-sm font-bold text-black">
                    {indicator.value}
                  </p>
                </div>
              ))}
          </div>
        ) : (
          <p className="text-sm text-neutral">No indicators listed.</p>
        )}
      </ReportSection>

      <ReportSection title="MITRE ATT&CK Mapping">
        {report.mitre_attack_assessment.length ? (
          <div className="space-y-3">
            {report.mitre_attack_assessment.slice(0, 5).map((mapping) => (
              <div
                key={`${mapping.technique_id}-${mapping.technique_name}`}
                className="border border-black/10 bg-white p-3"
              >
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <p className="text-sm font-black text-black">
                    {mapping.technique_id} {mapping.technique_name}
                  </p>
                  <StatusBadge value={mapping.mapping_status} />
                </div>

                <p className="mt-2 text-xs leading-5 text-neutral">
                  {mapping.justification}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-neutral">
            No supported MITRE ATT&CK mapping yet.
          </p>
        )}
      </ReportSection>

      <ReportSection title="Recommended Next Steps">
        {report.investigation_next_steps.length ? (
          <ul className="space-y-2 text-sm leading-6 text-secondary">
            {report.investigation_next_steps.slice(0, 6).map((step) => (
              <li key={step} className="flex gap-2">
                <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-black" />
                <span>{step}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-neutral">No next steps listed.</p>
        )}
      </ReportSection>
    </div>
  );
}

type InvestigationReportPanelProps = {
  isOpen: boolean;
  reportWorkflow: ReportWorkflowResponse | null;
  reportType: ReportType;
  reportButtonLabel: string;
  reportIsStale: boolean;
  retrievalRefreshed: boolean;
  isReportLoading: boolean;
  reportError: string;
  canGenerateReport: boolean;
  reportFollowupAnswer: string;
  onClose: () => void;
  onOpen: () => void;
  onReportTypeChange: (reportType: ReportType) => void;
  onGenerateReport: () => void;
  onReportFollowupAnswerChange: (answer: string) => void;
  onResumeReport: () => void;
};

export default function InvestigationReportPanel({
  isOpen,
  reportWorkflow,
  reportType,
  reportButtonLabel,
  reportIsStale,
  retrievalRefreshed,
  isReportLoading,
  reportError,
  canGenerateReport,
  reportFollowupAnswer,
  onClose,
  onOpen,
  onReportTypeChange,
  onGenerateReport,
  onReportFollowupAnswerChange,
  onResumeReport,
}: InvestigationReportPanelProps) {
  const report =
    reportWorkflow?.status === "completed" ? (reportWorkflow.report ?? null) : null;
  const completeness = reportCompleteness(reportWorkflow);

  if (!isOpen) {
    return (
      <aside className="hidden min-h-0 border-l border-black/10 bg-white xl:flex xl:flex-col xl:items-center xl:justify-center">
        <button
          type="button"
          onClick={onOpen}
          className="flex h-10 w-10 items-center justify-center rounded-full bg-black text-[10px] font-black text-white"
          aria-label="Open report panel"
        >
          CC
        </button>
      </aside>
    );
  }

  return (
    <aside className="flex min-h-0 flex-col border-t border-black/10 bg-[#fafafa] xl:border-l xl:border-t-0">
      <div className="shrink-0 border-b border-black/10 bg-white px-4 py-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="mono-label">CyberCase Output</p>
            <h2 className="mt-1 text-lg font-black text-black">
              Investigation Report
            </h2>
          </div>

          <div className="flex items-center gap-2">
            {completeness ? (
              <span className="rounded-md bg-black px-2.5 py-1.5 text-xs font-black text-white">
                {completeness.percentage}%
              </span>
            ) : null}

            <button
              type="button"
              onClick={onClose}
              className="border border-black/10 px-2 py-1 text-xs font-black hover:border-black"
              aria-label="Collapse report panel"
            >
              X
            </button>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-2">
          {REPORT_TYPES.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => onReportTypeChange(option.value)}
              aria-pressed={reportType === option.value}
              className={`rounded-md border px-3 py-2 text-left text-xs font-black transition-colors ${
                reportType === option.value
                  ? "border-black bg-black text-white"
                  : "border-black/10 bg-white text-neutral hover:border-black hover:text-black"
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>

        <button
          type="button"
          onClick={onGenerateReport}
          disabled={!canGenerateReport || isReportLoading}
          className="mt-3 w-full rounded-md bg-black px-4 py-3 text-sm font-black text-white transition-colors hover:bg-neutral-800 disabled:cursor-not-allowed disabled:bg-neutral-200 disabled:text-neutral"
        >
          {isReportLoading ? "Building report..." : reportButtonLabel}
        </button>

        {retrievalRefreshed ? (
          <p className="mt-2 inline-flex border border-black/10 bg-white px-2 py-1 text-[11px] font-black uppercase text-neutral">
            Retrieval refreshed
          </p>
        ) : null}

        {reportIsStale ? (
          <p className="mt-2 text-xs font-semibold text-neutral">
            Investigation context changed after the last report.
          </p>
        ) : null}

        {reportError ? (
          <p className="mt-3 border border-black/10 bg-white p-3 text-sm text-secondary">
            {reportError}
          </p>
        ) : null}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto py-4">
        {reportWorkflow?.status === "followup" ? (
          <section className="mx-4 border border-black/15 bg-white p-4">
            <p className="mono-label">Follow-up Required</p>

            <p className="mt-3 text-sm leading-6 text-secondary">
              {reportWorkflow.followup_question ||
                "Please provide more case detail."}
            </p>

            <textarea
              value={reportFollowupAnswer}
              onChange={(event) =>
                onReportFollowupAnswerChange(event.target.value)
              }
              className="mt-3 min-h-24 w-full resize-y border border-black/10 bg-white p-3 text-sm text-black outline-none placeholder:text-neutral focus:border-black"
              placeholder="Provide the missing investigation detail."
            />

            <button
              type="button"
              onClick={onResumeReport}
              disabled={!reportFollowupAnswer.trim() || isReportLoading}
              className="mt-3 rounded-md bg-black px-4 py-2 text-sm font-black text-white disabled:cursor-not-allowed disabled:bg-neutral-200 disabled:text-neutral"
            >
              Resume report
            </button>
          </section>
        ) : report ? (
          <ReportContent report={report} />
        ) : (
          <EmptyReportState />
        )}
      </div>
    </aside>
  );
}
