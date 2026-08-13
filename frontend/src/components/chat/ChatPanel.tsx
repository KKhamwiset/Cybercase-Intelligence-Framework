"use client";

import type { FormEvent } from "react";
import type {
  ChatMessageAction,
  PersistedChatMessage,
  ThreadStatus,
} from "@/lib/api";
import { ChatComposer } from "./ChatComposer";
import { ChatTranscript } from "./ChatTranscript";
import type { RunPhase } from "./types";

interface ChatPanelProps {
  messages: PersistedChatMessage[];
  input: string;
  threadStatus: ThreadStatus | null;
  phase: RunPhase;
  error: string | null;
  postAnswerAction: ChatMessageAction | null;
  onInputChange: (value: string) => void;
  onPostAnswerActionChange: (action: ChatMessageAction) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}

export function ChatPanel({
  messages,
  input,
  threadStatus,
  phase,
  error,
  postAnswerAction,
  onInputChange,
  onPostAnswerActionChange,
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

      {threadStatus === "answered" && (
        <div
          aria-label="Post-answer action"
          className="border-t border-[#DEDCD5] bg-[#FCFBF8] px-4 py-3 sm:px-7 lg:px-10"
        >
          <p className="text-xs font-bold text-[#6B6A66]">
            Choose how to use the next message.
          </p>
          <div className="mt-2 flex flex-wrap gap-2" role="group">
            <button
              type="button"
              aria-pressed={postAnswerAction === "ask"}
              onClick={() => onPostAnswerActionChange("ask")}
              className={`min-h-10 rounded-lg border px-3 text-xs font-bold outline-none transition-colors focus-visible:ring-2 focus-visible:ring-[#171717] focus-visible:ring-offset-2 ${
                postAnswerAction === "ask"
                  ? "border-[#171717] bg-[#171717] text-white"
                  : "border-[#C9C7BF] bg-white text-[#171717] hover:border-[#171717]"
              }`}
            >
              Ask about the case
            </button>
            <button
              type="button"
              aria-pressed={postAnswerAction === "add_case_info"}
              onClick={() => onPostAnswerActionChange("add_case_info")}
              className={`min-h-10 rounded-lg border px-3 text-xs font-bold outline-none transition-colors focus-visible:ring-2 focus-visible:ring-[#171717] focus-visible:ring-offset-2 ${
                postAnswerAction === "add_case_info"
                  ? "border-[#171717] bg-[#171717] text-white"
                  : "border-[#C9C7BF] bg-white text-[#171717] hover:border-[#171717]"
              }`}
            >
              Add case information
            </button>
          </div>
        </div>
      )}

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
