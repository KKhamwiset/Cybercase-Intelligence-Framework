"use client";

import type { FormEvent } from "react";
import type { PersistedChatMessage, ThreadStatus } from "@/lib/api";
import { ChatComposer } from "./ChatComposer";
import { ChatTranscript } from "./ChatTranscript";
import type { RunPhase } from "./types";

interface ActiveFollowUp {
  question: string;
  entries: Array<{ question: string; answer: string }>;
}

interface ChatPanelProps {
  messages: PersistedChatMessage[];
  input: string;
  followUp: ActiveFollowUp | null;
  followUpAnswer: string;
  threadStatus: ThreadStatus | null;
  phase: RunPhase;
  error: string | null;
  onInputChange: (value: string) => void;
  onFollowUpAnswerChange: (value: string) => void;
  onFollowUpSubmit: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}

export function ChatPanel({
  messages,
  input,
  followUp,
  followUpAnswer,
  threadStatus,
  phase,
  error,
  onInputChange,
  onFollowUpAnswerChange,
  onFollowUpSubmit,
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
        followUp={followUp}
        followUpAnswer={followUpAnswer}
        threadStatus={threadStatus}
        phase={phase}
        error={error}
        onFollowUpAnswerChange={onFollowUpAnswerChange}
        onFollowUpSubmit={onFollowUpSubmit}
      />

      {!followUp && (
        <ChatComposer
          input={input}
          isAwaitingFollowUp={isAwaitingFollowUp}
          isBusy={isBusy}
          onInputChange={onInputChange}
          onSubmit={onSubmit}
        />
      )}
    </section>
  );
}
