"use client";

import type { ChatExtraction } from "@/lib/api";
import {
  FailedChatExtractionState,
  NoChatExtractionState,
} from "./ChatEvidenceState";

interface ChatTimelineViewProps {
  extraction: ChatExtraction | null;
  onOpenChat: () => void;
}

function CandidateBadges() {
  return (
    <div className="mt-2 flex flex-wrap gap-1.5" aria-label="Timeline labels">
      {['Candidate', 'User-reported', 'Unverified'].map((label) => (
        <span
          key={label}
          className="rounded-full border border-[#C9C7BF] bg-white px-2 py-0.5 text-[9px] font-extrabold uppercase tracking-[0.1em] text-[#6B6A66]"
        >
          {label}
        </span>
      ))}
    </div>
  );
}

export function ChatTimelineView({
  extraction,
  onOpenChat,
}: ChatTimelineViewProps) {
  let content;
  if (!extraction) {
    content = <NoChatExtractionState onOpenChat={onOpenChat} />;
  } else if (extraction.mode === "single_pass_llm" && extraction.status === "failed") {
    content = (
      <FailedChatExtractionState
        extraction={extraction}
        onOpenChat={onOpenChat}
      />
    );
  } else {
    const timeline = extraction.timeline;
    content = (
      <section
        aria-label="Candidate incident timeline"
        className="rounded-2xl border border-[#C9C7BF] bg-[#FCFBF8] p-4 shadow-[0_4px_18px_rgba(23,23,23,0.05)] sm:p-6"
      >
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-[#DEDCD5] pb-4">
          <div>
            <p className="text-[10px] font-extrabold uppercase tracking-[0.16em] text-[#6B6A66]">
              {extraction.mode === "deterministic_demo"
                ? "Legacy chat-reported candidates"
                : "Baseline LLM candidates"}
            </p>
            <h2 className="mt-1 text-lg font-extrabold tracking-tight text-[#171717]">
              Reported event sequence
            </h2>
          </div>
          <span className="text-sm font-bold text-[#8A8984]">
            {timeline.length} {timeline.length === 1 ? "event" : "events"}
          </span>
        </div>

        {timeline.length === 0 ? (
          <div className="mt-5 rounded-xl border border-dashed border-[#C9C7BF] bg-[#F4F3EF] p-5">
            <p className="text-sm font-bold text-[#171717]">
              No timeline events extracted
            </p>
            <p className="mt-2 text-xs leading-5 text-[#6B6A66]">
              The extraction is valid, but it contains no explicit date, time,
              or sequence marker for this chat.
            </p>
            <CandidateBadges />
          </div>
        ) : (
          <ol className="mt-5 space-y-3">
            {timeline.map((item, index) => {
              const baselineEvent = "timestamp_text" in item;
              const timestamp = baselineEvent
                ? item.timestamp_text ?? item.timestamp ?? "Timestamp unknown"
                : item.timestamp ?? "Sequence marker";
              return (
                <li
                  key={item.event_id}
                  className="grid gap-3 rounded-xl border border-[#DEDCD5] bg-white p-4 sm:grid-cols-[104px_minmax(0,1fr)] sm:p-5"
                >
                  <div>
                    <p className="text-[10px] font-extrabold uppercase tracking-[0.1em] text-[#8A8984]">
                      Event {index + 1}
                    </p>
                    <p className="mt-1 text-xs font-bold leading-5 text-[#171717] [overflow-wrap:anywhere]">
                      {timestamp}
                    </p>
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-bold leading-6 text-[#171717]">
                      {item.event}
                    </p>
                    {baselineEvent && item.actors.length > 0 && (
                      <p className="mt-1 text-xs leading-5 text-[#6B6A66]">
                        Actors: {item.actors.join(", ")}
                      </p>
                    )}
                    {baselineEvent && (
                      <p className="mt-1 text-[11px] capitalize text-[#8A8984]">
                        {item.status} · {item.confidence}
                      </p>
                    )}
                    <CandidateBadges />
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </section>
    );
  }

  return (
    <section
      id="workspace-extraction-panel"
      role="tabpanel"
      aria-label="Evidence timeline"
      className="min-h-0 flex-1 overflow-y-auto bg-[#F7F6F2] px-4 py-8 sm:px-7 lg:px-10"
    >
      <div className="mx-auto w-full max-w-[1120px]">
        <div className="max-w-2xl">
          <p className="text-[10px] font-extrabold uppercase tracking-[0.18em] text-[#6B6A66]">
            Timeline
          </p>
          <h1 className="mt-3 text-3xl font-extrabold tracking-[-0.035em] text-[#171717] sm:text-4xl">
            Incident chronology
          </h1>
          <p className="mt-4 text-sm leading-6 text-[#6B6A66] sm:text-base sm:leading-7">
            Review only the reported event sequence from this thread. Missing
            timestamps remain explicit and no forensic order is inferred.
          </p>
        </div>
        <div className="mt-8">{content}</div>
      </div>
    </section>
  );
}
