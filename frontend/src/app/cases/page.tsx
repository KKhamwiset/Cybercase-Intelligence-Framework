"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import CyberCaseShell from "@/components/CyberCaseShell";
import { useCases, useCreateCase } from "@/hooks/useCase";
import { apiErrorMessage } from "@/lib/api-errors";
import type { CaseSeverity, CaseStatus } from "@/lib/cases";

const STATUS_STYLES: Record<CaseStatus, string> = {
  new: "border-slate-300 bg-slate-50 text-slate-700",
  triage: "border-violet-300 bg-violet-50 text-violet-800",
  investigating: "border-amber-300 bg-amber-50 text-amber-800",
  contained: "border-sky-300 bg-sky-50 text-sky-800",
  resolved: "border-emerald-300 bg-emerald-50 text-emerald-800",
  unknown: "border-ink/15 bg-subdued/60 text-muted",
};

const SEVERITY_STYLES: Record<CaseSeverity, string> = {
  critical: "border-red-700 bg-red-700 text-white",
  high: "border-red-300 bg-red-50 text-red-800",
  medium: "border-amber-300 bg-amber-50 text-amber-800",
  low: "border-sky-300 bg-sky-50 text-sky-800",
  unknown: "border-ink/15 bg-subdued/60 text-muted",
};

function readableLabel(value: string) {
  return value.replaceAll("_", " ");
}

function formatUpdatedAt(value?: string | null) {
  if (!value) return "Not recorded";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not recorded";
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
}

function LoadingCases() {
  return (
    <div role="status" aria-label="Loading saved investigations" className="divide-y divide-ink/10">
      <span className="sr-only">Loading saved investigations.</span>
      {[0, 1, 2].map((row) => (
        <div
          key={row}
          className="grid animate-pulse gap-4 px-5 py-5 motion-reduce:animate-none lg:grid-cols-[minmax(0,1fr)_120px_110px_130px] lg:items-center"
        >
          <div>
            <div className="h-4 w-2/5 bg-subdued" />
            <div className="mt-2 h-3 w-1/4 bg-subdued/70" />
          </div>
          <div className="h-6 w-20 bg-subdued" />
          <div className="h-6 w-16 bg-subdued" />
          <div className="h-4 w-24 bg-subdued" />
        </div>
      ))}
    </div>
  );
}

