"use client";

import type { FormEvent } from "react";
import type { PersistedChatMessage, ThreadStatus } from "@/lib/api";
import { ChatComposer } from "./ChatComposer";
import { ChatTranscript } from "./ChatTranscript";
import type { RunPhase } from "./types";

interface ChatPanelProps {
  messages: PersistedChatMessage[];
  input: string;
  threadStatus: ThreadStatus | null;
  phase: RunPhase;
  error: string | null;
  onInputChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}

export function ChatPanel({
  messages,
  input,
  threadStatus,
  phase,
  error,
  onInputChange,
  onSubmit,
}: ChatPanelProps) {
  const isBusy =
    phase === "querying" ||
    phase === "analyzing" ||
    threadStatus === "processing";
  const isAwaitingFollowUp =
    phase === "awaiting_followup" ||
    threadStatus === "awaiting_followup";

  return (
    <section
      aria-label="Chat"
      className="flex min-h-0 flex-1 flex-col bg-[#F7F6F2]"
    >
      <ChatTranscript
        messages={messages}
        threadStatus={threadStatus}
        phase={phase}
        error={error}
      />

      <ChatComposer
        input={input}
        isAwaitingFollowUp={isAwaitingFollowUp}
        isBusy={isBusy}
        onInputChange={onInputChange}
        onSubmit={onSubmit}
      />
    </section>
  );
}
