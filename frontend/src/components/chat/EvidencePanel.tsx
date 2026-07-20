"use client";

import { useState, type ReactNode } from "react";
import type { CaseAnalysisArtifact } from "@/lib/api";
import type {
  AnalysisAvailability,
  InspectorSelection,
} from "./types";

interface EvidencePanelProps {
  artifact: CaseAnalysisArtifact | null;
  availability: AnalysisAvailability;
  inlineInspector: ReactNode;
  onSelect: (selection: InspectorSelection) => void;
}

function EmptyAnalysis({ availability }: { availability: AnalysisAvailability }) {
  if (availability.status === "loading") {
    return <p role="status">Validating returned evidence…</p>;
  }
  if (availability.status === "unavailable" || availability.status === "error") {
    return <p>{availability.message}</p>;
  }
  return <p>No validated evidence is available for the current run.</p>;
}

export function EvidencePanel({
  artifact,
  availability,
  inlineInspector,
  onSelect,
}: EvidencePanelProps) {
  const [expandedSources, setExpandedSources] = useState<Set<string>>(
    () => new Set(),
  );

  const toggleSource = (sourceId: string) => {
    setExpandedSources((current) => {
      const next = new Set(current);
      if (next.has(sourceId)) next.delete(sourceId);
      else next.add(sourceId);
      return next;
    });
  };

  return (
    <section
      id="evidence-panel"
      role="tabpanel"
      aria-labelledby="vertical-evidence-tab horizontal-evidence-tab"
      className="h-full overflow-y-auto bg-white px-4 py-6 sm:px-6 lg:px-8"
    >
      <div className="mx-auto max-w-4xl">
        <header className="border-b border-gray-200 pb-5">
          <p className="text-xs font-extrabold uppercase tracking-[0.16em] text-gray-500">
            Validated artifact
          </p>
          <h2 className="mt-2 text-2xl font-extrabold tracking-tight">
            Evidence
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-gray-600">
            Caller-supplied text remains unverified. Retrieved context is shown as
            knowledge, not as proof that an event occurred in this case.
          </p>
        </header>

        {!artifact ? (
          <div className="py-12 text-sm leading-6 text-gray-600">
            <EmptyAnalysis availability={availability} />
          </div>
        ) : (
          <div className="space-y-10 py-7">
            <section aria-labelledby="claims-heading">
              <div className="flex items-end justify-between gap-4">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.14em] text-gray-500">
                    Material statements
                  </p>
                  <h3 id="claims-heading" className="mt-1 text-lg font-extrabold">
                    Claims
                  </h3>
                </div>
                <p className="font-mono text-xs text-gray-500">
                  {artifact.claims.length} returned
                </p>
              </div>

              {artifact.claims.length === 0 ? (
                <p className="mt-5 text-sm text-gray-600">
                  No validated claims were returned.
                </p>
              ) : (
                <div className="mt-4 divide-y divide-gray-200 border-y border-gray-200">
                  {artifact.claims.map((claim) => (
                    <button
                      key={claim.claim_id}
                      type="button"
                      onClick={() => onSelect({ kind: "claim", item: claim })}
                      className="block w-full px-1 py-5 text-left outline-none transition-colors hover:bg-gray-50 focus-visible:bg-gray-50 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-black motion-reduce:transition-none sm:px-3"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-full border border-gray-300 px-2.5 py-1 text-[10px] font-extrabold uppercase tracking-[0.12em]">
                          {claim.validation_status}
                        </span>
                        <span className="rounded-full bg-gray-100 px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.12em] text-gray-700">
                          {claim.evidential_status}
                        </span>
                        <span className="font-mono text-xs text-gray-500">
                          {claim.claim_id}
                        </span>
                      </div>
                      <p className="mt-3 text-sm font-bold leading-6 text-black sm:text-base">
                        {claim.claim_text}
                      </p>
                      <blockquote className="mt-3 border-l-2 border-gray-300 pl-3 text-sm leading-6 text-gray-600">
                        “{claim.exact_quote}”
                      </blockquote>
                      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 font-mono text-[11px] text-gray-500">
                        <span>source: {claim.source_id}</span>
                        <span>
                          span: {claim.span_start ?? "—"}–{claim.span_end ?? "—"}
                        </span>
                      </div>
                      {claim.validation_reasons.length > 0 && (
                        <p className="mt-3 text-xs leading-5 text-gray-600">
                          Reasons: {claim.validation_reasons.join(", ")}
                        </p>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </section>

            <section aria-labelledby="sources-heading">
              <div className="flex items-end justify-between gap-4">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.14em] text-gray-500">
                    Text inputs
                  </p>
                  <h3 id="sources-heading" className="mt-1 text-lg font-extrabold">
                    Sources
                  </h3>
                </div>
                <p className="font-mono text-xs text-gray-500">
                  {artifact.sources.length} returned
                </p>
              </div>

              {artifact.sources.length === 0 ? (
                <p className="mt-5 text-sm text-gray-600">
                  No analysis sources were returned.
                </p>
              ) : (
                <div className="mt-4 space-y-4">
                  {artifact.sources.map((source) => {
                    const expanded = expandedSources.has(source.source_id);
                    const isTruncated = source.normalized_text.length > 4_000;
                    const visibleText =
                      expanded || !isTruncated
                        ? source.normalized_text
                        : `${source.normalized_text.slice(0, 4_000)}\n…`;
                    const trustLabel =
                      source.source_type === "retrieved_context"
                        ? "Retrieved knowledge"
                        : "Caller-supplied · unverified";
                    return (
                      <article
                        key={source.source_id}
                        className="rounded-2xl border border-gray-200 bg-white p-4 sm:p-5"
                      >
                        <button
                          type="button"
                          onClick={() => onSelect({ kind: "source", item: source })}
                          className="w-full text-left outline-none focus-visible:ring-2 focus-visible:ring-black focus-visible:ring-offset-2"
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="rounded-full bg-gray-100 px-2.5 py-1 text-[10px] font-extrabold uppercase tracking-[0.12em] text-gray-700">
                              {trustLabel}
                            </span>
                            <span className="font-mono text-xs text-gray-500">
                              {source.source_type}
                            </span>
                          </div>
                          <p className="mt-3 break-all font-mono text-xs font-bold text-black">
                            {source.source_id}
                          </p>
                          <dl className="mt-3 grid gap-2 text-xs text-gray-600 sm:grid-cols-[110px_1fr]">
                            <dt className="font-bold text-gray-500">Identity</dt>
                            <dd className="break-all font-mono">
                              {source.identity_status}
                            </dd>
                            <dt className="font-bold text-gray-500">SHA-256</dt>
                            <dd className="break-all font-mono">
                              {source.text_sha256}
                            </dd>
                          </dl>
                        </button>

                        <div
                          className={`mt-4 overflow-y-auto whitespace-pre-wrap break-words rounded-xl bg-gray-50 p-3 font-mono text-xs leading-5 text-gray-700 ${
                            expanded ? "max-h-[40rem]" : "max-h-80"
                          }`}
                        >
                          {visibleText}
                        </div>
                        {isTruncated && (
                          <button
                            type="button"
                            onClick={() => toggleSource(source.source_id)}
                            aria-expanded={expanded}
                            className="mt-2 min-h-11 rounded-lg px-2 text-xs font-extrabold uppercase tracking-[0.12em] text-gray-600 outline-none hover:text-black focus-visible:ring-2 focus-visible:ring-black focus-visible:ring-offset-2"
                          >
                            {expanded ? "Collapse source" : "Expand full source"}
                          </button>
                        )}
                      </article>
                    );
                  })}
                </div>
              )}
            </section>
          </div>
        )}

        <div className="mt-8 min-[1100px]:hidden">{inlineInspector}</div>
      </div>
    </section>
  );
}