export default function CasesPage() {
  const router = useRouter();
  const casesQuery = useCases();
  const createMutation = useCreateCase();
  const [title, setTitle] = useState("");
  const [error, setError] = useState("");

  const handleCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    const normalizedTitle = title.trim() || "Untitled case";
    if (normalizedTitle.length > 255) {
      setError("Case title must be 255 characters or fewer.");
      return;
    }
    try {
      const createdCase = await createMutation.mutateAsync({
        title: normalizedTitle,
      });
      router.push(`/cases/${createdCase.case_id}/intake`);
    } catch (caught) {
      setError(apiErrorMessage(caught, "Could not create the case."));
    }
  };

  return (
    <CyberCaseShell activeNav="Investigate" title="Investigations" subtitle="Saved case workspaces">
      <div className="h-full overflow-auto bg-canvas px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <div className="mx-auto max-w-7xl">
          <header className="mb-6 max-w-3xl">
            <p className="mono-label text-accent">Case operations</p>
            <h1 className="mt-2 text-3xl font-black tracking-[-0.03em] text-ink sm:text-4xl">
              Investigations
            </h1>
            <p className="mt-2 max-w-2xl text-sm font-semibold leading-6 text-muted">
              Open a saved case or create a focused workspace for a new incident.
            </p>
          </header>

          <div className="grid items-start gap-5 lg:grid-cols-[336px_minmax(0,1fr)]">
            <form
              onSubmit={handleCreate}
              className="border border-ink/10 bg-surface p-5 shadow-[0_1px_0_rgba(23,23,23,0.04)] sm:p-6"
            >
              <p className="mono-label">New case</p>
              <h2 className="mt-2 text-2xl font-black tracking-tight text-ink">
                Create investigation
              </h2>
              <p className="mt-2 text-sm font-medium leading-6 text-muted">
                Give the incident a concise, recognizable title. You can add evidence and details next.
              </p>

              <label
                htmlFor="case-title"
                className="mt-6 block text-[11px] font-black uppercase tracking-[0.12em] text-ink"
              >
                Case title
              </label>
              <input
                id="case-title"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                maxLength={255}
                disabled={createMutation.isPending}
                aria-describedby="case-title-help"
                className="mt-2 w-full border border-ink/20 bg-white px-3.5 py-3 text-sm font-semibold text-ink outline-none transition-colors duration-150 placeholder:text-muted/70 hover:border-ink/40 focus:border-accent disabled:cursor-not-allowed disabled:bg-subdued/50 motion-reduce:transition-none"
                placeholder="Phishing credential theft"
              />
              <div
                id="case-title-help"
                className="mt-2 flex items-center justify-between gap-3 text-[11px] font-semibold text-muted"
              >
                <span>Blank titles become “Untitled case”.</span>
                <span>{title.length}/255</span>
              </div>

              <button type="submit" disabled={createMutation.isPending} className="btn-primary mt-5 w-full">
                {createMutation.isPending ? "Creating case…" : "Create Case"}
              </button>
              {error ? (
                <p role="alert" className="mt-3 border-l-2 border-accent bg-red-50 px-3 py-2 text-sm font-semibold text-red-800">
                  {error}
                </p>
              ) : null}
            </form>

            <section aria-labelledby="saved-cases-heading" className="min-w-0 border border-ink/10 bg-surface shadow-[0_1px_0_rgba(23,23,23,0.04)]">
              <div className="flex flex-wrap items-end justify-between gap-3 border-b border-ink/10 px-5 py-5 sm:px-6">
                <div>
                  <p className="mono-label">Case registry</p>
                  <h2 id="saved-cases-heading" className="mt-1.5 text-2xl font-black tracking-tight text-ink">
                    Saved investigations
                  </h2>
                </div>
                {casesQuery.data ? (
                  <p className="border border-ink/10 bg-subdued/50 px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.12em] text-muted">
                    {casesQuery.data.length} {casesQuery.data.length === 1 ? "case" : "cases"}
                  </p>
                ) : null}
              </div>

              {casesQuery.isLoading ? <LoadingCases /> : null}

              {casesQuery.error ? (
                <div role="alert" className="m-5 border border-red-200 bg-red-50 p-5 sm:m-6">
                  <p className="text-sm font-black text-red-900">Could not load saved investigations.</p>
                  <p className="mt-1 text-xs font-semibold leading-5 text-red-800">
                    Check the connection and try the case registry again.
                  </p>
                  <button
                    type="button"
                    onClick={() => void casesQuery.refetch()}
                    className="mt-4 border border-red-800 bg-red-800 px-3 py-2 text-xs font-black text-white transition-colors duration-150 hover:bg-red-900 motion-reduce:transition-none"
                  >
                    Retry
                  </button>
                </div>
              ) : null}

              {!casesQuery.isLoading && !casesQuery.error && casesQuery.data?.length ? (
                <table className="block w-full lg:table" aria-label="Saved investigations">
                  <thead className="hidden border-b border-ink/10 bg-subdued/35 lg:table-header-group">
                    <tr>
                      {[
                        ["Case", "text-left"],
                        ["Status", "text-left"],
                        ["Severity", "text-left"],
                        ["Updated", "text-right"],
                      ].map(([label, align]) => (
                        <th
                          key={label}
                          scope="col"
                          className={`px-5 py-3 text-[10px] font-black uppercase tracking-[0.13em] text-muted ${align}`}
                        >
                          {label}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="block divide-y divide-ink/10 lg:table-row-group">
                    {casesQuery.data.map((caseItem) => (
                      <tr
                        key={caseItem.case_id}
                        className="group grid gap-4 p-5 transition-colors duration-150 hover:bg-subdued/35 motion-reduce:transition-none lg:table-row lg:p-0"
                      >
                        <td className="block lg:table-cell lg:px-5 lg:py-4 lg:align-middle">
                          <span className="mb-1 block text-[9px] font-black uppercase tracking-[0.12em] text-muted lg:hidden">
                            Case
                          </span>
                          <Link
                            href={`/cases/${caseItem.case_id}/intake`}
                            className="inline-block max-w-full text-sm font-black text-ink decoration-accent decoration-2 underline-offset-4 transition-colors duration-150 hover:text-accent hover:underline motion-reduce:transition-none"
                          >
                            <span className="line-clamp-2 break-words">{caseItem.title || "Untitled case"}</span>
                          </Link>
                          <p className="mt-1 break-all text-[10px] font-bold uppercase tracking-[0.08em] text-muted">
                            {caseItem.case_id}
                          </p>
                        </td>
                        <td className="block lg:table-cell lg:px-5 lg:py-4 lg:align-middle">
                          <span className="mb-1.5 block text-[9px] font-black uppercase tracking-[0.12em] text-muted lg:hidden">
                            Status
                          </span>
                          <span className={`inline-flex border px-2 py-1 text-[9px] font-black uppercase tracking-[0.1em] ${STATUS_STYLES[caseItem.status]}`}>
                            {readableLabel(caseItem.status)}
                          </span>
                        </td>
                        <td className="block lg:table-cell lg:px-5 lg:py-4 lg:align-middle">
                          <span className="mb-1.5 block text-[9px] font-black uppercase tracking-[0.12em] text-muted lg:hidden">
                            Severity
                          </span>
                          <span className={`inline-flex border px-2 py-1 text-[9px] font-black uppercase tracking-[0.1em] ${SEVERITY_STYLES[caseItem.severity]}`}>
                            {readableLabel(caseItem.severity)}
                          </span>
                        </td>
                        <td className="block lg:table-cell lg:px-5 lg:py-4 lg:text-right lg:align-middle">
                          <span className="mb-1 block text-[9px] font-black uppercase tracking-[0.12em] text-muted lg:hidden">
                            Updated
                          </span>
                          {caseItem.updated_at ? (
                            <time dateTime={caseItem.updated_at} className="text-xs font-bold text-muted">
                              {formatUpdatedAt(caseItem.updated_at)}
                            </time>
                          ) : (
                            <span className="text-xs font-bold text-muted">Not recorded</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : null}

              {!casesQuery.isLoading && !casesQuery.error && casesQuery.data?.length === 0 ? (
                <div className="px-6 py-12 text-center sm:py-16">
                  <span aria-hidden="true" className="mx-auto flex h-11 w-11 items-center justify-center border border-ink/15 bg-subdued/50 text-lg font-black text-accent">
                    +
                  </span>
                  <h3 className="mt-4 text-lg font-black text-ink">No investigations yet</h3>
                  <p className="mx-auto mt-2 max-w-sm text-sm font-medium leading-6 text-muted">
                    Create the first case to begin collecting incident details, evidence, and analysis.
                  </p>
                </div>
              ) : null}
            </section>
          </div>
        </div>
      </div>
    </CyberCaseShell>
  );
}
