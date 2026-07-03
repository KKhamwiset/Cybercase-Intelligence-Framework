"use client";

import CaseRouteState from "@/components/cases/CaseRouteState";
import CaseStageShell from "@/components/cases/CaseStageShell";
import { FindingStatusBadge } from "@/components/report/status";
import { isNotFound, useCase } from "@/hooks/useCase";
import type { CaseAttackMapping, StructuredCase } from "@/lib/cases";
import type { ActionItemView, EvidenceItemView } from "@/lib/reports";

function formatCollectedAt(value?: string | null): string {
  if (!value) {
    return "Not recorded";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString();
}

function relatedAttackMappings(
  evidence: EvidenceItemView,
  caseData: StructuredCase,
): CaseAttackMapping[] {
  return caseData.attack_mappings.filter((mapping) =>
    mapping.metadata.evidence_ids.includes(evidence.evidence_id),
  );
}

function relatedRecommendations(
  evidence: EvidenceItemView,
  caseData: StructuredCase,
): ActionItemView[] {
  return caseData.recommendations.filter((recommendation) =>
    recommendation.metadata.evidence_ids.includes(evidence.evidence_id),
  );
}

export default function CaseEvidenceWorkspace({ caseId }: { caseId: string | null }) {
  const caseQuery = useCase(caseId);
  const loadedCase = caseQuery.data;

  if (!caseId) {
    return <CaseRouteState title="Evidence" message="No case ID was provided." />;
  }

  if (caseQuery.isLoading) {
    return <CaseRouteState title="Evidence" message={`Loading case ${caseId}.`} />;
  }

  if (isNotFound(caseQuery.error)) {
    return <CaseRouteState title="Evidence" message={`Case ${caseId} was not found.`} />;
  }

  if (caseQuery.error || !loadedCase) {
    return <CaseRouteState title="Evidence" message="Could not load this case." />;
  }

  return (
    <CaseStageShell activeStage="evidence" caseData={loadedCase}>
      <div className="mx-auto max-w-6xl p-5">
        <section className="border border-black/10 bg-white p-5">
          <p className="mono-label">Evidence</p>
          <h1 className="mt-2 text-2xl font-black">Saved evidence projection</h1>
          <p className="mt-2 max-w-2xl text-sm font-semibold text-neutral">
            Read-only evidence items generated from saved case intake and case outputs.
          </p>

          <div className="mt-5 grid gap-4">
            {loadedCase.evidence_items.length ? (
              loadedCase.evidence_items.map((evidence) => {
                const mappings = relatedAttackMappings(evidence, loadedCase);
                const recommendations = relatedRecommendations(evidence, loadedCase);

                return (
                  <article
                    key={evidence.evidence_id}
                    className="border border-black/10 bg-neutral-50 p-4"
                  >
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                      <div>
                        <p className="mono-label">{evidence.evidence_id}</p>
                        <h2 className="mt-1 text-lg font-black">{evidence.title}</h2>
                        <p className="mt-2 text-sm font-semibold leading-6 text-neutral-900">
                          {evidence.description || "No description recorded."}
                        </p>
                      </div>

                      <FindingStatusBadge status={evidence.status} />
                    </div>

                    <dl className="mt-4 grid gap-3 border-t border-black/10 pt-4 text-xs font-bold uppercase text-neutral sm:grid-cols-2 lg:grid-cols-5">
                      <div>
                        <dt>Source</dt>
                        <dd className="mt-1 text-black">{evidence.source_type}</dd>
                      </div>
                      <div>
                        <dt>Confidence</dt>
                        <dd className="mt-1 text-black">{evidence.confidence}</dd>
                      </div>
                      <div>
                        <dt>Analyst verified</dt>
                        <dd className="mt-1 text-black">
                          {evidence.analyst_verified ? "Yes" : "No"}
                        </dd>
                      </div>
                      <div>
                        <dt>Collected at</dt>
                        <dd className="mt-1 text-black">
                          {formatCollectedAt(evidence.collected_at)}
                        </dd>
                      </div>
                      <div>
                        <dt>Status</dt>
                        <dd className="mt-1 text-black">{evidence.status}</dd>
                      </div>
                    </dl>

                    <div className="mt-4 grid gap-3 lg:grid-cols-2">
                      <section className="border border-black/10 bg-white p-3">
                        <p className="mono-label">Related ATT&CK mappings</p>
                        {mappings.length ? (
                          <ul className="mt-3 space-y-2">
                            {mappings.map((mapping) => (
                              <li
                                key={mapping.mapping_id}
                                className="border border-black/10 p-3"
                              >
                                <p className="text-sm font-black">
                                  {mapping.technique_id} {mapping.technique_name}
                                </p>
                                <p className="mt-1 text-xs leading-5 text-neutral">
                                  {mapping.rationale || "No rationale recorded."}
                                </p>
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className="mt-3 text-sm font-semibold text-neutral">
                            No ATT&CK mappings reference this evidence.
                          </p>
                        )}
                      </section>

                      <section className="border border-black/10 bg-white p-3">
                        <p className="mono-label">Related recommendations</p>
                        {recommendations.length ? (
                          <ul className="mt-3 space-y-2">
                            {recommendations.map((recommendation) => (
                              <li
                                key={recommendation.action_id}
                                className="border border-black/10 p-3"
                              >
                                <p className="text-sm font-black">
                                  {recommendation.title}
                                </p>
                                <p className="mt-1 text-xs leading-5 text-neutral">
                                  {recommendation.description ||
                                    "No recommendation detail recorded."}
                                </p>
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className="mt-3 text-sm font-semibold text-neutral">
                            No recommendations reference this evidence.
                          </p>
                        )}
                      </section>
                    </div>
                  </article>
                );
              })
            ) : (
              <p className="border border-black/10 bg-neutral-50 p-4 text-sm font-semibold text-neutral">
                No evidence items are available yet. Save the intake narrative first.
              </p>
            )}
          </div>
        </section>
      </div>
    </CaseStageShell>
  );
}
