import type { ReactNode } from "react";
import type { MitreContextEntry } from "@/lib/api";
import { Icon } from "./icons";
import type { InspectorSelection } from "./types";

interface MitreMappingPanelProps {
  rows: MitreContextEntry[];
  inlineInspector: ReactNode;
  onSelect: (selection: InspectorSelection) => void;
}

const ATTACK_TECHNIQUE_ID = /^T\d{4}(?:\.\d{3})?$/i;

export function getAttackTechniqueUrl(techniqueId: string): string | null {
  const normalized = techniqueId.trim().toUpperCase();
  if (!ATTACK_TECHNIQUE_ID.test(normalized)) return null;
  return `https://attack.mitre.org/techniques/${normalized}/`;
}

export function MitreMappingPanel({
  rows,
  inlineInspector,
  onSelect,
}: MitreMappingPanelProps) {
  return (
    <section
      id="mitre-panel"
      role="tabpanel"
      aria-labelledby="vertical-mitre-tab horizontal-mitre-tab"
      className="h-full overflow-y-auto bg-white px-4 py-6 sm:px-6 lg:px-8"
    >
      <div className="mx-auto max-w-4xl">
        <header className="border-b border-gray-200 pb-5">
          <p className="text-xs font-extrabold uppercase tracking-[0.16em] text-gray-500">
            Analyst review required
          </p>
          <h2 className="mt-2 text-2xl font-extrabold tracking-tight">
            MITRE Mapping
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-gray-600">
            These rows are retrieval candidates. They do not confirm that a
            technique occurred in the submitted case.
          </p>
        </header>

        {rows.length === 0 ? (
          <p className="py-12 text-sm text-gray-600">
            No MITRE mapping candidates were returned.
          </p>
        ) : (
          <div className="divide-y divide-gray-200 border-b border-gray-200">
            {rows.map((row, index) => {
              const techniqueId = row.technique_id?.trim() ?? "";
              const techniqueUrl = getAttackTechniqueUrl(techniqueId);
              return (
                <article key={`${techniqueId || "candidate"}-${index}`} className="py-5">
                  <button
                    type="button"
                    onClick={() => onSelect({ kind: "mitre", item: row })}
                    className="block w-full rounded-xl px-2 py-1 text-left outline-none transition-colors hover:bg-gray-50 focus-visible:ring-2 focus-visible:ring-black focus-visible:ring-offset-2 motion-reduce:transition-none sm:px-3"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-full bg-black px-2.5 py-1 text-[10px] font-extrabold uppercase tracking-[0.12em] text-white">
                        Candidate
                      </span>
                      <span className="rounded-full border border-gray-300 px-2.5 py-1 text-[10px] font-extrabold uppercase tracking-[0.12em] text-gray-700">
                        Needs review
                      </span>
                      {techniqueId && (
                        <span className="font-mono text-xs font-bold text-gray-600">
                          {techniqueId}
                        </span>
                      )}
                    </div>
                    <h3 className="mt-3 text-base font-extrabold text-black sm:text-lg">
                      {row.name?.trim() || row.entity_type?.trim() || "Unnamed candidate"}
                    </h3>
                    {row.tactic && (
                      <p className="mt-1 text-xs font-bold uppercase tracking-[0.12em] text-gray-500">
                        {row.tactic}
                      </p>
                    )}
                    {(row.relevance || row.description) && (
                      <p className="mt-3 text-sm leading-6 text-gray-600">
                        {row.relevance || row.description}
                      </p>
                    )}
                  </button>

                  {techniqueUrl && (
                    <a
                      href={techniqueUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-2 inline-flex min-h-11 items-center gap-2 rounded-lg px-3 text-sm font-bold text-black outline-none hover:bg-gray-100 focus-visible:ring-2 focus-visible:ring-black focus-visible:ring-offset-2"
                    >
                      Open ATT&amp;CK technique
                      <Icon name="external" className="h-4 w-4" />
                    </a>
                  )}
                </article>
              );
            })}
          </div>
        )}

        <div className="mt-8 min-[1100px]:hidden">{inlineInspector}</div>
      </div>
    </section>
  );
}
