"use client";

import Link from "next/link";
import type { ChangeEvent, FormEvent } from "react";
import { useMemo, useState } from "react";
import CyberCaseShell from "@/components/CyberCaseShell";
import {
  generateReport,
  generateReportFile,
  resumeReport,
  updateReportReviewStatus,
} from "@/lib/api";
import type {
  CaseInformationCompleteness,
  CyberCaseReport,
  EvidenceStatus,
  ReportType,
  ReportWorkflowResponse,
  ReviewStatus,
} from "@/lib/api";

const SAMPLE_CASE =
  "On 2026-02-14 at 09:20, a finance employee reported a phishing email sent to a corporate banking account. The email linked to https://secure-bank-example.com/login and activity was observed from suspicious IP 203.0.113.45. The employee entered credentials on the website. An unauthorized transfer was then detected. Available evidence: email header, proxy log, and bank transaction log. Affected assets: corporate email account and online banking account. Impact: suspected financial fraud loss.";

const REPORT_TYPE_OPTIONS: { value: ReportType; label: string }[] = [
  { value: "overview", label: "Case Overview" },
  { value: "subject", label: "Evidence & Indicators" },
  { value: "timeline", label: "Incident Timeline" },
  { value: "vulnerability", label: "Exposure & Risk" },
];

const REVIEW_OPTIONS: ReviewStatus[] = [
  "draft",
  "ai_generated",
  "reviewed",
  "approved",
];

function statusClass(value: EvidenceStatus | ReviewStatus | string) {
  if (value === "confirmed" || value === "approved") {
    return "border-black bg-black text-white";
  }

  if (
    value === "reported" ||
    value === "reviewed" ||
    value === "ai_generated"
  ) {
    return "border-black/35 bg-white text-black";
  }

  if (value === "inferred") {
    return "border-black/15 bg-neutral-100 text-neutral-700";
  }

  return "border-black/15 bg-neutral-100 text-neutral";
}

function StatusBadge({
  value,
}: {
  value: EvidenceStatus | ReviewStatus | string;
}) {
  return (
    <span
      className={`inline-flex border px-2 py-1 text-[10px] font-black uppercase tracking-[0.08em] ${statusClass(
        value,
      )}`}
    >
      {value.replace("_", " ")}
    </span>
  );
}

function CompletenessMeter({
  completeness,
}: {
  completeness: CaseInformationCompleteness | null;
}) {
  if (!completeness) {
    return (
      <div className="border border-black/10 bg-white p-4">
        <p className="text-[10px] font-black uppercase tracking-[0.1em] text-neutral">
          Case Completeness
        </p>
        <p className="mt-2 text-sm leading-6 text-neutral">
          Completeness analysis will appear after report generation.
        </p>
      </div>
    );
  }

  return (
    <div className="border border-black/10 bg-white p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.1em] text-neutral">
            Case Completeness
          </p>
          <p className="mt-2 text-sm font-black text-black">
            {completeness.status}
          </p>
        </div>

        <span className="text-3xl font-black tracking-tight text-black">
          {completeness.percentage}%
        </span>
      </div>

      <div className="mt-4 h-2 overflow-hidden bg-neutral-200">
        <div
          className="h-full bg-black"
          style={{ width: `${completeness.percentage}%` }}
        />
      </div>

      {completeness.missing_fields.length ? (
        <p className="mt-3 text-xs leading-5 text-neutral">
          Missing: {completeness.missing_fields.join(", ")}
        </p>
      ) : (
        <p className="mt-3 text-xs leading-5 text-neutral">
          Required preliminary case details are available.
        </p>
      )}
    </div>
  );
}

