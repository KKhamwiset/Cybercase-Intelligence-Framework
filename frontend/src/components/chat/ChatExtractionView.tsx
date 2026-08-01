"use client";

import type { ChatDemoExtraction } from "@/lib/api";
import { ChatExtractionSummary } from "./ChatExtractionSummary";
import { Icon } from "./icons";

interface ChatExtractionViewProps {
  extraction: ChatDemoExtraction | null;
  onOpenChat: () => void;
}

export function ChatExtractionView({
  extraction,
  onOpenChat,
}: ChatExtractionViewProps) {
  return (
    <section
      id="workspace-extraction-panel"
      role="tabpanel"
      aria-label="Evidence and timeline"
      className="min-h-0 flex-1 overflow-y-auto bg-[#F7F6F2] px-4 py-8 sm:px-7 lg:px-10"
    >
      <div className="mx-auto w-full max-w-[980px]">
        <div className="max-w-2xl">
          <p className="text-[10px] font-extrabold uppercase tracking-[0.18em] text-[#6B6A66]">
            Evidence &amp; timeline
          </p>
          <h1 className="mt-3 text-3xl font-extrabold tracking-[-0.035em] text-[#171717] sm:text-4xl">
            Chat-reported candidates
          </h1>
          <p className="mt-4 text-sm leading-6 text-[#6B6A66] sm:text-base sm:leading-7">
            This view is scoped to the selected thread and shows only its latest
            assistant extraction. These are unverified chat-text candidates, not
            confirmed forensic evidence.
          </p>
        </div>

        {extraction ? (
          <div className="mt-8">
            <ChatExtractionSummary extraction={extraction} />
          </div>
        ) : (
          <div className="mt-8 max-w-2xl rounded-2xl border border-dashed border-[#C9C7BF] bg-[#FCFBF8] p-6 sm:p-8">
            <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#171717] text-white shadow-sm">
              <Icon name="evidence" className="h-6 w-6" />
            </span>
            <h2 className="mt-5 text-xl font-extrabold tracking-tight text-[#171717]">
              No extraction for this chat yet
            </h2>
            <p className="mt-3 text-sm leading-6 text-[#6B6A66]">
              Send a message and wait for an assistant response with deterministic
              demo metadata before reviewing chat-reported candidates here.
            </p>
            <button
              type="button"
              onClick={onOpenChat}
              className="mt-6 inline-flex min-h-11 items-center rounded-xl bg-[#171717] px-4 text-sm font-bold text-white outline-none transition-colors hover:bg-[#333333] focus-visible:ring-2 focus-visible:ring-[#171717] focus-visible:ring-offset-2"
            >
              Return to Chat
            </button>
          </div>
        )}
      </div>
    </section>
  );
}
