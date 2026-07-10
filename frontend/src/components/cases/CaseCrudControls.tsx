"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";

import AccessibleDialog from "@/components/AccessibleDialog";
import { apiErrorMessage } from "@/lib/api-errors";
import type { CaseSeverity, CaseStatus, StructuredCase } from "@/lib/cases";
import {
  useCaseActionPending,
  useDeleteCase,
  useUpdateCase,
} from "@/hooks/useCase";

const CASE_STATUSES: CaseStatus[] = [
  "new",
  "triage",
  "investigating",
  "contained",
  "resolved",
  "unknown",
];
const CASE_SEVERITIES: CaseSeverity[] = ["critical", "high", "medium", "low", "unknown"];

type CaseMetadataDraft = {
  title: string;
  case_type: string;
  status: CaseStatus;
  severity: CaseSeverity;
};

function draftFromCase(caseData: StructuredCase): CaseMetadataDraft {
  return {
    title: caseData.title,
    case_type: caseData.case_type,
    status: caseData.status,
    severity: caseData.severity,
  };
}

export default function CaseCrudControls({ caseData }: { caseData: StructuredCase }) {
  const router = useRouter();
  const updateMutation = useUpdateCase(caseData.case_id);
  const deleteMutation = useDeleteCase(caseData.case_id);
  const actionPending = useCaseActionPending(caseData.case_id);
  const firstFieldRef = useRef<HTMLInputElement>(null);
  const [mode, setMode] = useState<"closed" | "edit" | "delete">("closed");
  const [draft, setDraft] = useState<CaseMetadataDraft>(() => draftFromCase(caseData));
  const [error, setError] = useState("");

  const normalized = {
    ...draft,
    title: draft.title.trim(),
    case_type: draft.case_type.trim(),
  };
  const changed =
    normalized.title !== caseData.title ||
    normalized.case_type !== caseData.case_type ||
    normalized.status !== caseData.status ||
    normalized.severity !== caseData.severity;

  function closeDialog() {
    if (actionPending) return;
    setMode("closed");
    setDraft(draftFromCase(caseData));
    setError("");
  }

  async function saveCase() {
    if (!normalized.title) {
      setError("Title is required.");
      return;
    }
    if (!normalized.case_type) {
      setError("Case type is required.");
      return;
    }
    if (normalized.title.length > 255 || normalized.case_type.length > 80) {
      setError("Title must be 255 characters or fewer and case type 80 characters or fewer.");
      return;
    }
    setError("");
    try {
      await updateMutation.mutateAsync(normalized);
      setMode("closed");
    } catch (caught) {
      setError(apiErrorMessage(caught, "Could not save case changes."));
    }
  }

  async function confirmDelete() {
    setError("");
    try {
      await deleteMutation.mutateAsync();
      router.replace("/cases");
      router.refresh();
    } catch (caught) {
      setError(apiErrorMessage(caught, "Could not delete this case."));
    }
  }

  return (
    <>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => {
            setDraft(draftFromCase(caseData));
            setError("");
            setMode("edit");
          }}
          disabled={actionPending}
          className="border border-black/20 bg-white px-3 py-2 text-xs font-black uppercase tracking-wider hover:border-black disabled:cursor-not-allowed disabled:opacity-40"
        >
          Edit case
        </button>
        <button
          type="button"
          onClick={() => {
            setError("");
            setMode("delete");
          }}
          disabled={actionPending}
          className="border border-black bg-black px-3 py-2 text-xs font-black uppercase tracking-wider text-white hover:bg-neutral-800 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Delete case
        </button>
      </div>

      {mode !== "closed" ? (
        <AccessibleDialog
          titleId={mode === "edit" ? "case-edit-title" : "case-delete-title"}
          onClose={closeDialog}
          initialFocusRef={mode === "edit" ? firstFieldRef : undefined}
        >
            {mode === "edit" ? (
              <>
                <div className="border-b border-black/10 p-5">
                  <p className="mono-label">Case metadata</p>
                  <h2 id="case-edit-title" className="mt-2 text-2xl font-black">
                    Edit case
                  </h2>
                  <p className="mt-2 text-sm font-semibold text-neutral">
                    Narrative and analyst notes remain editable in their case stages.
                  </p>
                </div>
                <div className="grid gap-4 p-5 sm:grid-cols-2">
                  <label className="sm:col-span-2 text-xs font-black uppercase tracking-wider">
                    Title
                    <input
                      ref={firstFieldRef}
                      value={draft.title}
                      maxLength={255}
                      onChange={(event) => setDraft((current) => ({ ...current, title: event.target.value }))}
                      className="mt-2 w-full border border-black/20 p-3 text-sm font-semibold normal-case tracking-normal outline-none focus:border-black"
                    />
                  </label>
                  <label className="sm:col-span-2 text-xs font-black uppercase tracking-wider">
                    Case type
                    <input
                      value={draft.case_type}
                      maxLength={80}
                      onChange={(event) => setDraft((current) => ({ ...current, case_type: event.target.value }))}
                      className="mt-2 w-full border border-black/20 p-3 text-sm font-semibold normal-case tracking-normal outline-none focus:border-black"
                    />
                  </label>
                  <label className="text-xs font-black uppercase tracking-wider">
                    Status
                    <select
                      value={draft.status}
                      onChange={(event) => setDraft((current) => ({ ...current, status: event.target.value as CaseStatus }))}
                      className="mt-2 w-full border border-black/20 bg-white p-3 text-sm font-semibold normal-case tracking-normal outline-none focus:border-black"
                    >
                      {CASE_STATUSES.map((status) => <option key={status}>{status}</option>)}
                    </select>
                  </label>
                  <label className="text-xs font-black uppercase tracking-wider">
                    Severity
                    <select
                      value={draft.severity}
                      onChange={(event) => setDraft((current) => ({ ...current, severity: event.target.value as CaseSeverity }))}
                      className="mt-2 w-full border border-black/20 bg-white p-3 text-sm font-semibold normal-case tracking-normal outline-none focus:border-black"
                    >
                      {CASE_SEVERITIES.map((severity) => <option key={severity}>{severity}</option>)}
                    </select>
                  </label>
                </div>
              </>
            ) : (
              <div className="p-5">
                <p className="mono-label">Permanent action</p>
                <h2 id="case-delete-title" className="mt-2 text-2xl font-black">
                  Delete case?
                </h2>
                <p className="mt-3 text-sm font-semibold leading-6 text-neutral-800">
                  This deletes {caseData.case_id} and its dependent chat and report records. It cannot be undone.
                </p>
              </div>
            )}

            {error ? (
              <p role="alert" className="mx-5 mb-4 border border-red-500/30 bg-red-50 p-3 text-sm font-semibold text-red-800">
                {error}
              </p>
            ) : null}
            <div className="flex flex-wrap justify-end gap-3 border-t border-black/10 p-4">
              <button
                type="button"
                onClick={closeDialog}
                disabled={actionPending}
                className="border border-black px-4 py-2 text-xs font-black uppercase tracking-wider hover:bg-neutral-100 disabled:opacity-40"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => void (mode === "edit" ? saveCase() : confirmDelete())}
                disabled={actionPending || (mode === "edit" && !changed)}
                className="border border-black bg-black px-4 py-2 text-xs font-black uppercase tracking-wider text-white hover:bg-neutral-800 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {actionPending
                  ? mode === "edit" ? "Saving..." : "Deleting..."
                  : mode === "edit" ? "Save changes" : "Delete case"}
              </button>
            </div>
        </AccessibleDialog>
      ) : null}
    </>
  );
}
