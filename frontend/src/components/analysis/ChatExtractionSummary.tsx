import type { ReactNode } from "react";
import type {
  ChatBaselineExtraction,
  ChatExtraction,
} from "@/lib/api";
import { FailedChatExtractionState } from "./ChatExtractionState";

interface ChatExtractionSummaryProps {
  extraction: ChatExtraction;
  onOpenChat: () => void;
}

export function ChatExtractionSummary({
  extraction,
  onOpenChat,
}: ChatExtractionSummaryProps) {
  if (extraction.status === "failed") {
    return (
      <FailedChatExtractionState
        extraction={extraction}
        onOpenChat={onOpenChat}
      />
    );
  }
  return <BaselineExtractionSummary extraction={extraction} />;
}

function BaselineExtractionSummary({
  extraction,
}: {
  extraction: ChatBaselineExtraction;
}) {
  return (
    <SummaryShell
      eyebrow="Baseline LLM candidates"
      title="User-reported incident facts"
      description="This single-pass baseline uses only the selected thread’s user case statement and clarification answers. It is a candidate extraction, not validated forensic evidence."
    >
      <div className="mb-4 rounded-xl border border-line bg-surface-nested p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h4 className="text-[10px] font-extrabold uppercase tracking-[0.14em] text-ink-secondary">
            Case summary
          </h4>
          <ItemBadges />
        </div>
        <p className="mt-2 text-sm leading-6 text-ink">
          {extraction.case_summary}
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <ExtractionList
          title="Entities"
          count={extraction.entities.length}
          emptyMessage="No explicitly reported entity was extracted."
        >
          {extraction.entities.map((item) => (
            <li key={item.entity_id} className="rounded-xl bg-surface p-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-bold text-ink">{item.name}</p>
                  <p className="mt-1 text-xs text-ink-secondary">
                    {item.entity_type}
                    {item.reported_role ? ` · ${item.reported_role}` : ""}
                  </p>
                </div>
                <span className="shrink-0 text-[10px] font-bold uppercase tracking-[0.1em] text-ink-secondary">
                  {item.entity_id}
                </span>
              </div>
              <ConfidenceLine confidence={item.confidence} />
              <ItemBadges />
            </li>
          ))}
        </ExtractionList>

        <ExtractionList
          title="Case details"
          count={extraction.evidence.length}
          emptyMessage="No user-reported case detail was extracted."
        >
          {extraction.evidence.map((item) => (
            <li key={item.evidence_id} className="rounded-xl bg-surface p-3">
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm font-bold text-ink">{item.title}</p>
                <span className="shrink-0 text-[10px] font-bold uppercase tracking-[0.1em] text-ink-secondary">
                  {item.evidence_id}
                </span>
              </div>
              <p className="mt-1 text-xs leading-5 text-ink-secondary">
                {item.description}
              </p>
              <p className="mt-1 text-[11px] text-ink-secondary">
                {item.artifact_type} · {item.status} · {item.confidence}
              </p>
              <ItemBadges />
            </li>
          ))}
        </ExtractionList>

        <ExtractionList
          title="Missing information"
          count={extraction.missing_information.length}
          emptyMessage="No explicit missing-information item was extracted."
        >
          {extraction.missing_information.map((item) => (
            <li key={item.missing_id} className="rounded-xl bg-surface p-3">
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm leading-5 text-ink">
                  {item.description}
                </p>
                <span className="shrink-0 text-[10px] font-bold uppercase tracking-[0.1em] text-ink-secondary">
                  {item.importance}
                </span>
              </div>
              <ItemBadges />
            </li>
          ))}
        </ExtractionList>
      </div>

      <div className="mt-4 rounded-xl border border-line bg-surface p-4">
        <div className="flex items-center justify-between gap-3">
          <h4 className="text-[10px] font-extrabold uppercase tracking-[0.14em] text-ink-secondary">
            Warnings
          </h4>
          <span className="text-xs font-bold text-ink-secondary">
            {extraction.warnings.length}
          </span>
        </div>
        {extraction.warnings.length > 0 ? (
          <ul className="mt-2 list-disc space-y-1 pl-5 text-xs leading-5 text-ink-secondary">
            {extraction.warnings.map((warning, index) => (
              <li key={`${warning}-${index}`}>{warning}</li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-xs leading-5 text-ink-secondary">
            No extraction warnings were returned.
          </p>
        )}
      </div>
    </SummaryShell>
  );
}

function SummaryShell({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <section
      aria-label="Unverified chat-reported candidates"
      className="w-full rounded-2xl border border-line-strong bg-surface p-4 shadow-[0_4px_18px_rgba(39,39,39,0.05)] sm:p-5"
    >
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line pb-3">
        <div>
          <p className="text-[10px] font-extrabold uppercase tracking-[0.16em] text-ink-secondary">
            {eyebrow}
          </p>
          <h3 className="mt-1 text-base font-extrabold tracking-tight text-ink">
            {title}
          </h3>
        </div>
        <ItemBadges />
      </div>
      <p className="mt-3 text-xs leading-5 text-ink-secondary">{description}</p>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function ItemBadges() {
  return (
    <div className="mt-2 flex flex-wrap gap-1.5" aria-label="Extraction labels">
      <span className="rounded-full border border-line-strong bg-surface-nested px-2 py-0.5 text-[9px] font-extrabold uppercase tracking-[0.1em] text-ink-secondary">
        Candidate
      </span>
      <span className="rounded-full border border-line-strong bg-surface px-2 py-0.5 text-[9px] font-extrabold uppercase tracking-[0.1em] text-ink-secondary">
        User-reported
      </span>
      <span className="rounded-full border border-line-strong bg-surface px-2 py-0.5 text-[9px] font-extrabold uppercase tracking-[0.1em] text-ink-secondary">
        Unverified
      </span>
    </div>
  );
}

function ConfidenceLine({
  confidence,
}: {
  confidence: string;
}) {
  return (
    <p className="mt-1 text-[11px] text-ink-secondary">
      Confidence: {confidence}
    </p>
  );
}

interface ExtractionListProps {
  title: string;
  count: number;
  emptyMessage: string;
  children: ReactNode;
}

function ExtractionList({
  title,
  count,
  emptyMessage,
  children,
}: ExtractionListProps) {
  return (
    <div className="rounded-xl border border-line bg-surface-nested p-3">
      <div className="flex items-center justify-between gap-3">
        <h4 className="text-[10px] font-extrabold uppercase tracking-[0.14em] text-ink-secondary">
          {title}
        </h4>
        <span className="text-xs font-bold text-ink-secondary">{count}</span>
      </div>
      {count > 0 ? (
        <ul className="mt-2 space-y-2">{children}</ul>
      ) : (
        <p className="mt-2 text-xs leading-5 text-ink-secondary">{emptyMessage}</p>
      )}
    </div>
  );
}
