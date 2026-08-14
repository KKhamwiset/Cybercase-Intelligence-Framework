"use client";

import type { FormEvent } from "react";
import type {
  ChatMessageAction,
  PersistedChatMessage,
  ThreadStatus,
} from "@/lib/api";
import type { RunPhase } from "@/components/common/types";
import { ChatComposer } from "./ChatComposer";
import { ChatTranscript } from "./ChatTranscript";

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
  const isProcessing = phase === "querying" || phase === "analyzing";

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col overflow-hidden bg-[#F7F6F2]">
      {/* Transcript Scroll Area */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        <ChatTranscript messages={messages} isProcessing={isProcessing} />
      </div>

      {/* Error Alert */}
      {error && (
        <div
          role="alert"
          className="mx-4 mb-3 rounded-xl border border-red-200 bg-red-50 p-3 text-xs font-medium text-red-800 sm:mx-6"
        >
          {error}
        </div>
      )}

      {/* Input Area */}
      <div className="border-t border-[#DEDCD5] bg-[#FCFBF8] p-4 sm:p-6">
        <div className="mx-auto max-w-3xl">
          {threadStatus === "answered" && (
            <div className="mb-3 flex items-center gap-2">
              <span className="text-[11px] font-bold text-[#6B6A66]">
                Next action:
              </span>
              <button
                type="button"
                onClick={() => onPostAnswerActionChange("ask")}
                className={`rounded-lg border px-2.5 py-1 text-xs font-bold transition-colors ${
                  postAnswerAction === "ask"
                    ? "border-[#171717] bg-[#171717] text-white"
                    : "border-[#C9C7BF] bg-white text-[#6B6A66] hover:bg-[#F4F3EF]"
                }`}
              >
                Ask question
              </button>
              <button
                type="button"
                onClick={() => onPostAnswerActionChange("add_case_info")}
                className={`rounded-lg border px-2.5 py-1 text-xs font-bold transition-colors ${
                  postAnswerAction === "add_case_info"
                    ? "border-[#171717] bg-[#171717] text-white"
                    : "border-[#C9C7BF] bg-white text-[#6B6A66] hover:bg-[#F4F3EF]"
                }`}
              >
                Add case info
              </button>
            </div>
          )}
          <ChatComposer
            input={input}
            isSubmitting={isProcessing}
            onInputChange={onInputChange}
            onSubmit={onSubmit}
          />
        </div>
      </div>
    </div>
  );
}
