"use client";

import { useState } from "react";
import Link from "next/link";

import CaseOutputSummaryCards from "@/components/cases/CaseOutputState";
import CaseRouteState from "@/components/cases/CaseRouteState";
import CaseStageShell from "@/components/cases/CaseStageShell";
import SaveStatus, { SaveState } from "@/components/cases/SaveStatus";
import { useUnsavedChangesWarning } from "@/components/cases/useUnsavedChangesWarning";
import { isNotFound, useCase, useCaseOutputs, useUpdateCase } from "@/hooks/useCase";
import { apiErrorMessage } from "@/lib/api-errors";
import { useSessionDraft } from "@/hooks/useSessionDraft";

export default function CaseIntakeWorkspace({ caseId }: { caseId: string | null }) {
  const caseQuery = useCase(caseId);
  const outputsQuery = useCaseOutputs(caseId);
  const mutation = useUpdateCase(caseId ?? "");
  const loadedCase = caseQuery.data;
  const initialNarrative = loadedCase?.incident_summary ?? "";
  const { draft, setDraft, clearDraft } = useSessionDraft(
    `cybercase:${caseId}:incident_summary`,
    initialNarrative,
  );
  const [followUp, setFollowUp] = useState("");
  const [saveState, setSaveState] = useState<SaveState>("saved");
  const [saveError, setSaveError] = useState("");

  const hasSavedNarrative = Boolean(loadedCase?.incident_summary.trim());
  const hasUnsavedNarrative = Boolean(loadedCase && draft !== loadedCase.incident_summary);
  const hasUnsavedFollowUp = followUp.trim().length > 0;
  const displayedSaveState: SaveState =
    mutation.isPending || saveState === "saving"
      ? "saving"
      : saveState === "failed"
        ? "failed"
        : hasUnsavedNarrative || hasUnsavedFollowUp
          ? "unsaved"
          : "saved";
  useUnsavedChangesWarning(hasUnsavedNarrative || hasUnsavedFollowUp);

  if (!caseId) {
    return <CaseRouteState title="Case Intake" message="No case ID was provided." />;
  }

  if (caseQuery.isLoading || outputsQuery.isLoading) {
    return <CaseRouteState title="Case Intake" message={`Loading case ${caseId}.`} />;
  }

  if (isNotFound(caseQuery.error) || isNotFound(outputsQuery.error)) {
    return <CaseRouteState title="Case Intake" message={`Case ${caseId} was not found.`} />;
  }

  if (caseQuery.error || outputsQuery.error || !loadedCase || !outputsQuery.data) {
    return <CaseRouteState title="Case Intake" message="Could not load this case." />;
  }

  const saveNarrative = async () => {
    if (!draft.trim()) {
      return;
    }
    setSaveState("saving");
    setSaveError("");
    try {
      const savedCase = await mutation.mutateAsync({ incident_summary: draft });
      clearDraft(savedCase.incident_summary);
      setSaveState("saved");
    } catch (caught) {
      setSaveState("failed");
      setSaveError(apiErrorMessage(caught, "Could not save the intake narrative."));
    }
  };

  const saveFollowUp = async () => {
    const note = followUp.trim();
    if (!note) {
      return;
    }
    const nextNotes = [loadedCase.analyst_notes, note].filter(Boolean).join("\n\n");
    setSaveState("saving");
    setSaveError("");
    try {
      await mutation.mutateAsync({ analyst_notes: nextNotes });
      setFollowUp("");
      setSaveState("saved");
    } catch (caught) {
      setSaveState("failed");
      setSaveError(apiErrorMessage(caught, "Could not save the analyst note."));
    }
  };

  return (
    <CaseStageShell
      activeStage="intake"
      caseData={loadedCase}
      actions={<SaveStatus state={displayedSaveState} />}
    >
      <div className="mx-auto max-w-7xl p-5">
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_390px]">
          <section className="border border-black/10 bg-white">
            <div className="border-b border-black/10 p-5">
              <p className="mono-label">Case Intake</p>
              <h1 className="mt-2 text-2xl font-black">Incident narrative</h1>
              <p className="mt-2 max-w-2xl text-sm font-semibold text-neutral">
                Start with the analyst-provided incident description. Generated gaps and
                recommendations remain empty until a current analysis completes.
              </p>
            </div>

            <div className="p-5">
              {saveError ? (
                <p role="alert" className="mb-4 border border-red-500/30 bg-red-50 p-3 text-sm font-semibold text-red-800">
                  {saveError}
                </p>
              ) : null}
              <textarea
                value={draft}
                onChange={(event) => {
                  setDraft(event.target.value);
                  if (saveState === "failed") {
                    setSaveState("saved");
                  }
                }}
                placeholder="Describe what happened, who was affected, what evidence exists, and what response actions were taken."
                className="min-h-72 w-full resize-y border border-black/15 bg-white p-4 text-sm font-semibold leading-6 outline-none focus:border-black"
              />
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={saveNarrative}
                  disabled={
                    !hasUnsavedNarrative ||
                    !draft.trim() ||
                    displayedSaveState === "saving"
                  }
                  className="btn-primary"
                >
                  Save Intake
                </button>
                {hasUnsavedNarrative ? (
                  <p className="text-xs font-semibold text-neutral">
                    Draft is kept in this browser tab and scoped to {caseId}.
                  </p>
                ) : null}
              </div>
            </div>

            {hasSavedNarrative ? (
              <div className="space-y-4 border-t border-black/10 p-5">
                {loadedCase.analyst_notes ? (
                  <article className="border border-black/10 bg-neutral-50 p-4">
                    <p className="mono-label">Analyst Notes</p>
                    <p className="mt-2 whitespace-pre-wrap text-sm font-semibold leading-6 text-neutral-900">
                      {loadedCase.analyst_notes}
                    </p>
                  </article>
                ) : null}

                <div>
                  <label htmlFor="case-followup" className="mono-label">
                    Add follow-up note
                  </label>
                  <textarea
                    id="case-followup"
                    value={followUp}
                    onChange={(event) => {
                      setFollowUp(event.target.value);
                      if (saveState === "failed") {
                        setSaveState("saved");
                      }
                    }}
                    placeholder="Add clarification, analyst validation, or a new fact for later stages."
                    className="mt-2 min-h-28 w-full resize-y border border-black/15 bg-white p-3 text-sm font-semibold leading-6 outline-none focus:border-black"
                  />
                  <div className="mt-3 flex flex-wrap items-center gap-3">
                    <button
                      type="button"
                      onClick={saveFollowUp}
                      disabled={!followUp.trim() || displayedSaveState === "saving"}
                      className="btn-primary"
                    >
                      Save Note
                    </button>
                    {hasUnsavedFollowUp ? (
                      <p className="text-xs font-semibold text-neutral">
                        Save notes before moving into another stage.
                      </p>
                    ) : null}
                    <Link
                      href={`/cases/${loadedCase.case_id}/chat`}
                      className="border border-black px-4 py-2 text-xs font-black uppercase tracking-wider hover:bg-black hover:text-white"
                    >
                      Open investigation chat
                    </Link>
                  </div>
                </div>
              </div>
            ) : null}
          </section>

          <CaseOutputSummaryCards data={outputsQuery.data} />
        </div>
      </div>
    </CaseStageShell>
  );
}
