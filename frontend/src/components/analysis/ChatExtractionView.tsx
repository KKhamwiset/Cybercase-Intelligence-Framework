"use client";

import type { ChatExtraction } from "@/lib/api";
import { NoChatExtractionState } from "./ChatExtractionState";
import { ChatExtractionSummary } from "./ChatExtractionSummary";

interface ChatExtractionViewProps {
  extraction: ChatExtraction | null;
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
      aria-label="Case details and timeline"
      className="min-h-0 flex-1 overflow-y-auto bg-[#F7F6F2] px-4 py-8 sm:px-7 lg:px-10"
    >
      <div className="mx-auto w-full max-w-[1120px]">
        <div className="max-w-2xl">
          <p className="text-[10px] font-extrabold uppercase tracking-[0.18em] text-[#6B6A66]">
            Case information overview
          </p>
          <h1 className="mt-3 text-3xl font-extrabold tracking-[-0.035em] text-[#171717] sm:text-4xl">
            Reported case details &amp; observables
          </h1>
          <p className="mt-4 text-sm leading-6 text-[#6B6A66] sm:text-base sm:leading-7">
            This view is scoped to the selected thread and shows only its latest
            assistant extraction. These are user-reported, unverified case statements
            and observables, not finalized forensic findings.
          </p>
        </div>

        {extraction ? (
          <div className="mt-8">
            <ChatExtractionSummary
              extraction={extraction}
              onOpenChat={onOpenChat}
            />
          </div>
        ) : (
          <div className="mt-8">
            <NoChatExtractionState onOpenChat={onOpenChat} />
          </div>
        )}
      </div>
    </section>
  );
}
