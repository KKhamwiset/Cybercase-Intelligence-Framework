import type { ReactNode } from "react";
import type { ChatDemoExtraction } from "@/lib/api";

interface ChatExtractionSummaryProps {
  extraction: ChatDemoExtraction;
}

export function ChatExtractionSummary({
  extraction,
}: ChatExtractionSummaryProps) {
  return (
    <section
      aria-label="Unverified chat-reported candidates"
      className="w-full rounded-2xl border border-[#C9C7BF] bg-[#FCFBF8] p-4 shadow-[0_4px_18px_rgba(23,23,23,0.05)] sm:p-5"
    >
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-[#DEDCD5] pb-3">
        <div>
          <p className="text-[10px] font-extrabold uppercase tracking-[0.16em] text-[#6B6A66]">
            Chat-reported candidates
          </p>
          <h3 className="mt-1 text-base font-extrabold tracking-tight text-[#171717]">
            Evidence and timeline
          </h3>
        </div>
        <span className="rounded-full border border-[#C9C7BF] bg-white px-2.5 py-1 text-[10px] font-extrabold uppercase tracking-[0.12em] text-[#6B6A66]">
          Unverified extraction
        </span>
      </div>

      <p className="mt-3 text-xs leading-5 text-[#6B6A66]">
        {extraction.disclaimer}
      </p>

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <ExtractionList
          title="Evidence"
          count={extraction.evidence.length}
          emptyMessage="No evidence-like detail found in this chat text yet."
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
            </li>
          ))}
        </ExtractionList>

        <ExtractionList
          title="Timeline"
          count={extraction.timeline.length}
          emptyMessage="No date, time, or sequence marker found in this chat text yet."
        >
          {extraction.timeline.map((item) => (
            <li key={item.event_id} className="rounded-xl bg-white p-3">
              <p className="text-[10px] font-extrabold uppercase tracking-[0.1em] text-[#6B6A66]">
                {item.timestamp ?? "Sequence marker"}
              </p>
              <p className="mt-1 text-sm leading-5 text-[#171717]">
                {item.event}
              </p>
            </li>
          ))}
        </ExtractionList>
      </div>
    </section>
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
