"use client";

import { useEffect, useRef } from "react";
import type { PersistedChatMessage } from "@/lib/api";
import { ChatMessageMarkdown } from "./ChatMessageMarkdown";

interface ChatTranscriptProps {
  messages: PersistedChatMessage[];
  isProcessing: boolean;
}

export function ChatTranscript({
  messages,
  isProcessing,
}: ChatTranscriptProps) {
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, isProcessing]);

  if (messages.length === 0) {
    return (
      <div className="flex h-full min-h-[400px] flex-col items-center justify-center p-8 text-center">
        <div className="mx-auto max-w-md">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-surface-hover text-lg font-black text-ink">
            CC
          </div>
          <h3 className="mt-4 text-base font-extrabold text-ink">
            Investigation Console
          </h3>
          <p className="mt-2 text-xs leading-relaxed text-ink-secondary">
            Describe an incident, paste forensic logs, or query MITRE ATT&amp;CK tactics.
            CyberCase will retrieve graph context and extract candidate observables.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6 px-4 py-6 sm:px-6">
      {messages.map((message) => {
        const isUser = message.role === "user";
        return (
          <div
            key={message.id}
            className={`flex flex-col ${isUser ? "items-end" : "items-start w-full"}`}
          >
            <div className="flex items-center gap-2 mb-1.5 px-1">
              <span className="text-[10px] font-extrabold uppercase tracking-wider text-ink-secondary">
                {isUser ? "Analyst" : "CyberCase AI"}
              </span>
              <span className="text-[10px] text-ink-secondary">
                #{message.ordinal}
              </span>
            </div>

            <div
              className={`rounded-2xl px-4 py-3.5 shadow-[0_1px_3px_rgba(39,39,39,0.04)] sm:px-5 sm:py-4 ${
                isUser
                  ? "max-w-[85%] bg-charcoal text-ivory"
                  : "w-full border border-line bg-surface text-ink"
              }`}
            >
              {isUser ? (
                <p className="whitespace-pre-wrap text-sm leading-relaxed">
                  {message.content}
                </p>
              ) : (
                <ChatMessageMarkdown content={message.content} />
              )}
            </div>
          </div>
        );
      })}

      {isProcessing && (
        <div className="flex items-center gap-3 px-2 text-xs font-semibold text-ink-secondary">
          <span className="flex h-2 w-2 rounded-full bg-charcoal animate-ping" />
          <span>Analyzing threat telemetry &amp; traversing STIX graph...</span>
        </div>
      )}

      <div ref={bottomRef} aria-hidden="true" />
    </div>
  );
}
