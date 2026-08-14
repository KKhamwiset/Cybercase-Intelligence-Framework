import type { ReactNode } from "react";
import type {
  ChatBaselineExtraction,
  ChatDemoExtraction,
  ChatExtraction,
} from "@/lib/api";
import { FailedChatExtractionState } from "./ChatEvidenceState";

interface ChatExtractionSummaryProps {
  extraction: ChatExtraction;
  onOpenChat: () => void;
}

export function ChatExtractionSummary({
  extraction,
  onOpenChat,
}: ChatExtractionSummaryProps) {
  if (extraction.mode === "deterministic_demo") {
    return <LegacyExtractionSummary extraction={extraction} />;
  }
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

function LegacyExtractionSummary({
  extraction,
}: {
  extraction: ChatDemoExtraction;
}) {
  return (
    <SummaryShell
      eyebrow="Chat-reported candidates"
      title="Case information overview"
      description={extraction.disclaimer}
    >
      <div>
        <ExtractionList
          title="Case details"
          count={extraction.evidence.length}
          emptyMessage="No case detail found in this chat text yet."
        >
          {extraction.evidence.map((item) => (
            <li key={item.evidence_id} className="rounded-xl bg-white p-3">
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm font-bold text-[#171717]">{item.title}</p>
                <span className="shrink-0 text-[10px] font-bold uppercase tracking-[0.1em] text-[#8A8984]">
                  {item.evidence_id}
                </span>
              </div>
              <p className="mt-1 text-xs leading-5 text-[#6B6A66]">
                {item.description}
              </p>
              <ItemBadges />
            </li>
          ))}
        </ExtractionList>
      </div>
    </SummaryShell>
  );
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
      <div className="mb-4 rounded-xl border border-[#DEDCD5] bg-[#F4F3EF] p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h4 className="text-[10px] font-extrabold uppercase tracking-[0.14em] text-[#6B6A66]">
            Case summary
          </h4>
          <ItemBadges />
        </div>
        <p className="mt-2 text-sm leading-6 text-[#171717]">
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
            <li key={item.entity_id} className="rounded-xl bg-white p-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-bold text-[#171717]">{item.name}</p>
                  <p className="mt-1 text-xs text-[#6B6A66]">
                    {item.entity_type}
                    {item.reported_role ? ` · ${item.reported_role}` : ""}
                  </p>
                </div>
                <span className="shrink-0 text-[10px] font-bold uppercase tracking-[0.1em] text-[#8A8984]">
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
            <li key={item.evidence_id} className="rounded-xl bg-white p-3">
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm font-bold text-[#171717]">{item.title}</p>
                <span className="shrink-0 text-[10px] font-bold uppercase tracking-[0.1em] text-[#8A8984]">
                  {item.evidence_id}
                </span>
              </div>
              <p className="mt-1 text-xs leading-5 text-[#6B6A66]">
                {item.description}
              </p>
              <p className="mt-1 text-[11px] text-[#8A8984]">
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
            <li key={item.missing_id} className="rounded-xl bg-white p-3">
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm leading-5 text-[#171717]">
                  {item.description}
                </p>
                <span className="shrink-0 text-[10px] font-bold uppercase tracking-[0.1em] text-[#8A8984]">
                  {item.importance}
                </span>
              </div>
              <ItemBadges />
            </li>
          ))}
        </ExtractionList>
      </div>

      <div className="mt-4 rounded-xl border border-[#DEDCD5] bg-white p-4">
        <div className="flex items-center justify-between gap-3">
          <h4 className="text-[10px] font-extrabold uppercase tracking-[0.14em] text-[#6B6A66]">
            Warnings
          </h4>
          <span className="text-xs font-bold text-[#8A8984]">
            {extraction.warnings.length}
          </span>
        </div>
        {extraction.warnings.length > 0 ? (
          <ul className="mt-2 list-disc space-y-1 pl-5 text-xs leading-5 text-[#6B6A66]">
            {extraction.warnings.map((warning, index) => (
              <li key={`${warning}-${index}`}>{warning}</li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-xs leading-5 text-[#8A8984]">
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
      className="w-full rounded-2xl border border-[#C9C7BF] bg-[#FCFBF8] p-4 shadow-[0_4px_18px_rgba(23,23,23,0.05)] sm:p-5"
    >
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-[#DEDCD5] pb-3">
        <div>
          <p className="text-[10px] font-extrabold uppercase tracking-[0.16em] text-[#6B6A66]">
            {eyebrow}
          </p>
          <h3 className="mt-1 text-base font-extrabold tracking-tight text-[#171717]">
            {title}
          </h3>
        </div>
        <ItemBadges />
      </div>
      <p className="mt-3 text-xs leading-5 text-[#6B6A66]">{description}</p>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function ItemBadges() {
  return (
    <div className="mt-2 flex flex-wrap gap-1.5" aria-label="Extraction labels">
      <span className="rounded-full border border-[#C9C7BF] bg-[#F4F3EF] px-2 py-0.5 text-[9px] font-extrabold uppercase tracking-[0.1em] text-[#6B6A66]">
        Candidate
      </span>
      <span className="rounded-full border border-[#C9C7BF] bg-white px-2 py-0.5 text-[9px] font-extrabold uppercase tracking-[0.1em] text-[#6B6A66]">
        User-reported
      </span>
      <span className="rounded-full border border-[#C9C7BF] bg-white px-2 py-0.5 text-[9px] font-extrabold uppercase tracking-[0.1em] text-[#6B6A66]">
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
    <p className="mt-1 text-[11px] text-[#8A8984]">
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
    <div className="rounded-xl border border-[#DEDCD5] bg-[#F4F3EF] p-3">
      <div className="flex items-center justify-between gap-3">
        <h4 className="text-[10px] font-extrabold uppercase tracking-[0.14em] text-[#6B6A66]">
          {title}
        </h4>
        <span className="text-xs font-bold text-[#8A8984]">{count}</span>
      </div>
      {count > 0 ? (
        <ul className="mt-2 space-y-2">{children}</ul>
      ) : (
        <p className="mt-2 text-xs leading-5 text-[#8A8984]">{emptyMessage}</p>
      )}
    </div>
  );
}
