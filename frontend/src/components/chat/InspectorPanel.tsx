import type { ReactNode } from "react";
import type {
  AnalysisAvailability,
  InspectorSelection,
  RunPhase,
} from "./types";

interface InspectorPanelProps {
  caseId: string | null;
  retrievalContextId: string | null;
  phase: RunPhase;
  availability: AnalysisAvailability;
  selection: InspectorSelection;
  inline?: boolean;
}

const phaseLabels: Record<RunPhase, string> = {
  idle: "Ready for input",
  querying: "Query in progress",
  awaiting_followup: "Waiting for follow-up answer",
  analyzing: "Validating evidence",
  ready: "Run complete",
  error: "Request error",
};

function DetailRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-[10px] font-extrabold uppercase tracking-[0.14em] text-gray-500">
        {label}
      </dt>
      <dd className="mt-1 break-words text-sm leading-6 text-gray-800">
        {children}
      </dd>
    </div>
  );
}

function SelectionDetails({ selection }: { selection: InspectorSelection }) {
  if (!selection) {
    return (
      <p className="text-sm leading-6 text-gray-600">
        Select an evidence item, MITRE candidate, or timeline event to inspect
        the returned details.
      </p>
    );
  }

  if (selection.kind === "claim") {
    const claim = selection.item;
    return (
      <dl className="space-y-5">
        <DetailRow label="Claim ID">
          <span className="font-mono text-xs">{claim.claim_id}</span>
        </DetailRow>
        <DetailRow label="Claim">{claim.claim_text}</DetailRow>
        <DetailRow label="Trust state">
          {claim.validation_status} · {claim.evidential_status}
        </DetailRow>
        <DetailRow label="Scope">{claim.claim_scope}</DetailRow>
        <DetailRow label="Source">
          <span className="font-mono text-xs">{claim.source_id}</span>
        </DetailRow>
        <DetailRow label="Exact quote">“{claim.exact_quote}”</DetailRow>
        <DetailRow label="Span">
          <span className="font-mono text-xs">
            {claim.span_start ?? "—"}–{claim.span_end ?? "—"}
          </span>
        </DetailRow>
        <DetailRow label="Validation reasons">
          {claim.validation_reasons.length
            ? claim.validation_reasons.join(", ")
            : "None returned"}
        </DetailRow>
      </dl>
    );
  }

  if (selection.kind === "source") {
    const source = selection.item;
    return (
      <dl className="space-y-5">
        <DetailRow label="Source ID">
          <span className="break-all font-mono text-xs">{source.source_id}</span>
        </DetailRow>
        <DetailRow label="Type">{source.source_type}</DetailRow>
        <DetailRow label="Identity">{source.identity_status}</DetailRow>
        <DetailRow label="SHA-256">
          <span className="break-all font-mono text-xs">
            {source.text_sha256}
          </span>
        </DetailRow>
        <DetailRow label="Text preview">
          <span className="block max-h-80 overflow-y-auto whitespace-pre-wrap rounded-xl bg-gray-50 p-3 font-mono text-xs leading-5">
            {source.normalized_text.slice(0, 4_000)}
            {source.normalized_text.length > 4_000 ? "\n…" : ""}
          </span>
        </DetailRow>
      </dl>
    );
  }

  if (selection.kind === "mitre") {
    const row = selection.item;
    return (
      <dl className="space-y-5">
        <DetailRow label="Review status">Candidate · needs review</DetailRow>
        <DetailRow label="Technique ID">{row.technique_id || "Not returned"}</DetailRow>
        <DetailRow label="Name">{row.name || "Not returned"}</DetailRow>
        <DetailRow label="Tactic">{row.tactic || "Not returned"}</DetailRow>
        <DetailRow label="Relevance">
          {row.relevance || row.description || "Not returned"}
        </DetailRow>
        <DetailRow label="Retrieved source">
          {row.source || "Not returned"}
        </DetailRow>
      </dl>
    );
  }

  return (
    <dl className="space-y-5">
      <DetailRow label="Returned order">{selection.index + 1}</DetailRow>
      <DetailRow label="Event text">{selection.item}</DetailRow>
    </dl>
  );
}

function InspectorContent({
  caseId,
  retrievalContextId,
  phase,
  availability,
  selection,
}: Omit<InspectorPanelProps, "inline">) {
  return (
    <>
      <div className="border-b border-gray-200 pb-5">
        <p className="text-[10px] font-extrabold uppercase tracking-[0.16em] text-gray-500">
          Current run
        </p>
        <p className="mt-2 text-sm font-extrabold text-black">
          {phaseLabels[phase]}
        </p>
        {availability.message && (
          <p className="mt-2 text-xs leading-5 text-gray-600">
            {availability.message}
          </p>
        )}
        <dl className="mt-4 space-y-3">
          <DetailRow label="Case ID">
            <span className="break-all font-mono text-xs">
              {caseId || "Not created"}
            </span>
          </DetailRow>
          <DetailRow label="Retrieval context">
            <span className="break-all font-mono text-xs">
              {retrievalContextId || "Not returned"}
            </span>
          </DetailRow>
        </dl>
      </div>

      <div className="pt-5">
        <p className="mb-4 text-[10px] font-extrabold uppercase tracking-[0.16em] text-gray-500">
          Selected details
        </p>
        <SelectionDetails selection={selection} />
      </div>
    </>
  );
}

export function InspectorPanel({ inline = false, ...props }: InspectorPanelProps) {
  if (inline) {
    return (
      <details className="rounded-2xl border border-gray-200 bg-gray-50">
        <summary className="flex min-h-12 cursor-pointer items-center justify-between px-4 text-sm font-extrabold outline-none focus-visible:ring-2 focus-visible:ring-black focus-visible:ring-offset-2">
          Investigation details
        </summary>
        <div className="border-t border-gray-200 bg-white p-4">
          <InspectorContent {...props} />
        </div>
      </details>
    );
  }

  return (
    <aside
      aria-label="Investigation details"
      className="hidden h-full w-[344px] shrink-0 overflow-y-auto border-l border-gray-200 bg-gray-50 p-6 min-[1100px]:block"
    >
      <h2 className="text-base font-extrabold tracking-tight">
        Investigation details
      </h2>
      <div className="mt-5">
        <InspectorContent {...props} />
      </div>
    </aside>
  );
}
