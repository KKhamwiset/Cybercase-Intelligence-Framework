"use client";

import type { ChatExtraction } from "@/lib/api";
import {
  FailedChatExtractionState,
  NoChatExtractionState,
} from "@/components/analysis/ChatExtractionState";

interface ChatTimelineViewProps {
  extraction: ChatExtraction | null;
  onOpenChat: () => void;
}

export function ChatTimelineView({
  extraction,
  onOpenChat,
}: ChatTimelineViewProps) {
  let content;
  if (!extraction) {
    content = <NoChatExtractionState onOpenChat={onOpenChat} />;
  } else if (extraction.status === "failed") {
    content = (
      <FailedChatExtractionState
        extraction={extraction}
        onOpenChat={onOpenChat}
      />
    );
  } else {
    content = (
      <section
        aria-label="Reported timeline events"
        className="rounded-2xl border border-line-strong bg-surface p-4 shadow-[0_4px_18px_rgba(39,39,39,0.05)] sm:p-6"
      >
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-4">
          <div>
            <p className="text-[10px] font-extrabold uppercase tracking-[0.16em] text-ink-secondary">
              Chronological sequence
            </p>
            <h3 className="mt-1 text-base font-extrabold tracking-tight text-ink">
              Reported event sequence
            </h3>
          </div>
        </div>

        {extraction.timeline.length === 0 ? (
          <p className="mt-4 text-xs leading-5 text-ink-secondary">
            No timestamped or sequenced events were explicitly reported in this chat.
          </p>
        ) : (
          <ol className="mt-4 space-y-3">
            {extraction.timeline.map((item, index) => {
              const timestamp = item.timestamp_text ?? item.timestamp ?? "Timestamp unknown";
              return (
                <li
                  key={item.event_id}
                  className="grid gap-3 rounded-xl border border-line bg-surface p-4 sm:grid-cols-[104px_minmax(0,1fr)] sm:p-5"
                >
                  <div>
                    <p className="text-[10px] font-extrabold uppercase tracking-[0.1em] text-ink-secondary">
                      Event {index + 1}
                    </p>
                    <p className="mt-1 text-xs font-bold leading-5 text-ink [overflow-wrap:anywhere]">
                      {timestamp}
                    </p>
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-bold leading-6 text-ink">
                      {item.event}
                    </p>
                    {item.actors.length > 0 && (
                      <p className="mt-1 text-xs leading-5 text-ink-secondary">
                        Actors: {item.actors.join(", ")}
                      </p>
                    )}
                    <p className="mt-1 text-[11px] capitalize text-ink-secondary">
                      {item.status} · {item.confidence}
                    </p>
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
      id="workspace-timeline-panel"
      role="tabpanel"
      aria-label="Incident timeline"
      className="min-h-0 flex-1 overflow-y-auto bg-canvas px-4 py-8 sm:px-7 lg:px-10"
    >
      <div className="mx-auto w-full max-w-[1120px]">
        <div className="max-w-2xl">
          <p className="text-[10px] font-extrabold uppercase tracking-[0.18em] text-ink-secondary">
            Timeline
          </p>
          <h1 className="mt-3 text-3xl font-extrabold tracking-[-0.035em] text-ink sm:text-4xl">
            Incident chronology
          </h1>
          <p className="mt-4 text-sm leading-6 text-ink-secondary sm:text-base sm:leading-7">
            Review only the reported event sequence from this thread. Missing
            timestamps remain explicit and no forensic order is inferred.
          </p>
        </div>
        <div className="mt-8">{content}</div>
      </div>
    </section>
  );
}
