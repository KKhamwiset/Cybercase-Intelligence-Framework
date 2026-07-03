"use client";

import { useMemo, useState } from "react";
import Link from "next/link";

import CaseRouteState from "@/components/cases/CaseRouteState";
import CaseStageShell from "@/components/cases/CaseStageShell";
import SaveStatus, { SaveState } from "@/components/cases/SaveStatus";
import { useUnsavedChangesWarning } from "@/components/cases/useUnsavedChangesWarning";
import { isNotFound, useCase, useUpdateCase } from "@/hooks/useCase";
import { useSessionDraft } from "@/hooks/useSessionDraft";

type CaseOutputTile = {
  title: string;
  count: number;
  status: string;
  preview: string;
  href?: string;
};

export default function CaseIntakeWorkspace({ caseId }: { caseId: string | null }) {
  const caseQuery = useCase(caseId);
  const mutation = useUpdateCase(caseId ?? "");
  const loadedCase = caseQuery.data;
  const initialNarrative = loadedCase?.incident_summary ?? "";
  const { draft, setDraft, clearDraft } = useSessionDraft(
    `cybercase:${caseId}:incident_summary`,
    initialNarrative,
  );
  const [followUp, setFollowUp] = useState("");
  const [saveState, setSaveState] = useState<SaveState>("saved");

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

  const outputTiles = useMemo<CaseOutputTile[]>(() => {
    if (!loadedCase) {
      return [];
    }
    return [
      {
        title: "Evidence",
        count: loadedCase.evidence_items.length,
        href: `/cases/${loadedCase.case_id}/evidence`,
        status: loadedCase.evidence_items.length
          ? `${loadedCase.evidence_items.length} item(s) extracted`
          : "No evidence extracted yet",
        preview:
          loadedCase.evidence_items[0]?.title ||
          "Save Intake to generate evidence candidates.",
      },
      {
        title: "Gaps",
        count: loadedCase.gaps.length,
        href: `/cases/${loadedCase.case_id}/gap-analysis`,
        status: loadedCase.gaps.length
          ? `${loadedCase.gaps.length} gap(s) identified`
          : "No gaps identified yet",
        preview: loadedCase.gaps[0] || "Save Intake to identify missing facts.",
      },
      {
        title: "ATT&CK Mapping",
        count: loadedCase.attack_mappings.length,
        href: `/cases/${loadedCase.case_id}/attack-mapping`,
        status: loadedCase.attack_mappings.length
          ? `${loadedCase.attack_mappings.length} candidate mapping(s)`
          : "No mappings generated yet",
        preview: loadedCase.attack_mappings[0]
          ? `${loadedCase.attack_mappings[0].technique_id} ${loadedCase.attack_mappings[0].technique_name}`
          : "Save Intake to produce technique candidates.",
      },
      {
        title: "Recommendations",
        count: loadedCase.recommendations.length,
        status: loadedCase.recommendations.length
          ? `${loadedCase.recommendations.length} recommendation(s)`
          : "No recommendations yet",
        preview:
          loadedCase.recommendations[0]?.title ||
          "Recommendations appear after case outputs are generated.",
      },
    ];
  }, [loadedCase]);

  if (!caseId) {
    return <CaseRouteState title="Case Intake" message="No case ID was provided." />;
  }

  if (caseQuery.isLoading) {
    return <CaseRouteState title="Case Intake" message={`Loading case ${caseId}.`} />;
  }

  if (isNotFound(caseQuery.error)) {
    return <CaseRouteState title="Case Intake" message={`Case ${caseId} was not found.`} />;
  }

  if (caseQuery.error || !loadedCase) {
    return <CaseRouteState title="Case Intake" message="Could not load this case." />;
  }

  const saveNarrative = async () => {
    if (!draft.trim()) {
      return;
    }
    setSaveState("saving");
    try {
      const savedCase = await mutation.mutateAsync({ incident_summary: draft });
      clearDraft(savedCase.incident_summary);
      setSaveState("saved");
    } catch {
      setSaveState("failed");
    }
  };

  const saveFollowUp = async () => {
    const note = followUp.trim();
    if (!note) {
      return;
    }
    const nextNotes = [loadedCase.analyst_notes, note].filter(Boolean).join("\n\n");
    setSaveState("saving");
    try {
      await mutation.mutateAsync({ analyst_notes: nextNotes });
      setFollowUp("");
      setSaveState("saved");
    } catch {
      setSaveState("failed");
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
                Start with the incident description. Saving this narrative creates the
                downstream gap analysis, ATT&CK mapping, and report inputs for this case.
              </p>
            </div>

            <div className="p-5">
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
                  </div>
                </div>
              </div>
            ) : null}
          </section>

          <aside className="border border-black/10 bg-white p-5">
            <p className="mono-label">Generated Case Outputs</p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
              {outputTiles.map((tile) => {
                const content = (
                  <>
                    <div className="flex items-start justify-between gap-3">
                      <h2 className="text-lg font-black">{tile.title}</h2>
                      <span className="text-3xl font-black">{tile.count}</span>
                    </div>
                    <p className="mt-3 text-xs font-black uppercase text-neutral">
                      {tile.status}
                    </p>
                    <p className="mt-2 line-clamp-3 text-sm font-semibold leading-6 text-neutral-900">
                      {tile.preview}
                    </p>
                  </>
                );

                return tile.href ? (
                  <Link
                    key={tile.title}
                    href={tile.href}
                    className="block min-h-40 border border-black/10 bg-neutral-50 p-4 transition hover:border-black hover:bg-white"
                  >
                    {content}
                  </Link>
                ) : (
                  <article
                    key={tile.title}
                    className="min-h-40 border border-black/10 bg-neutral-50 p-4"
                  >
                    {content}
                  </article>
                );
              })}
            </div>
          </aside>
        </div>
      </div>
    </CaseStageShell>
  );
}
