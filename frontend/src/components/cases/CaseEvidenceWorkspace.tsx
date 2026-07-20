"use client";

import CaseRouteState from "@/components/cases/CaseRouteState";
import CaseStageShell from "@/components/cases/CaseStageShell";
import {
  analysisStatusLabel,
  OutputProvenance,
  outputSourceLabel,
} from "@/components/cases/CaseOutputState";
import { isNotFound, useCase, useCaseOutputs } from "@/hooks/useCase";
import type { CaseOutputItem } from "@/lib/cases";

function relatedItems(item: CaseOutputItem, candidates: CaseOutputItem[]): CaseOutputItem[] {
  const references = new Set([item.item_id, ...item.source_references]);
  return candidates.filter((candidate) =>
    candidate.source_references.some((reference) => references.has(reference)),
  );
}

export default function CaseEvidenceWorkspace({ caseId }: { caseId: string | null }) {
  const caseQuery = useCase(caseId);
  const outputsQuery = useCaseOutputs(caseId);
  const loadedCase = caseQuery.data;

  if (!caseId) {
    return <CaseRouteState title="Evidence" message="No case ID was provided." />;
  }
  if (caseQuery.isLoading || outputsQuery.isLoading) {
    return <CaseRouteState title="Evidence" message={`Loading case ${caseId}.`} />;
  }
  if (isNotFound(caseQuery.error) || isNotFound(outputsQuery.error)) {
    return <CaseRouteState title="Evidence" message={`Case ${caseId} was not found.`} />;
  }
  if (caseQuery.error || outputsQuery.error || !loadedCase || !outputsQuery.data) {
    return <CaseRouteState title="Evidence" message="Could not load authoritative case evidence." />;
  }

  const evidenceBucket = outputsQuery.data.outputs.evidence;
  const mappings = outputsQuery.data.outputs.attack_mappings.items;
  const recommendations = outputsQuery.data.outputs.recommendations.items;

  return (
    <CaseStageShell activeStage="evidence" caseData={loadedCase}>
      <div className="mx-auto max-w-6xl p-5">
        <section className="border border-black/10 bg-white p-5">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="mono-label">Evidence</p>
              <h1 className="mt-2 text-2xl font-black">Current case evidence</h1>
            </div>
            <span className="border border-black/15 px-2 py-1 text-[10px] font-black uppercase tracking-wider">
              {analysisStatusLabel(outputsQuery.data.analysis.status)}
            </span>
          </div>
          <p className="mt-2 max-w-3xl text-sm font-semibold text-neutral">
            Evidence is read from the backend lifecycle view. Intake evidence is labeled as analyst-provided and is never presented as a confirmed model finding.
          </p>

          <div className="mt-5 grid gap-4">
            {evidenceBucket.current_count ? (
              evidenceBucket.items.map((evidence) => {
                const relatedMappings = relatedItems(evidence, mappings);
                const relatedRecommendations = relatedItems(evidence, recommendations);
                return (
                  <article key={evidence.item_id} className="border border-black/10 bg-neutral-50 p-4">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                      <div>
                        <p className="mono-label">{evidence.item_id}</p>
                        <h2 className="mt-1 text-lg font-black">{evidence.title}</h2>
                        <p className="mt-2 text-sm font-semibold leading-6 text-neutral-900">
                          {evidence.description || "No description recorded."}
                        </p>
                      </div>
                      <span className="shrink-0 border border-black/15 bg-white px-2 py-1 text-[10px] font-black uppercase tracking-wider">
                        {evidence.status}
                      </span>
                    </div>

                    <OutputProvenance item={evidence} />
                    <p className="mt-3 text-xs font-semibold text-neutral-800">
                      Source: {outputSourceLabel(evidence.source_type)}
                      {evidence.source_type === "analyst_input"
                        ? " — analyst-provided, not system-confirmed."
                        : "."}
                    </p>

                    <div className="mt-4 grid gap-3 lg:grid-cols-2">
                      <section className="border border-black/10 bg-white p-3">
                        <p className="mono-label">Related current ATT&CK mappings</p>
                        {relatedMappings.length ? (
                          <ul className="mt-3 space-y-2">
                            {relatedMappings.map((mapping) => (
                              <li key={mapping.item_id} className="border border-black/10 p-3">
                                <p className="text-sm font-black">{mapping.item_id} {mapping.title}</p>
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className="mt-3 text-sm font-semibold text-neutral">No current mapping references this evidence.</p>
                        )}
                      </section>
                      <section className="border border-black/10 bg-white p-3">
                        <p className="mono-label">Related current recommendations</p>
                        {relatedRecommendations.length ? (
                          <ul className="mt-3 space-y-2">
                            {relatedRecommendations.map((recommendation) => (
                              <li key={recommendation.item_id} className="border border-black/10 p-3">
                                <p className="text-sm font-black">{recommendation.title}</p>
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className="mt-3 text-sm font-semibold text-neutral">No current recommendation references this evidence.</p>
                        )}
                      </section>
                    </div>
                  </article>
                );
              })
            ) : (
              <p className="border border-black/10 bg-neutral-50 p-4 text-sm font-semibold text-neutral">
                No analyst-provided intake evidence is available for this case.
              </p>
            )}
          </div>

          {outputsQuery.data.historical_outputs.evidence.historical_count ? (
            <p className="mt-4 border-t border-black/10 pt-3 text-xs font-semibold text-neutral">
              {outputsQuery.data.historical_outputs.evidence.historical_count} historical evidence item(s) are excluded from current counts.
            </p>
          ) : null}
        </section>
      </div>
    </CaseStageShell>
  );
}
