"use client";

import { useRef, useState } from "react";

import AccessibleDialog from "@/components/AccessibleDialog";
import { apiErrorMessage } from "@/lib/api-errors";
import {
  deleteReport,
  updateReport,
  type ReportCompletedResponse,
  type ReportUpdateInput,
} from "@/lib/api";

type ReportDraft = {
  title: string;
  executive_case_summary: string;
  evidence_still_required: string;
  investigation_next_steps: string;
  limitations_and_disclaimers: string;
};

function listToText(items: string[]): string {
  return items.join("\n");
}

function textToList(value: string): string[] {
  return value.split("\n").map((item) => item.trim()).filter(Boolean);
}

function draftFromWorkflow(workflow: ReportCompletedResponse): ReportDraft {
  return {
    title: workflow.report.title,
    executive_case_summary: workflow.report.executive_case_summary,
    evidence_still_required: listToText(workflow.report.evidence_still_required),
    investigation_next_steps: listToText(workflow.report.investigation_next_steps),
    limitations_and_disclaimers: listToText(workflow.report.limitations_and_disclaimers),
  };
}

function sameList(left: string[], right: string[]): boolean {
  return left.length === right.length && left.every((item, index) => item === right[index]);
}

export default function ReportCrudControls({
  workflow,
  disabled = false,
  onBusyChange,
  onUpdated,
  onDeleted,
}: {
  workflow: ReportCompletedResponse;
  disabled?: boolean;
  onBusyChange?: (busy: boolean) => void;
  onUpdated: (workflow: ReportCompletedResponse) => void;
  onDeleted: () => void;
}) {
  const firstFieldRef = useRef<HTMLInputElement>(null);
  const [mode, setMode] = useState<"closed" | "edit" | "delete">("closed");
  const [draft, setDraft] = useState<ReportDraft>(() => draftFromWorkflow(workflow));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const locked = disabled || busy;

  function setActionBusy(value: boolean) {
    setBusy(value);
    onBusyChange?.(value);
  }

  function buildChanges(): ReportUpdateInput {
    const report = workflow.report;
    const changes: ReportUpdateInput = {};
    const title = draft.title.trim();
    const summary = draft.executive_case_summary.trim();
    const evidence = textToList(draft.evidence_still_required);
    const nextSteps = textToList(draft.investigation_next_steps);
    const limitations = textToList(draft.limitations_and_disclaimers);
    if (title !== report.title) changes.title = title;
    if (summary !== report.executive_case_summary) changes.executive_case_summary = summary;
    if (!sameList(evidence, report.evidence_still_required)) changes.evidence_still_required = evidence;
    if (!sameList(nextSteps, report.investigation_next_steps)) changes.investigation_next_steps = nextSteps;
    if (!sameList(limitations, report.limitations_and_disclaimers)) {
      changes.limitations_and_disclaimers = limitations;
    }
    return changes;
  }

  const changes = buildChanges();
  const hasChanges = Object.keys(changes).length > 0;

  function closeDialog() {
    if (busy) return;
    setMode("closed");
    setDraft(draftFromWorkflow(workflow));
    setError("");
  }

  async function saveReport() {
    if (!draft.title.trim() || !draft.executive_case_summary.trim()) {
      setError("Title and executive case summary are required.");
      return;
    }
    if (!hasChanges) return;
    setError("");
    setActionBusy(true);
    try {
      const result = await updateReport(workflow.report_id, changes);
      if (result.status !== "completed") {
        throw new Error("The backend did not return a completed report.");
      }
      onUpdated(result);
      setMode("closed");
    } catch (caught) {
      setError(apiErrorMessage(caught, "Could not save report edits."));
    } finally {
      setActionBusy(false);
    }
  }

  async function confirmDelete() {
    setError("");
    setActionBusy(true);
    try {
      await deleteReport(workflow.report_id);
      setMode("closed");
      onDeleted();
    } catch (caught) {
      setError(apiErrorMessage(caught, "Could not delete this report."));
    } finally {
      setActionBusy(false);
    }
  }

  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        <span className="border border-black/15 px-2 py-1 text-[10px] font-black uppercase tracking-wider">
          {workflow.edit_metadata.origin === "manual_edit" ? "Analyst edited" : "Generated"}
        </span>
        <button
          type="button"
          disabled={locked}
          onClick={() => {
            setDraft(draftFromWorkflow(workflow));
            setError("");
            setMode("edit");
          }}
          className="border border-black bg-white px-3 py-2 text-xs font-black uppercase tracking-wider hover:bg-neutral-100 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Edit report
        </button>
        <button
          type="button"
          disabled={locked}
          onClick={() => {
            setError("");
            setMode("delete");
          }}
          className="border border-black bg-black px-3 py-2 text-xs font-black uppercase tracking-wider text-white hover:bg-neutral-800 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Delete report
        </button>
      </div>

      {mode !== "closed" ? (
        <AccessibleDialog
          titleId={mode === "edit" ? "report-edit-title" : "report-delete-title"}
          onClose={closeDialog}
          initialFocusRef={mode === "edit" ? firstFieldRef : undefined}
        >
          {mode === "edit" ? (
            <>
              <div className="border-b border-black/10 p-5">
                <p className="mono-label">Analyst narrative overlay</p>
                <h2 id="report-edit-title" className="mt-2 text-2xl font-black">Edit report</h2>
                <p className="mt-2 text-sm font-semibold text-neutral">
                  Generated evidence, mappings, identifiers, and fact-pack data remain immutable.
                </p>
              </div>
              <div className="max-h-[65vh] space-y-4 overflow-y-auto p-5">
                <label className="block text-xs font-black uppercase tracking-wider">
                  Title
                  <input
                    ref={firstFieldRef}
                    value={draft.title}
                    maxLength={255}
                    onChange={(event) => setDraft((current) => ({ ...current, title: event.target.value }))}
                    className="mt-2 w-full border border-black/20 p-3 text-sm font-semibold normal-case tracking-normal outline-none focus:border-black"
                  />
                </label>
                <label className="block text-xs font-black uppercase tracking-wider">
                  Executive case summary
                  <textarea
                    value={draft.executive_case_summary}
                    maxLength={20000}
                    onChange={(event) => setDraft((current) => ({ ...current, executive_case_summary: event.target.value }))}
                    className="mt-2 min-h-32 w-full border border-black/20 p-3 text-sm font-semibold normal-case tracking-normal outline-none focus:border-black"
                  />
                </label>
                {([
                  ["evidence_still_required", "Evidence still required"],
                  ["investigation_next_steps", "Investigation next steps"],
                  ["limitations_and_disclaimers", "Limitations and disclaimers"],
                ] as const).map(([field, label]) => (
                  <label key={field} className="block text-xs font-black uppercase tracking-wider">
                    {label} <span className="font-semibold normal-case tracking-normal text-neutral">(one item per line)</span>
                    <textarea
                      value={draft[field]}
                      onChange={(event) => setDraft((current) => ({ ...current, [field]: event.target.value }))}
                      className="mt-2 min-h-24 w-full border border-black/20 p-3 text-sm font-semibold normal-case tracking-normal outline-none focus:border-black"
                    />
                  </label>
                ))}
              </div>
            </>
          ) : (
            <div className="p-5">
              <p className="mono-label">Permanent action</p>
              <h2 id="report-delete-title" className="mt-2 text-2xl font-black">Delete report?</h2>
              <p className="mt-3 text-sm font-semibold leading-6 text-neutral-800">
                This deletes report {workflow.report_id}. The parent case and its completed analysis are preserved, so a new report can be generated later.
              </p>
            </div>
          )}

          {error ? (
            <p role="alert" className="mx-5 mb-4 border border-red-500/30 bg-red-50 p-3 text-sm font-semibold text-red-800">{error}</p>
          ) : null}
          <div className="flex flex-wrap justify-end gap-3 border-t border-black/10 p-4">
            <button type="button" onClick={closeDialog} disabled={busy} className="border border-black px-4 py-2 text-xs font-black uppercase tracking-wider hover:bg-neutral-100 disabled:opacity-40">
              Cancel
            </button>
            <button
              type="button"
              onClick={() => void (mode === "edit" ? saveReport() : confirmDelete())}
              disabled={busy || (mode === "edit" && !hasChanges)}
              className="border border-black bg-black px-4 py-2 text-xs font-black uppercase tracking-wider text-white hover:bg-neutral-800 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {busy ? (mode === "edit" ? "Saving..." : "Deleting...") : mode === "edit" ? "Save changes" : "Delete report"}
            </button>
          </div>
        </AccessibleDialog>
      ) : null}
    </>
  );
}
