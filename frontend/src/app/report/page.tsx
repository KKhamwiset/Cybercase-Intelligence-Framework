"use client";

import Link from "next/link";
import type { ChangeEvent, FormEvent, ReactNode } from "react";
import { useMemo, useState } from "react";
import {
  generateReport,
  generateReportFile,
  resumeReport,
  updateReportReviewStatus,
} from "@/lib/api";
import type {
  CaseFactPack,
  CaseInformationCompleteness,
  CyberCaseReport,
  EvidenceStatus,
  ReportType,
  ReportWorkflowResponse,
  ReviewStatus,
} from "@/lib/api";

const SAMPLE_CASE = "On 2026-02-14 at 09:20, the victim reported a phishing email to a corporate bank account. The email linked to https://secure-bank-example.com/login and a suspicious IP 203.0.113.45. After credentials were entered, an unauthorized transfer was observed. Evidence available: email header, proxy log, and bank transaction log. Affected asset: user email account and online banking account. Impact: suspected fraud loss.";

const REPORT_TYPE_OPTIONS: { value: ReportType; label: string }[] = [
  { value: "overview", label: "Overview" },
  { value: "subject", label: "Subject" },
  { value: "timeline", label: "Timeline" },
  { value: "vulnerability", label: "Vulnerability" },
];

const REVIEW_OPTIONS: ReviewStatus[] = ["draft", "ai_generated", "reviewed", "approved"];

