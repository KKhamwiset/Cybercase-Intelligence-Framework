"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import CaseRouteState from "@/components/cases/CaseRouteState";
import CaseStageShell from "@/components/cases/CaseStageShell";
import SaveStatus, { SaveState } from "@/components/cases/SaveStatus";
import { useUnsavedChangesWarning } from "@/components/cases/useUnsavedChangesWarning";
import { isNotFound, useCase, useUpdateCase } from "@/hooks/useCase";
import { useSessionDraft } from "@/hooks/useSessionDraft";
import type { CaseUpdateInput, StructuredCase } from "@/lib/cases";

type TextFieldConfig = {
  field: "incident_summary" | "analyst_notes";
  label: string;
  description: string;
  placeholder: string;
  autosave?: boolean;
};

type CaseTextWorkflowProps = {
  caseId: string | null;
  activeStage: string;
  heading: string;
  config: TextFieldConfig;
};

export default function CaseTextWorkflow({
  caseId,
  activeStage,
  heading,
  config,
}: CaseTextWorkflowProps) {
  const caseQuery = useCase(caseId);
  const mutation = useUpdateCase(caseId ?? "");
  const loadedCase = caseQuery.data;
  const initialText = loadedCase?.[config.field] ?? "";
  const draftKey = `cybercase:${caseId}:${config.field}`;
  const { draft, setDraft, clearDraft } = useSessionDraft(draftKey, initialText);
  const [saveState, setSaveState] = useState<SaveState>("saved");

  const hasUnsavedChanges = Boolean(loadedCase && draft !== loadedCase[config.field]);
  const displayedSaveState: SaveState =
    mutation.isPending || saveState === "saving"
      ? "saving"
      : saveState === "failed"
        ? "failed"
        : hasUnsavedChanges
          ? "unsaved"
          : "saved";
  useUnsavedChangesWarning(hasUnsavedChanges);

  const updatePayload = useMemo<CaseUpdateInput>(
    () => ({ [config.field]: draft }),
    [config.field, draft],
  );

  const saveDraft = useCallback(async () => {
    if (!caseId || !loadedCase) {
      return;
    }
    setSaveState("saving");
    try {
      const savedCase = await mutation.mutateAsync(updatePayload);
      clearDraft(savedCase[config.field] ?? draft);
      setSaveState("saved");
    } catch {
      setSaveState("failed");
    }
  }, [caseId, clearDraft, config.field, draft, loadedCase, mutation, updatePayload]);

  useEffect(() => {
    if (!config.autosave || !hasUnsavedChanges || !caseId || !loadedCase) {
      return;
    }
    const timeout = window.setTimeout(() => {
      void saveDraft();
    }, 900);

    return () => window.clearTimeout(timeout);
  }, [caseId, config.autosave, draft, hasUnsavedChanges, loadedCase, saveDraft]);

  if (!caseId) {
    return <CaseRouteState title={heading} message="No case ID was provided." />;
  }

  if (caseQuery.isLoading) {
    return <CaseRouteState title={heading} message={`Loading case ${caseId}.`} />;
  }

  if (isNotFound(caseQuery.error)) {
    return <CaseRouteState title={heading} message={`Case ${caseId} was not found.`} />;
  }

  if (caseQuery.error || !loadedCase) {
    return <CaseRouteState title={heading} message="Could not load this case." />;
  }

  return (
    <CaseStageShell
      activeStage={activeStage}
      caseData={loadedCase as StructuredCase}
      actions={<SaveStatus state={displayedSaveState} />}
    >
      <div className="mx-auto max-w-5xl p-5">
        <section className="border border-black/10 bg-white p-5">
          <p className="mono-label">{heading}</p>
          <h1 className="mt-2 text-2xl font-black">{config.label}</h1>
          <p className="mt-2 max-w-2xl text-sm font-semibold text-neutral">
            {config.description}
          </p>
          <textarea
            value={draft}
            onChange={(event) => {
              setDraft(event.target.value);
              if (saveState === "failed") {
                setSaveState("saved");
              }
            }}
            placeholder={config.placeholder}
            className="mt-5 min-h-64 w-full resize-y border border-black/15 bg-white p-4 text-sm font-semibold leading-6 outline-none focus:border-black"
          />
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={saveDraft}
              disabled={!hasUnsavedChanges || displayedSaveState === "saving"}
              className="btn-primary"
            >
              Save
            </button>
            {hasUnsavedChanges ? (
              <p className="text-xs font-semibold text-neutral">
                Unsaved draft is scoped to this browser tab and case.
              </p>
            ) : null}
          </div>
        </section>
      </div>
    </CaseStageShell>
  );
}
