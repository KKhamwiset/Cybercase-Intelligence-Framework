"use client";

import { useEffect, useRef } from "react";
import type { PersistedChatMessage, ThreadStatus } from "@/lib/api";
import { Icon } from "./icons";
import type { RunPhase } from "./types";

interface ChatTranscriptProps {
  messages: PersistedChatMessage[];
  threadStatus: ThreadStatus | null;
  phase: RunPhase;
  error: string | null;
}

export function ChatTranscript({
  messages,
  threadStatus,
  phase,
  error,
}: ChatTranscriptProps) {
  const endRef = useRef<HTMLDivElement>(null);
  const isBusy =
    phase === "querying" ||
    phase === "analyzing" ||
    threadStatus === "processing";

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages, phase, error]);

  return (
    <div className="min-h-0 flex-1 overflow-y-auto px-4 py-8 sm:px-7 lg:px-10">
      <div className="mx-auto flex min-h-full w-full max-w-[800px] flex-col">
        {messages.length === 0 ? (
          <div className="my-auto max-w-xl py-14 text-left sm:py-20">
            <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#171717] text-white shadow-sm">
              <Icon name="chat" className="h-6 w-6" />
            </span>
            <p className="mt-8 text-[10px] font-extrabold uppercase tracking-[0.18em] text-[#6B6A66]">
              Chat workspace
            </p>
            <h2 className="mt-3 text-3xl font-extrabold tracking-[-0.035em] text-[#171717] sm:text-4xl">
              Start a conversation
            </h2>
            <p className="mt-4 max-w-lg text-sm leading-6 text-[#6B6A66] sm:text-base sm:leading-7">
              Ask a question or describe an incident. CyberCase restores this
              saved conversation and shows only data returned by the backend.
            </p>
          </div>
        ) : (
          <div className="space-y-8 py-2" aria-live="polite">
            {messages.map((message) => (
              <article
                key={message.id}
                className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`px-4 py-3 sm:px-5 sm:py-4 ${
                    message.role === "user"
                      ? "max-w-[88%] rounded-2xl rounded-br-md bg-[#171717] text-white shadow-sm sm:max-w-[72%]"
                      : "w-full border-l-2 border-[#171717] bg-white/55 text-[#171717] sm:px-6"
                  }`}
                >
                  <p
                    className={`mb-1 text-[10px] font-extrabold uppercase tracking-[0.16em] ${
                      message.role === "user"
                        ? "text-[#C9C7BF]"
                        : "text-[#6B6A66]"
                    }`}
                  >
                    {message.role === "user" ? "You" : "CyberCase"}
                  </p>
                  <p className="whitespace-pre-wrap break-words text-sm leading-6 sm:text-base">
                    {message.content}
                  </p>
                </div>
              </article>
            ))}

            {isBusy && (
              <div className="flex justify-start" role="status" aria-live="polite">
                <div className="flex items-center gap-3 border-l-2 border-[#171717] bg-white/60 px-5 py-3 text-sm font-semibold text-[#6B6A66]">
                  <span className="h-2 w-2 rounded-full bg-[#171717] motion-safe:animate-pulse" />
                  Waiting for the backend…
                </div>
              </div>
            )}

            {error && (
              <div
                role="alert"
                className="rounded-xl border border-[#B42318]/25 bg-[#B42318]/5 px-4 py-3 text-sm leading-6 text-[#7A271A]"
              >
                <p className="font-extrabold">Request failed</p>
                <p className="mt-1 break-words">{error}</p>
              </div>
            )}
          </div>
        )}

        <div ref={endRef} />
      </div>
    </div>
  );
}
