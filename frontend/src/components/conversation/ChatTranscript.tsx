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
      <div className="flex min-h-[300px] flex-col items-center justify-center p-8 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#EAE8E1] text-lg font-black text-[#171717]">
          CC
        </div>
        <h3 className="mt-4 text-base font-extrabold text-[#171717]">
          Investigation Console
        </h3>
        <p className="mt-2 max-w-md text-xs leading-relaxed text-[#6B6A66]">
          Describe an incident, paste forensic logs, or query MITRE ATT&amp;CK tactics.
          CyberCase will retrieve graph context and extract candidate observables.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6 px-4 py-6 sm:px-6">
      {messages.map((message) => {
        const isUser = message.role === "user";
        return (
          <div
            key={message.id}
            className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}
          >
            <div className="flex items-center gap-2 mb-1.5 px-1">
              <span className="text-[10px] font-extrabold uppercase tracking-wider text-[#8A8984]">
                {isUser ? "Analyst" : "CyberCase AI"}
              </span>
              <span className="text-[10px] text-[#A8A7A1]">
                #{message.ordinal}
              </span>
            </div>

            <div
              className={`max-w-[85%] rounded-2xl px-4 py-3.5 shadow-[0_1px_3px_rgba(23,23,23,0.04)] sm:px-5 sm:py-4 ${
                isUser
                  ? "bg-[#171717] text-white"
                  : "border border-[#DEDCD5] bg-white text-[#171717]"
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
        <div className="flex items-center gap-3 px-2 text-xs font-semibold text-[#6B6A66]">
          <span className="flex h-2 w-2 rounded-full bg-[#171717] animate-ping" />
          <span>Analyzing threat telemetry &amp; traversing STIX graph...</span>
        </div>
      )}

      <div ref={bottomRef} aria-hidden="true" />
    </div>
  );
}
