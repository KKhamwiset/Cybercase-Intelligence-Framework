"use client";

import type { ChatExtraction } from "@/lib/api";
import { CaseRelationshipGraph } from "./CaseRelationshipGraph";
import {
  FailedChatExtractionState,
  LegacyRelationshipsUnavailableState,
  NoChatExtractionState,
} from "./ChatEvidenceState";

interface ChatRelationshipsViewProps {
  extraction: ChatExtraction | null;
  onOpenChat: () => void;
}

export function ChatRelationshipsView({
  extraction,
  onOpenChat,
}: ChatRelationshipsViewProps) {
  let content;
  if (!extraction) {
    content = <NoChatExtractionState onOpenChat={onOpenChat} />;
  } else if (extraction.mode === "deterministic_demo") {
    content = (
      <LegacyRelationshipsUnavailableState onOpenChat={onOpenChat} />
    );
  } else if (extraction.status === "failed") {
    content = (
      <FailedChatExtractionState
        extraction={extraction}
        onOpenChat={onOpenChat}
      />
    );
  } else {
    content = (
      <CaseRelationshipGraph
        entities={extraction.entities}
        relationships={extraction.relationships}
      />
    );
  }

  return (
    <section
      id="workspace-extraction-panel"
      role="tabpanel"
      aria-label="Entity relationships"
      className="min-h-0 flex-1 overflow-y-auto bg-[#F7F6F2] px-4 py-8 sm:px-7 lg:px-10"
    >
      <div className="mx-auto w-full max-w-[1600px]">
        <div className="max-w-3xl">
          <p className="text-[10px] font-extrabold uppercase tracking-[0.18em] text-[#6B6A66]">
            Relationships
          </p>
          <h1 className="mt-3 text-3xl font-extrabold tracking-[-0.035em] text-[#171717] sm:text-4xl">
            Entity relationship graph
          </h1>
          <p className="mt-4 text-sm leading-6 text-[#6B6A66] sm:text-base sm:leading-7">
            Inspect explicit candidate relationships on a dedicated canvas.
            Connections remain user-reported and unverified, not forensic proof.
          </p>
        </div>
        <div className="mt-8">{content}</div>
      </div>
    </section>
  );
}
