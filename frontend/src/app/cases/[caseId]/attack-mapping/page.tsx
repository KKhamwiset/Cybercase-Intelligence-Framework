"use client";

import { useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import CaseRouteState from "@/components/cases/CaseRouteState";
import CaseStageShell from "@/components/cases/CaseStageShell";
import { analysisStatusLabel, OutputProvenance } from "@/components/cases/CaseOutputState";
import SaveStatus, { SaveState } from "@/components/cases/SaveStatus";
import { isNotFound, useCase, useCaseOutputs, useUpdateCase } from "@/hooks/useCase";
import { apiErrorMessage } from "@/lib/api-errors";
import { getRouteParam } from "@/lib/routeParams";
import { generateCaseReport } from "@/lib/api";
import { caseAnalysisKeys, getCaseReportReadiness } from "@/lib/case-chat";

const VALIDATION_NOTE = "ATT&CK mappings require analyst validation before confirmed reporting.";

export default function CaseAttackMappingPage() {
  const router = useRouter();
  const params = useParams();
  const caseId = getRouteParam(params.caseId);
  const caseQuery = useCase(caseId);
  const outputsQuery = useCaseOutputs(caseId);
  const mutation = useUpdateCase(caseId ?? "");
  const [saveState, setSaveState] = useState<SaveState>("saved");
  const [isGeneratingReport, setIsGeneratingReport] = useState(false);
  const [reportError, setReportError] = useState("");
  const [saveError, setSaveError] = useState("");
  const displayedSaveState: SaveState =
    mutation.isPending || saveState === "saving" ? "saving" : saveState;

  const mappingSummary = useMemo(() => {
    const mappings = outputsQuery.data?.outputs.attack_mappings.items ?? [];
    return {
      confirmed: mappings.filter((mapping) => mapping.status === "confirmed").length,
      candidate: mappings.filter((mapping) => mapping.status === "candidate").length,
      unknown: mappings.filter((mapping) => !["confirmed", "candidate"].includes(mapping.status)).length,
    };
  }, [outputsQuery.data?.outputs.attack_mappings.items]);

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

  if (!caseId) {
    return <CaseRouteState title="ATT&CK Mapping" message="No case ID was provided." />;
  }
  if (caseQuery.isLoading || readinessQuery.isLoading || outputsQuery.isLoading) {
    return <CaseRouteState title="ATT&CK Mapping" message={`Loading case ${caseId}.`} />;
  }
  if (
    isNotFound(caseQuery.error) ||
    isNotFound(readinessQuery.error) ||
    isNotFound(outputsQuery.error)
  ) {
    return <CaseRouteState title="ATT&CK Mapping" message={`Case ${caseId} was not found.`} />;
  }
  if (
    caseQuery.error ||
    readinessQuery.error ||
    outputsQuery.error ||
    !caseQuery.data ||
    !readinessQuery.data ||
    !outputsQuery.data
  ) {
    return <CaseRouteState title="ATT&CK Mapping" message="Could not load this case." />;
  }

  const hasValidationNote = caseQuery.data.analyst_notes.includes(VALIDATION_NOTE);
  const readiness = readinessQuery.data;
  const attackBucket = outputsQuery.data.outputs.attack_mappings;

  async function saveValidationNote() {
    if (hasValidationNote || mutation.isPending) return;
    const nextNotes = [caseQuery.data?.analyst_notes, VALIDATION_NOTE].filter(Boolean).join("\n\n");
    setSaveState("saving");
    setSaveError("");
    try {
      await mutation.mutateAsync({ analyst_notes: nextNotes });
      setSaveState("saved");
    } catch (caught) {
      setSaveState("failed");
      setSaveError(apiErrorMessage(caught, "Could not save the validation note."));
    }
  }

  async function generateReport() {
    if (!caseId || !readiness.report_eligible || isGeneratingReport) return;
    setIsGeneratingReport(true);
    setReportError("");
    try {
      const result = await generateCaseReport(caseId, "overview", false, false);
      if (result.status !== "completed" && result.status !== "followup") {
        setReportError(result.message);
        await readinessQuery.refetch();
        return;
      }
      router.push(`/cases/${caseId}/report`);
    } catch {
      setReportError("The report could not start. Refresh analysis from investigation chat and try again.");
    } finally {
      setIsGeneratingReport(false);
    }
  }

  return (
    <CaseStageShell
      activeStage="attack-mapping"
      caseData={caseQuery.data}
      actions={<SaveStatus state={displayedSaveState} />}
    >
      <div className="mx-auto max-w-5xl p-5">
        {reportError || saveError ? (
          <div role="alert" className="mb-4 border border-red-500/20 bg-red-50 p-4 text-sm font-semibold text-red-700">
            {reportError || saveError}
          </div>
        ) : null}

        <div role="status" aria-live="polite" className="mb-4 border border-black/15 bg-white p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="mono-label">
                {readiness.report_eligible
                  ? "Current investigation analysis available"
                  : "No current RAG analysis for this case version"}
              </p>
              <p className="mt-2 text-sm font-semibold text-neutral-900">
                {readiness.report_eligible
                  ? "A preliminary report can be generated from the current case-bound analysis."
                  : "Open investigation chat to analyze or refresh the saved case before reporting."}
              </p>
            </div>
            {readiness.report_eligible ? (
              <button
                type="button"
                onClick={() => void generateReport()}
                disabled={isGeneratingReport}
                className="btn-primary shrink-0 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {isGeneratingReport ? "Starting report..." : "Generate preliminary report"}
              </button>
            ) : (
              <button
                type="button"
                onClick={() => router.push(`/cases/${caseId}/chat`)}
                className="border border-black px-4 py-2 text-xs font-black uppercase tracking-wider hover:bg-black hover:text-white"
              >
                Open investigation chat
              </button>
            )}
          </div>
        </div>

        <section className="border border-black/10 bg-white p-5">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="mono-label">ATT&CK candidate mapping</p>
              <h1 className="mt-2 text-2xl font-black">
                {outputsQuery.data.analysis.status === "completed"
                  ? "Current analysis ATT&CK candidates"
                  : "Intake-derived ATT&CK candidates"}
              </h1>
            </div>
            <span className="border border-black/15 px-2 py-1 text-[10px] font-black uppercase tracking-wider">
              {analysisStatusLabel(outputsQuery.data.analysis.status)}
            </span>
          </div>
          <p className="mt-3 max-w-3xl text-sm font-semibold leading-6 text-neutral">
            Counts and items come from the backend lifecycle view. Intake/system-rule candidates and analysis-derived candidates remain unreviewed until an analyst accepts them.
          </p>

          <div className="mt-4 grid gap-3 md:grid-cols-3">
            <div className="border border-black/10 p-3"><p className="mono-label">Analyst-confirmed</p><p className="mt-1 text-2xl font-black">{mappingSummary.confirmed}</p></div>
            <div className="border border-black/10 p-3"><p className="mono-label">Candidate</p><p className="mt-1 text-2xl font-black">{mappingSummary.candidate}</p></div>
            <div className="border border-black/10 p-3"><p className="mono-label">Unknown</p><p className="mt-1 text-2xl font-black">{mappingSummary.unknown}</p></div>
          </div>

          <div className="mt-5 space-y-3">
            {attackBucket.current_count ? (
              attackBucket.items.map((mapping) => (
                <article key={mapping.item_id} className="border border-black/10 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h2 className="font-black">{mapping.item_id} {mapping.title}</h2>
                      <p className="mt-1 text-sm text-neutral">{mapping.description || "No rationale recorded."}</p>
                    </div>
                    <span className="border border-black/15 bg-neutral-50 px-2 py-1 text-[10px] font-black uppercase tracking-wider">{mapping.status}</span>
                  </div>
                  <OutputProvenance item={mapping} />
                  <p className="mt-3 text-xs font-black uppercase text-neutral">Candidate - analyst review required</p>
                </article>
              ))
            ) : (
              <p className="text-sm font-semibold text-neutral">
                {outputsQuery.data.analysis.status === "pending"
                  ? "Analysis is in progress. Previous mappings are not counted as current."
                  : "No current ATT&CK candidates are available."}
              </p>
            )}
          </div>

          {outputsQuery.data.historical_outputs.attack_mappings.historical_count ? (
            <p className="mt-3 text-xs font-semibold text-neutral">
              {outputsQuery.data.historical_outputs.attack_mappings.historical_count} historical mapping(s) are excluded from current counts.
            </p>
          ) : null}

          <button
            type="button"
            onClick={() => void saveValidationNote()}
            disabled={hasValidationNote || displayedSaveState === "saving"}
            className="btn-primary mt-5 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Save Validation Note
          </button>
        </section>
      </div>
    </CaseStageShell>
  );
}