function Panel({ title, aside, children }: { title: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-white/10 bg-zinc-950 p-5 shadow-sm">
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-100">{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  );
}

function EvidenceIdList({ ids }: { ids?: string[] | null }) {
  const safeIds = ids ?? [];
  if (!safeIds.length) {
    return <span className="text-zinc-500">unknown</span>;
  }
  return (
    <span className="inline-flex flex-wrap gap-1">
      {safeIds.map((id) => (
        <span key={id} className="rounded border border-cyan-400/30 bg-cyan-400/10 px-1.5 py-0.5 text-[11px] font-semibold text-cyan-200">
          {id}
        </span>
      ))}
    </span>
  );
}

function StatusBadge({ value }: { value: EvidenceStatus | ReviewStatus | string }) {
  const color =
    value === "confirmed" || value === "approved"
      ? "border-emerald-400/40 bg-emerald-400/10 text-emerald-200"
      : value === "reported" || value === "reviewed" || value === "ai_generated"
        ? "border-sky-400/40 bg-sky-400/10 text-sky-200"
        : value === "inferred"
          ? "border-amber-400/40 bg-amber-400/10 text-amber-200"
          : "border-zinc-500/40 bg-zinc-500/10 text-zinc-300";
  return <span className={"rounded border px-2 py-1 text-xs font-semibold " + color}>{value.replace("_", " ")}</span>;
}

function EmptyState({ label }: { label: string }) {
  return <p className="text-sm text-zinc-500">{label}</p>;
}

function CompletenessCard({ completeness }: { completeness: CaseInformationCompleteness | null }) {
  if (!completeness) {
    return null;
  }
  return (
    <div className="rounded-lg border border-white/10 bg-black p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-zinc-500">Case-information completeness</p>
          <p className="mt-1 text-sm font-semibold text-zinc-100">{completeness.status}</p>
        </div>
        <span className="text-2xl font-bold text-zinc-50">{completeness.percentage}%</span>
      </div>
      <div className="mt-4 h-2 overflow-hidden rounded bg-zinc-800">
        <div className="h-full bg-cyan-400" style={{ width: completeness.percentage + "%" }} />
      </div>
      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        {completeness.fields.map((field) => (
          <div key={field.field_id} className="flex items-center justify-between gap-2 rounded border border-white/10 bg-zinc-900 px-3 py-2">
            <span className="text-xs text-zinc-300">{field.label}</span>
            <span className={field.present ? "text-xs font-semibold text-emerald-300" : "text-xs font-semibold text-amber-300"}>
              {field.present ? "present" : "missing"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function EvidenceReview({ factPack }: { factPack: CaseFactPack | null }) {
  if (!factPack) {
    return <EmptyState label="No evidence registry available yet." />;
  }
  return (
    <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="text-xs uppercase text-zinc-500">
            <tr>
              <th className="border-b border-white/10 px-3 py-2">Fact</th>
              <th className="border-b border-white/10 px-3 py-2">Status</th>
              <th className="border-b border-white/10 px-3 py-2">Confidence</th>
              <th className="border-b border-white/10 px-3 py-2">Evidence</th>
            </tr>
          </thead>
          <tbody>
            {factPack.facts.map((fact) => (
              <tr key={fact.fact_id} className="align-top text-zinc-300">
                <td className="border-b border-white/5 px-3 py-3">{fact.statement}</td>
                <td className="border-b border-white/5 px-3 py-3"><StatusBadge value={fact.status} /></td>
                <td className="border-b border-white/5 px-3 py-3 capitalize">{fact.confidence}</td>
                <td className="border-b border-white/5 px-3 py-3"><EvidenceIdList ids={fact.evidence_ids} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="space-y-3">
        {factPack.evidence_registry.map((evidence) => (
          <div key={evidence.evidence_id} className="rounded border border-white/10 bg-zinc-900 p-3">
            <div className="flex items-center justify-between gap-2">
              <EvidenceIdList ids={[evidence.evidence_id]} />
              <span className="text-xs text-zinc-500">{evidence.source_type}</span>
            </div>
            <p className="mt-2 text-sm font-semibold text-zinc-100">{evidence.source_name}</p>
            {evidence.excerpt ? <p className="mt-2 line-clamp-4 text-xs leading-5 text-zinc-400">{evidence.excerpt}</p> : null}
            {evidence.page_number ? <p className="mt-2 text-xs text-zinc-500">page {evidence.page_number}</p> : null}
            {evidence.file_hash_sha256 ? <p className="mt-2 break-all text-xs text-zinc-500">SHA-256 {evidence.file_hash_sha256}</p> : null}
          </div>
        ))}
      </div>
    </div>
  );
}

function Timeline({ report }: { report: CyberCaseReport }) {
  if (!report.incident_timeline.length) {
    return <EmptyState label="Unknown / missing timeline information." />;
  }
  return (
    <ol className="space-y-3">
      {report.incident_timeline.map((event) => (
        <li key={event.event_id} className="rounded border border-white/10 bg-zinc-900 p-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <span className="text-sm font-semibold text-zinc-100">{event.timestamp || "Unknown time"}</span>
            <StatusBadge value={event.status} />
          </div>
          <p className="mt-2 text-sm leading-6 text-zinc-300">{event.event}</p>
          <div className="mt-2"><EvidenceIdList ids={event.evidence_ids} /></div>
        </li>
      ))}
    </ol>
  );
}

function MitreTable({ report }: { report: CyberCaseReport }) {
  if (!report.mitre_attack_assessment.length) {
    return <EmptyState label="No MITRE ATT&CK mapping is supported by retrieved MITRE data yet." />;
  }
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-left text-sm">
        <thead className="text-xs uppercase text-zinc-500">
          <tr>
            <th className="border-b border-white/10 px-3 py-2">Technique</th>
            <th className="border-b border-white/10 px-3 py-2">Status</th>
            <th className="border-b border-white/10 px-3 py-2">Justification</th>
            <th className="border-b border-white/10 px-3 py-2">Evidence</th>
          </tr>
        </thead>
        <tbody>
          {report.mitre_attack_assessment.map((mapping) => (
            <tr key={mapping.technique_id} className="align-top text-zinc-300">
              <td className="border-b border-white/5 px-3 py-3 font-semibold text-zinc-100">{mapping.technique_id} {mapping.technique_name}</td>
              <td className="border-b border-white/5 px-3 py-3"><StatusBadge value={mapping.mapping_status} /></td>
              <td className="border-b border-white/5 px-3 py-3">{mapping.justification}</td>
              <td className="border-b border-white/5 px-3 py-3"><EvidenceIdList ids={mapping.evidence_ids} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function BulletList({ items, emptyLabel }: { items?: string[] | null; emptyLabel: string }) {
  const safeItems = items ?? [];
  if (!safeItems.length) {
    return <EmptyState label={emptyLabel} />;
  }
  return (
    <ul className="space-y-2 text-sm text-zinc-300">
      {safeItems.map((item) => (
        <li key={item} className="flex gap-2">
          <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-300" />
          <span>{item}</span>
        </li>
      ))}
    </ul>
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
  const factPack = workflow?.case_fact_pack ?? report?.case_fact_pack ?? null;
  const completeness = workflow?.completeness ?? report?.case_information_completeness ?? factPack?.completeness ?? null;
  const canSubmit = useMemo(
    () => (query.trim().length > 0 || file !== null) && !isGenerating,
    [query, file, isGenerating],
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) {
      setError("Add case text or upload a file before generating a report.");
      return;
    }

    setIsGenerating(true);
    setError("");
    setWorkflow(null);
    setFollowupAnswer("");

    try {
      const result = file
        ? await generateReportFile(file, query.trim(), reportType, legal, forceGenerate)
        : await generateReport(query.trim(), reportType, legal, forceGenerate);
      setWorkflow(result);
    } catch (generationError) {
      console.error(generationError);
      setError("Report generation failed. Check the backend and RAG service, then try again.");
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
      const result = await resumeReport(workflow.session_id, followupAnswer.trim());
      setWorkflow(result);
      setFollowupAnswer("");
    } catch (resumeError) {
      console.error(resumeError);
      setError("Could not resume the report session.");
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
      setError("Could not update review status.");
    } finally {
      setIsUpdatingStatus(false);
    }
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setFile(event.target.files?.[0] ?? null);
  }

  return (
    <main className="min-h-screen bg-black text-zinc-100">
      <nav className="flex items-center justify-between border-b border-white/10 bg-zinc-950 px-6 py-5 lg:px-12">
        <Link href="/" className="flex items-center gap-3 text-xl font-bold tracking-tight text-white">
          <div className="flex h-8 w-8 items-center justify-center rounded bg-cyan-400 text-sm text-black">C</div>
          CyberCase Framework
        </Link>
        <div className="flex items-center gap-4 text-sm font-medium">
          <Link href="/chat" className="text-zinc-400 hover:text-white">RAG Search</Link>
          <Link href="/report" className="text-white">Report Generation</Link>
        </div>
      </nav>

      <section className="mx-auto grid w-full max-w-7xl gap-6 px-6 py-8 lg:grid-cols-[420px_1fr] lg:px-8">
        <div className="space-y-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-cyan-300">Preliminary report</p>
            <h1 className="mt-2 text-3xl font-bold tracking-tight text-white">Evidence-traceable case report</h1>
          </div>

          <form onSubmit={handleSubmit} className="rounded-lg border border-white/10 bg-zinc-950 p-5">
            <label htmlFor="case-detail" className="text-sm font-semibold text-zinc-100">Case details</label>
            <textarea
              id="case-detail"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Incident date/time, affected asset, observed behavior, logs/evidence, impact, indicators..."
              className="mt-2 min-h-52 w-full resize-y rounded-md border border-white/10 bg-black p-3 text-sm leading-6 text-zinc-100 outline-none transition placeholder:text-zinc-600 focus:border-cyan-300"
            />

            <div className="mt-4 grid gap-2 sm:grid-cols-2">
              {REPORT_TYPE_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  aria-pressed={reportType === option.value}
                  onClick={() => setReportType(option.value)}
                  className={
                    "rounded-md border px-3 py-2 text-left text-sm transition " +
                    (reportType === option.value
                      ? "border-cyan-300 bg-cyan-300/10 text-cyan-100"
                      : "border-white/10 bg-black text-zinc-400 hover:border-white/30")
                  }
                >
                  {option.label}
                </button>
              ))}
            </div>

            <div className="mt-4 space-y-3">
              <label className="flex items-center justify-between gap-3 rounded-md border border-white/10 bg-black px-3 py-2 text-sm text-zinc-300">
                <span>Include preliminary legal relevance</span>
                <input type="checkbox" checked={legal} onChange={(event) => setLegal(event.target.checked)} className="h-4 w-4 accent-cyan-300" />
              </label>
              <label className="flex items-center justify-between gap-3 rounded-md border border-white/10 bg-black px-3 py-2 text-sm text-zinc-300">
                <span>Generate even if incomplete</span>
                <input type="checkbox" checked={forceGenerate} onChange={(event) => setForceGenerate(event.target.checked)} className="h-4 w-4 accent-cyan-300" />
              </label>
            </div>

            <label htmlFor="case-file" className="mt-4 block text-sm font-semibold text-zinc-100">Evidence file</label>
            <input
              id="case-file"
              type="file"
              accept=".pdf,.png,.jpg,.jpeg"
              onChange={handleFileChange}
              className="mt-2 block w-full rounded-md border border-white/10 bg-black p-2 text-sm text-zinc-300 file:mr-3 file:rounded file:border-0 file:bg-zinc-800 file:px-3 file:py-2 file:text-zinc-100"
            />
            {file ? <p className="mt-2 text-xs text-zinc-500">Selected: {file.name}</p> : null}

            <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:justify-between">
              <button type="button" onClick={() => setQuery(SAMPLE_CASE)} className="rounded-md border border-white/10 px-4 py-2 text-sm font-semibold text-zinc-200 hover:border-white/30">
                Use sample case
              </button>
              <button type="submit" disabled={!canSubmit} className="rounded-md bg-cyan-300 px-5 py-2 text-sm font-bold text-black transition hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-50">
                {isGenerating ? "Generating..." : "Generate Report"}
              </button>
            </div>

            {error ? <p className="mt-4 rounded-md border border-red-400/30 bg-red-400/10 p-3 text-sm text-red-200">{error}</p> : null}
          </form>

          <CompletenessCard completeness={completeness} />

          {workflow?.status === "followup" ? (
            <Panel title="Follow-up required">
              <p className="text-sm leading-6 text-zinc-300">{workflow.followup_question}</p>
              <textarea
                value={followupAnswer}
                onChange={(event) => setFollowupAnswer(event.target.value)}
                className="mt-3 min-h-28 w-full rounded-md border border-white/10 bg-black p-3 text-sm text-zinc-100 outline-none focus:border-cyan-300"
                placeholder="Provide the missing fact, or write unknown."
              />
              <button type="button" onClick={handleResume} disabled={!followupAnswer.trim() || isGenerating} className="mt-3 rounded-md bg-cyan-300 px-4 py-2 text-sm font-bold text-black disabled:cursor-not-allowed disabled:opacity-50">
                Resume report
              </button>
            </Panel>
          ) : null}
        </div>

        <div className="space-y-5">
          {legal ? (
            <div className="rounded-lg border border-amber-300/30 bg-amber-300/10 p-4 text-sm leading-6 text-amber-100">
              This is preliminary investigation support only and is not a legal conclusion.
            </div>
          ) : null}

          {report ? (
            <>
              <Panel
                title={report.title}
                aside={<StatusBadge value={report.review_status} />}
              >
                <p className="text-sm leading-7 text-zinc-300">{report.executive_case_summary}</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {REVIEW_OPTIONS.map((status) => (
                    <button
                      key={status}
                      type="button"
                      disabled={isUpdatingStatus || report.review_status === status}
                      onClick={() => handleReviewStatus(status)}
                      className="rounded border border-white/10 px-3 py-1.5 text-xs font-semibold text-zinc-300 hover:border-cyan-300 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {status.replace("_", " ")}
                    </button>
                  ))}
                </div>
              </Panel>

              <Panel title="Evidence review">
                <EvidenceReview factPack={factPack} />
              </Panel>

              <Panel title="Evidence and indicators">
                {report.evidence_and_indicators_table.length ? (
                  <div className="grid gap-3 sm:grid-cols-2">
                    {report.evidence_and_indicators_table.map((indicator) => (
                      <div key={indicator.indicator_id} className="rounded border border-white/10 bg-zinc-900 p-3">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-xs uppercase text-zinc-500">{indicator.indicator_type}</span>
                          <StatusBadge value={indicator.status} />
                        </div>
                        <p className="mt-2 break-all text-sm font-semibold text-zinc-100">{indicator.value}</p>
                        <div className="mt-2"><EvidenceIdList ids={indicator.evidence_ids} /></div>
                      </div>
                    ))}
                  </div>
                ) : <EmptyState label="Unknown / missing indicator information." />}
              </Panel>

              <Panel title="Incident timeline">
                <Timeline report={report} />
              </Panel>

              <Panel title="MITRE ATT&CK assessment">
                <MitreTable report={report} />
              </Panel>

              <Panel title="Evidence still required / next steps">
                <div className="grid gap-4 md:grid-cols-2">
                  <BulletList items={report.evidence_still_required} emptyLabel="No required evidence listed." />
                  <BulletList items={report.investigation_next_steps} emptyLabel="No next steps listed." />
                </div>
              </Panel>

              {report.legal_assessments.length ? (
                <Panel title="Preliminary legal relevance">
                  <div className="space-y-3">
                    {report.legal_assessments.map((item) => (
                      <div key={item.provision_reference} className="rounded border border-amber-300/20 bg-amber-300/10 p-3 text-sm leading-6 text-amber-100">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-semibold">{item.provision_reference}</span>
                          <StatusBadge value={item.status} />
                        </div>
                        <p className="mt-2">{item.preliminary_relevance}</p>
                        <p className="mt-2 font-semibold">{item.disclaimer}</p>
                        <div className="mt-2"><EvidenceIdList ids={item.evidence_ids} /></div>
                      </div>
                    ))}
                  </div>
                </Panel>
              ) : null}

              <Panel title="Limitations and disclaimers">
                <BulletList items={report.limitations_and_disclaimers} emptyLabel="No limitations listed." />
              </Panel>
            </>
          ) : (
            <Panel title="Report workspace">
              <p className="text-sm leading-6 text-zinc-500">No report generated yet.</p>
            </Panel>
          )}
        </div>
      </section>
    </main>
  );
}