function ReportPreview({
  report,
  completeness,
}: {
  report: CyberCaseReport | null;
  completeness: CaseInformationCompleteness | null;
}) {
  const title = report?.title || "CyberCase Preliminary Investigation Report";

  const summary =
    report?.executive_case_summary ||
    "Generate a report to synthesize submitted case facts, available evidence, MITRE ATT&CK mappings, investigation gaps, and recommended next actions.";

  const reportDate = report?.created_at?.slice(0, 10) || "Pending";

  const nextSteps = report?.investigation_next_steps.length
    ? report.investigation_next_steps.slice(0, 6)
    : [
        "Collect the initial incident narrative and affected asset details.",
        "Validate indicators against available logs and telemetry.",
        "Confirm the confidence of each MITRE ATT&CK mapping.",
      ];

  return (
    <article className="mx-auto min-h-[760px] max-w-5xl border border-black/15 bg-white p-6 md:p-10">
      <div className="flex flex-col gap-5 border-b border-black pb-6 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.14em] text-neutral">
            CyberCase Investigation Report
          </p>

          <h2 className="mt-3 max-w-3xl text-3xl font-black leading-tight tracking-tight md:text-4xl">
            {title}
          </h2>

          <div className="mt-5 flex flex-wrap gap-x-5 gap-y-2 text-[10px] font-black uppercase tracking-[0.08em] text-neutral">
            <span>Date: {reportDate}</span>
            <span>Generated by: CyberCase AI</span>
            <span>
              Classification:{" "}
              <span className="bg-black px-1.5 py-0.5 text-white">
                Internal
              </span>
            </span>
          </div>
        </div>

        <StatusBadge value={report?.review_status || "draft"} />
      </div>

      <section className="border-b border-black/20 py-7">
        <h3 className="text-lg font-black">1. Executive Summary</h3>
        <p className="mt-4 max-w-3xl text-sm leading-7 text-secondary">
          {summary}
        </p>
      </section>

      <section className="border-b border-black/20 py-7">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h3 className="text-lg font-black">2. Case Readiness</h3>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-neutral">
              Evaluation of whether enough verified information is available for
              an analyst-ready preliminary report.
            </p>
          </div>

          {completeness ? (
            <span className="text-3xl font-black">
              {completeness.percentage}%
            </span>
          ) : null}
        </div>

        {completeness ? (
          <>
            <div className="mt-5 h-2 overflow-hidden bg-neutral-200">
              <div
                className="h-full bg-black"
                style={{ width: `${completeness.percentage}%` }}
              />
            </div>

            <p className="mt-3 text-xs leading-5 text-neutral">
              {completeness.missing_fields.length
                ? `Missing fields: ${completeness.missing_fields.join(", ")}`
                : "No missing preliminary fields were identified."}
            </p>
          </>
        ) : (
          <p className="mt-5 text-sm text-neutral">
            Generate a report to evaluate case completeness.
          </p>
        )}
      </section>

      <section className="border-b border-black/20 py-7">
        <h3 className="text-lg font-black">3. Evidence & Indicators</h3>

        {report?.evidence_and_indicators_table.length ? (
          <div className="mt-4 overflow-x-auto border border-black/10">
            <table className="min-w-full text-left text-sm">
              <thead className="border-b border-black/10 bg-neutral-50 text-[10px] font-black uppercase tracking-[0.08em] text-neutral">
                <tr>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Observed Value</th>
                  <th className="px-4 py-3">Status</th>
                </tr>
              </thead>

              <tbody>
                {report.evidence_and_indicators_table
                  .slice(0, 8)
                  .map((indicator) => (
                    <tr
                      key={indicator.indicator_id}
                      className="border-b border-black/10 last:border-b-0"
                    >
                      <td className="px-4 py-3 text-xs font-black uppercase text-neutral">
                        {indicator.indicator_type}
                      </td>

                      <td className="max-w-md break-all px-4 py-3 font-semibold text-black">
                        {indicator.value}
                      </td>

                      <td className="px-4 py-3">
                        <StatusBadge value={indicator.status} />
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="mt-4 text-sm leading-7 text-neutral">
            No indicators have been extracted yet. Add case details or upload
            evidence, then generate the report.
          </p>
        )}
      </section>

      <section className="border-b border-black/20 py-7">
        <h3 className="text-lg font-black">4. MITRE ATT&CK Assessment</h3>

        {report?.mitre_attack_assessment.length ? (
          <div className="mt-4 divide-y divide-black/10 border border-black/10">
            {report.mitre_attack_assessment.slice(0, 6).map((mapping) => (
              <div
                key={`${mapping.technique_id}-${mapping.technique_name}`}
                className="grid gap-3 p-4 md:grid-cols-[170px_minmax(0,1fr)_auto]"
              >
                <div>
                  <p className="text-sm font-black">{mapping.technique_id}</p>
                  <p className="mt-1 text-xs font-semibold text-neutral">
                    {mapping.technique_name}
                  </p>
                </div>

                <p className="text-sm leading-6 text-secondary">
                  {mapping.justification}
                </p>

                <div>
                  <StatusBadge value={mapping.mapping_status} />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-4 text-sm leading-7 text-neutral">
            MITRE ATT&CK mappings will appear when the case context supports
            them.
          </p>
        )}
      </section>

      <section className="pt-7">
        <h3 className="text-lg font-black">5. Recommended Next Steps</h3>

        <ul className="mt-4 space-y-3 text-sm leading-6 text-secondary">
          {nextSteps.map((step) => (
            <li key={step} className="flex gap-3">
              <span className="mt-2 h-1.5 w-1.5 shrink-0 bg-black" />
              <span>{step}</span>
            </li>
          ))}
        </ul>
      </section>
    </article>
  );
}

export default function ReportPage() {
  const [query, setQuery] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [reportType, setReportType] = useState<ReportType>("overview");
  const [legal, setLegal] = useState(false);
  const [forceGenerate, setForceGenerate] = useState(false);
  const [workflow, setWorkflow] = useState<ReportWorkflowResponse | null>(null);
  const [followupAnswer, setFollowupAnswer] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);
  const [error, setError] = useState("");

  const report = workflow?.report ?? null;

  const completeness =
    workflow?.completeness ??
    report?.case_information_completeness ??
    report?.case_fact_pack?.completeness ??
    null;

  const canSubmit = useMemo(
    () => (query.trim().length > 0 || file !== null) && !isGenerating,
    [query, file, isGenerating],
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!canSubmit) {
      setError("Add case text or upload an evidence file before generating.");
      return;
    }

    setIsGenerating(true);
    setError("");
    setWorkflow(null);
    setFollowupAnswer("");

    try {
      const result = file
        ? await generateReportFile(
            file,
            query.trim(),
            reportType,
            legal,
            forceGenerate,
          )
        : await generateReport(query.trim(), reportType, legal, forceGenerate);

      setWorkflow(result);
    } catch (generationError) {
      console.error(generationError);
      setError(
        "Report generation failed. Check the backend and RAG service, then try again.",
      );
    } finally {
      setIsGenerating(false);
    }
  }

  async function handleResume() {
    if (!workflow?.session_id || !followupAnswer.trim()) {
      return;
    }

    setIsGenerating(true);
    setError("");

    try {
      const result = await resumeReport(
        workflow.session_id,
        followupAnswer.trim(),
      );

      setWorkflow(result);
      setFollowupAnswer("");
    } catch (resumeError) {
      console.error(resumeError);
      setError("Could not resume the CyberCase report session.");
    } finally {
      setIsGenerating(false);
    }
  }

  async function handleReviewStatus(status: ReviewStatus) {
    if (!report) {
      return;
    }

    setIsUpdatingStatus(true);
    setError("");

    try {
      const result = await updateReportReviewStatus(report.report_id, status);
      setWorkflow(result);
    } catch (statusError) {
      console.error(statusError);
      setError("Could not update the report review status.");
    } finally {
      setIsUpdatingStatus(false);
    }
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setFile(event.target.files?.[0] ?? null);
  }

  return (
    <CyberCaseShell
      activeNav="Reports"
      eyebrow="CyberCase Intelligence Framework"
      title="Report Builder"
      subtitle="Generate evidence-led cyber investigation reports"
      actions={
        <>
          <Link
            href="/chat"
            className="border border-black/15 px-3 py-2 text-xs font-black transition hover:border-black hover:bg-black hover:text-white"
          >
            Investigate
          </Link>
        </>
      }
    >
      <div className="flex h-full min-h-0 flex-col xl:flex-row">
        <aside className="shrink-0 overflow-y-auto border-b border-black/10 bg-[#f7f7f7] xl:w-[370px] xl:border-b-0 xl:border-r">
          <form onSubmit={handleSubmit} className="space-y-4 p-4">
            <section className="border border-black/10 bg-white p-4">
              <p className="text-[10px] font-black uppercase tracking-[0.1em] text-neutral">
                Report Input
              </p>

              <h2 className="mt-2 text-lg font-black">
                Build from case evidence.
              </h2>

              <p className="mt-2 text-xs leading-5 text-neutral">
                Add incident facts directly, attach an evidence file, or use
                both as report context.
              </p>

              <label
                htmlFor="case-detail"
                className="mt-5 block text-[10px] font-black uppercase tracking-[0.08em] text-neutral"
              >
                Incident details
              </label>

              <textarea
                id="case-detail"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Paste incident details, observed actions, evidence, indicators, logs, or analyst notes..."
                className="mt-2 min-h-36 w-full resize-y border border-black/15 bg-white p-3 text-sm leading-6 outline-none focus:border-black"
              />

              <label
                htmlFor="case-file"
                className="mt-4 block text-[10px] font-black uppercase tracking-[0.08em] text-neutral"
              >
                Evidence file
              </label>

              <input
                id="case-file"
                type="file"
                accept=".pdf,.png,.jpg,.jpeg"
                onChange={handleFileChange}
                className="mt-2 block w-full border border-black/15 bg-white p-2 text-xs file:mr-3 file:border-0 file:bg-black file:px-3 file:py-2 file:text-white"
              />

              {file ? (
                <div className="mt-2 flex items-center justify-between gap-3 border border-black/10 bg-neutral-50 px-3 py-2">
                  <span className="truncate text-xs font-semibold">
                    {file.name}
                  </span>

                  <button
                    type="button"
                    onClick={() => setFile(null)}
                    className="text-xs font-black hover:underline"
                  >
                    Clear
                  </button>
                </div>
              ) : null}
            </section>

            <section className="border border-black/10 bg-white p-4">
              <p className="text-[10px] font-black uppercase tracking-[0.1em] text-neutral">
                Report Configuration
              </p>

              <div className="mt-4 space-y-2">
                {REPORT_TYPE_OPTIONS.map((option) => (
                  <label
                    key={option.value}
                    className="flex cursor-pointer items-center gap-3 border border-transparent px-2 py-2 text-sm font-bold hover:bg-neutral-50"
                  >
                    <input
                      type="radio"
                      name="report-type"
                      checked={reportType === option.value}
                      onChange={() => setReportType(option.value)}
                      className="h-4 w-4 accent-black"
                    />
                    {option.label}
                  </label>
                ))}
              </div>

              <div className="mt-4 border-t border-black/10 pt-4">
                <label className="flex cursor-pointer items-start gap-3 text-sm font-bold">
                  <input
                    type="checkbox"
                    checked={legal}
                    onChange={(event) => setLegal(event.target.checked)}
                    className="mt-0.5 h-4 w-4 accent-black"
                  />

                  <span>
                    Include legal relevance
                    <span className="mt-1 block text-xs font-medium text-neutral">
                      Include legal-focused analysis where applicable.
                    </span>
                  </span>
                </label>

                <label className="mt-4 flex cursor-pointer items-start gap-3 text-sm font-bold">
                  <input
                    type="checkbox"
                    checked={forceGenerate}
                    onChange={(event) => setForceGenerate(event.target.checked)}
                    className="mt-0.5 h-4 w-4 accent-black"
                  />

                  <span>
                    Generate with missing facts
                    <span className="mt-1 block text-xs font-medium text-neutral">
                      Continue while clearly flagging incomplete information.
                    </span>
                  </span>
                </label>
              </div>
            </section>

            <div className="grid gap-2">
              <button
                type="submit"
                disabled={!canSubmit}
                className="bg-black px-4 py-3 text-sm font-black text-white transition hover:bg-neutral-800 disabled:cursor-not-allowed disabled:bg-neutral-300"
              >
                {isGenerating ? "Generating Report..." : "Generate Report"}
              </button>

              <button
                type="button"
                onClick={() => setQuery(SAMPLE_CASE)}
                disabled={isGenerating}
                className="border border-black/15 px-4 py-3 text-sm font-black transition hover:border-black hover:bg-white disabled:opacity-50"
              >
                Use Sample Case
              </button>
            </div>

            {error ? (
              <p className="border border-black/15 bg-white p-3 text-sm leading-6 text-secondary">
                {error}
              </p>
            ) : null}

            <CompletenessMeter completeness={completeness} />

            {workflow?.status === "followup" ? (
              <section className="border border-black/10 bg-white p-4">
                <p className="text-[10px] font-black uppercase tracking-[0.1em] text-neutral">
                  Follow-up Required
                </p>

                <h2 className="mt-2 text-lg font-black">
                  More case detail is needed.
                </h2>

                <p className="mt-3 text-sm leading-6 text-secondary">
                  {workflow.followup_question}
                </p>

                <textarea
                  value={followupAnswer}
                  onChange={(event) => setFollowupAnswer(event.target.value)}
                  className="mt-3 min-h-24 w-full resize-y border border-black/15 bg-white p-3 text-sm outline-none focus:border-black"
                  placeholder="Provide the missing fact, or write unknown."
                />

                <button
                  type="button"
                  onClick={handleResume}
                  disabled={!followupAnswer.trim() || isGenerating}
                  className="mt-3 bg-black px-4 py-2 text-sm font-black text-white disabled:cursor-not-allowed disabled:bg-neutral-300"
                >
                  Resume Report
                </button>
              </section>
            ) : null}
          </form>
        </aside>

        <section className="min-h-0 min-w-0 flex-1 overflow-y-auto bg-[#f5f5f5] p-4 md:p-6">
          <div className="mx-auto mb-4 flex max-w-5xl flex-col gap-3 border border-black/10 bg-white px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-[10px] font-black uppercase tracking-[0.1em] text-neutral">
                Live Report Preview
              </p>
              <p className="mt-1 text-xs font-semibold text-neutral">
                Review status and report content update after generation.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {report ? (
                REVIEW_OPTIONS.map((status) => (
                  <button
                    key={status}
                    type="button"
                    disabled={
                      isUpdatingStatus || report.review_status === status
                    }
                    onClick={() => handleReviewStatus(status)}
                    className={`border px-2 py-1 text-[10px] font-black uppercase transition disabled:cursor-not-allowed disabled:opacity-40 ${
                      report.review_status === status
                        ? "border-black bg-black text-white"
                        : "border-black/15 bg-white hover:border-black"
                    }`}
                  >
                    {status.replace("_", " ")}
                  </button>
                ))
              ) : (
                <StatusBadge value="draft" />
              )}
            </div>
          </div>

          <ReportPreview report={report} completeness={completeness} />
        </section>
      </div>
    </CyberCaseShell>
  );
}
