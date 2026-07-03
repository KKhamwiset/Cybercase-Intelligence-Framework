"use client";

import { useMemo, useState } from "react";
import { useParams } from "next/navigation";

import CaseRouteState from "@/components/cases/CaseRouteState";
import CaseStageShell from "@/components/cases/CaseStageShell";
import SaveStatus, { SaveState } from "@/components/cases/SaveStatus";
import { FindingStatusBadge } from "@/components/report/status";
import { isNotFound, useCase, useUpdateCase } from "@/hooks/useCase";
import { getRouteParam } from "@/lib/routeParams";

const VALIDATION_NOTE =
  "ATT&CK mappings require analyst validation before confirmed reporting.";

export default function CaseAttackMappingPage() {
  const params = useParams();
  const caseId = getRouteParam(params.caseId);
  const caseQuery = useCase(caseId);
  const mutation = useUpdateCase(caseId ?? "");
  const [saveState, setSaveState] = useState<SaveState>("saved");
  const displayedSaveState: SaveState =
    mutation.isPending || saveState === "saving" ? "saving" : saveState;

  const mappingSummary = useMemo(() => {
    const mappings = caseQuery.data?.attack_mappings ?? [];
    return {
      confirmed: mappings.filter((mapping) => mapping.metadata.status === "confirmed").length,
      candidate: mappings.filter((mapping) => mapping.metadata.status === "candidate").length,
      unknown: mappings.filter((mapping) => mapping.metadata.status === "unknown").length,
    };
  }, [caseQuery.data?.attack_mappings]);

  if (!caseId) {
    return <CaseRouteState title="ATT&CK Mapping" message="No case ID was provided." />;
  }

  if (caseQuery.isLoading) {
    return <CaseRouteState title="ATT&CK Mapping" message={`Loading case ${caseId}.`} />;
  }

  if (isNotFound(caseQuery.error)) {
    return <CaseRouteState title="ATT&CK Mapping" message={`Case ${caseId} was not found.`} />;
  }

  if (caseQuery.error || !caseQuery.data) {
    return <CaseRouteState title="ATT&CK Mapping" message="Could not load this case." />;
  }

  const hasValidationNote = caseQuery.data.analyst_notes.includes(VALIDATION_NOTE);

  const saveValidationNote = async () => {
    if (hasValidationNote || mutation.isPending) {
      return;
    }
    const nextNotes = [caseQuery.data.analyst_notes, VALIDATION_NOTE]
      .filter(Boolean)
      .join("\n\n");
    setSaveState("saving");
    try {
      await mutation.mutateAsync({
        analyst_notes: nextNotes,
      });
      setSaveState("saved");
    } catch {
      setSaveState("failed");
    }
  };

  return (
    <CaseStageShell
      activeStage="attack-mapping"
      caseData={caseQuery.data}
      actions={<SaveStatus state={displayedSaveState} />}
    >
      <div className="mx-auto max-w-5xl p-5">
        <section className="border border-black/10 bg-white p-5">
          <p className="mono-label">ATT&CK Mapping</p>
          <h1 className="mt-2 text-2xl font-black">Technique mappings</h1>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            <div className="border border-black/10 p-3">
              <p className="mono-label">Confirmed</p>
              <p className="mt-1 text-2xl font-black">{mappingSummary.confirmed}</p>
            </div>
            <div className="border border-black/10 p-3">
              <p className="mono-label">Candidate</p>
              <p className="mt-1 text-2xl font-black">{mappingSummary.candidate}</p>
            </div>
            <div className="border border-black/10 p-3">
              <p className="mono-label">Unknown</p>
              <p className="mt-1 text-2xl font-black">{mappingSummary.unknown}</p>
            </div>
          </div>

          <div className="mt-5 space-y-3">
            {caseQuery.data.attack_mappings.length ? (
              caseQuery.data.attack_mappings.map((mapping) => (
                <div key={mapping.mapping_id} className="border border-black/10 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-black">
                        {mapping.technique_id} {mapping.technique_name}
                      </p>
                      <p className="mt-1 text-sm text-neutral">
                        {mapping.rationale || "No rationale recorded."}
                      </p>
                    </div>
                    <FindingStatusBadge status={mapping.metadata.status} />
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs font-black uppercase text-neutral">
                    <span>Confidence {mapping.metadata.confidence}</span>
                    <span>Evidence {mapping.metadata.evidence_ids.join(", ") || "None"}</span>
                    <span>{mapping.metadata.source_type}</span>
                  </div>
                </div>
              ))
            ) : (
              <p className="text-sm font-semibold text-neutral">
                No ATT&CK mappings have been saved for this case yet.
              </p>
            )}
          </div>

          <button
            type="button"
            onClick={saveValidationNote}
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
