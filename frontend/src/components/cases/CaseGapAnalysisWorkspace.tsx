"use client";

import { useState } from "react";

import CaseRouteState from "@/components/cases/CaseRouteState";
import CaseStageShell from "@/components/cases/CaseStageShell";
import { analysisStatusLabel, OutputProvenance } from "@/components/cases/CaseOutputState";
import SaveStatus, { SaveState } from "@/components/cases/SaveStatus";
import { useUnsavedChangesWarning } from "@/components/cases/useUnsavedChangesWarning";
import { isNotFound, useCase, useCaseOutputs, useUpdateCase } from "@/hooks/useCase";
import { apiErrorMessage } from "@/lib/api-errors";
import { useSessionDraft } from "@/hooks/useSessionDraft";

export default function CaseGapAnalysisWorkspace({ caseId }: { caseId: string | null }) {
  const caseQuery = useCase(caseId);
  const outputsQuery = useCaseOutputs(caseId);
  const mutation = useUpdateCase(caseId ?? "");
  const loadedCase = caseQuery.data;
  const initialNotes = loadedCase?.analyst_notes ?? "";
  const { draft, setDraft, clearDraft } = useSessionDraft(
    `cybercase:${caseId}:analyst_notes`,
    initialNotes,
  );
  const [saveState, setSaveState] = useState<SaveState>("saved");
  const [saveError, setSaveError] = useState("");

  const hasUnsavedChanges = Boolean(loadedCase && draft !== loadedCase.analyst_notes);
  const displayedSaveState: SaveState =
    mutation.isPending || saveState === "saving"
      ? "saving"
      : saveState === "failed"
        ? "failed"
        : hasUnsavedChanges
          ? "unsaved"
          : "saved";
  useUnsavedChangesWarning(hasUnsavedChanges);

  if (!caseId) {
    return <CaseRouteState title="Gap Analysis" message="No case ID was provided." />;
  }

  if (caseQuery.isLoading || outputsQuery.isLoading) {
    return <CaseRouteState title="Gap Analysis" message={`Loading case ${caseId}.`} />;
  }

  if (isNotFound(caseQuery.error) || isNotFound(outputsQuery.error)) {
    return <CaseRouteState title="Gap Analysis" message={`Case ${caseId} was not found.`} />;
  }

  if (caseQuery.error || outputsQuery.error || !loadedCase || !outputsQuery.data) {
    return <CaseRouteState title="Gap Analysis" message="Could not load this case." />;
  }

  const saveNotes = async () => {
    if (!hasUnsavedChanges || mutation.isPending) {
      return;
    }
    setSaveState("saving");
    setSaveError("");
    try {
      const savedCase = await mutation.mutateAsync({ analyst_notes: draft });
      clearDraft(savedCase.analyst_notes);
      setSaveState("saved");
    } catch (caught) {
      setSaveState("failed");
      setSaveError(apiErrorMessage(caught, "Could not save analyst notes."));
    }
  };

  return (
    <CaseStageShell
      activeStage="gap-analysis"
      caseData={loadedCase}
      actions={<SaveStatus state={displayedSaveState} />}
    >
      <div className="mx-auto max-w-5xl p-5">
        <section className="border border-black/10 bg-white p-5">
          <p className="mono-label">Gap Analysis</p>
          <div className="flex flex-wrap items-end justify-between gap-3">
            <h1 className="mt-2 text-2xl font-black">Generated investigation gaps</h1>
            <span className="border border-black/15 px-2 py-1 text-[10px] font-black uppercase tracking-wider">
              {analysisStatusLabel(outputsQuery.data.analysis.status)}
            </span>
          </div>

          <div className="mt-5 grid gap-3">
            {outputsQuery.data.outputs.gaps.current_count ? (
              outputsQuery.data.outputs.gaps.items.map((gap) => (
                <article key={gap.item_id} className="border border-black/10 bg-neutral-50 p-4">
                  <h2 className="text-sm font-black leading-6 text-neutral-900">{gap.title}</h2>
                  {gap.description ? (
                    <p className="mt-2 text-sm font-semibold leading-6 text-neutral-800">{gap.description}</p>
                  ) : null}
                  <OutputProvenance item={gap} />
                </article>
              ))
            ) : (
              <p className="border border-black/10 bg-neutral-50 p-4 text-sm font-semibold text-neutral">
                {outputsQuery.data.analysis.status === "pending"
                  ? "Analysis is in progress. Current gaps will appear when it completes."
                  : outputsQuery.data.analysis.status === "completed"
                    ? "No evidence gaps were returned by the current completed analysis."
                    : "Run analysis to identify evidence gaps."}
              </p>
            )}
          </div>
          {outputsQuery.data.historical_outputs.gaps.historical_count ? (
            <p className="mt-3 text-xs font-semibold text-neutral">
              {outputsQuery.data.historical_outputs.gaps.historical_count} historical gap(s) are retained for audit and excluded from current results.
            </p>
          ) : null}

          <div className="mt-6 border-t border-black/10 pt-5">
            {saveError ? (
              <p role="alert" className="mb-4 border border-red-500/30 bg-red-50 p-3 text-sm font-semibold text-red-800">
                {saveError}
              </p>
            ) : null}
            <label htmlFor="gap-notes" className="mono-label">
              Analyst notes
            </label>
            <textarea
              id="gap-notes"
              value={draft}
              onChange={(event) => {
                setDraft(event.target.value);
                if (saveState === "failed") {
                  setSaveState("saved");
                }
              }}
              placeholder="Record analyst answers, validation concerns, and missing facts resolved during review."
              className="mt-3 min-h-48 w-full resize-y border border-black/15 bg-white p-4 text-sm font-semibold leading-6 outline-none focus:border-black"
            />
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={saveNotes}
                disabled={!hasUnsavedChanges || displayedSaveState === "saving"}
                className="btn-primary"
              >
                Save Notes
              </button>
              {hasUnsavedChanges ? (
                <p className="text-xs font-semibold text-neutral">
                  Draft notes are scoped to this browser tab and case.
                </p>
              ) : null}
            </div>
          </div>
        </section>
      </div>
    </CaseStageShell>
  );
}
