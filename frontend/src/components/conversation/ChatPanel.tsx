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
    <div className="flex h-full min-h-0 flex-1 flex-col overflow-hidden bg-canvas">
      {/* Transcript Scroll Area */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        <ChatTranscript messages={messages} isProcessing={isProcessing} />
      </div>

      {/* Error Alert */}
      {error && (
        <div className="mx-auto w-full max-w-3xl px-4 sm:px-6">
          <div
            role="alert"
            className="mb-3 rounded-xl border border-red-200 bg-red-50 p-3 text-xs font-medium text-red-800"
          >
            {error}
          </div>
        </div>
      )}

      {/* Input Area */}
      <div className="border-t border-line bg-canvas p-4 sm:p-6">
        <div className="mx-auto w-full max-w-3xl">
          {threadStatus === "answered" && (
            <div className="mb-3 flex items-center gap-2">
              <span className="text-[11px] font-bold text-ink-secondary">
                Next action:
              </span>
              <button
                type="button"
                onClick={() => onPostAnswerActionChange("ask")}
                className={`rounded-lg border px-2.5 py-1 text-xs font-bold transition-colors ${
                  postAnswerAction === "ask"
                    ? "border-charcoal bg-charcoal text-ivory"
                    : "border-line-strong bg-surface text-ink-secondary hover:bg-surface-hover"
                }`}
              >
                Ask question
              </button>
              <button
                type="button"
                onClick={() => onPostAnswerActionChange("add_case_info")}
                className={`rounded-lg border px-2.5 py-1 text-xs font-bold transition-colors ${
                  postAnswerAction === "add_case_info"
                    ? "border-charcoal bg-charcoal text-ivory"
                    : "border-line-strong bg-surface text-ink-secondary hover:bg-surface-hover"
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
