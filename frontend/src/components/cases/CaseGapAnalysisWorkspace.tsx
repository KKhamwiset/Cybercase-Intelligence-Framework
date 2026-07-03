"use client";

import { useState } from "react";

import CaseRouteState from "@/components/cases/CaseRouteState";
import CaseStageShell from "@/components/cases/CaseStageShell";
import SaveStatus, { SaveState } from "@/components/cases/SaveStatus";
import { useUnsavedChangesWarning } from "@/components/cases/useUnsavedChangesWarning";
import { isNotFound, useCase, useUpdateCase } from "@/hooks/useCase";
import { useSessionDraft } from "@/hooks/useSessionDraft";

export default function CaseGapAnalysisWorkspace({ caseId }: { caseId: string | null }) {
  const caseQuery = useCase(caseId);
  const mutation = useUpdateCase(caseId ?? "");
  const loadedCase = caseQuery.data;
  const initialNotes = loadedCase?.analyst_notes ?? "";
  const { draft, setDraft, clearDraft } = useSessionDraft(
    `cybercase:${caseId}:analyst_notes`,
    initialNotes,
  );
  const [saveState, setSaveState] = useState<SaveState>("saved");

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

  if (caseQuery.isLoading) {
    return <CaseRouteState title="Gap Analysis" message={`Loading case ${caseId}.`} />;
  }

  if (isNotFound(caseQuery.error)) {
    return <CaseRouteState title="Gap Analysis" message={`Case ${caseId} was not found.`} />;
  }

  if (caseQuery.error || !loadedCase) {
    return <CaseRouteState title="Gap Analysis" message="Could not load this case." />;
  }

  const saveNotes = async () => {
    if (!hasUnsavedChanges || mutation.isPending) {
      return;
    }
    setSaveState("saving");
    try {
      const savedCase = await mutation.mutateAsync({ analyst_notes: draft });
      clearDraft(savedCase.analyst_notes);
      setSaveState("saved");
    } catch {
      setSaveState("failed");
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
          <h1 className="mt-2 text-2xl font-black">Generated investigation gaps</h1>

          <div className="mt-5 grid gap-3">
            {loadedCase.gaps.length ? (
              loadedCase.gaps.map((gap) => (
                <div key={gap} className="border border-black/10 bg-neutral-50 p-4">
                  <p className="text-sm font-semibold leading-6 text-neutral-900">{gap}</p>
                </div>
              ))
            ) : (
              <p className="border border-black/10 bg-neutral-50 p-4 text-sm font-semibold text-neutral">
                No generated gaps are available yet. Save the intake narrative first.
              </p>
            )}
          </div>

          <div className="mt-6 border-t border-black/10 pt-5">
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
