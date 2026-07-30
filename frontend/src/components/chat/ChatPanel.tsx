"use client";

import {
  useEffect,
  useRef,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import type { PersistedChatMessage, ThreadStatus } from "@/lib/api";
import { Icon } from "./icons";
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
  const endRef = useRef<HTMLDivElement>(null);
  const isBusy =
    phase === "querying" ||
    phase === "analyzing" ||
    threadStatus === "processing";
  const isAwaitingFollowUp =
    phase === "awaiting_followup" ||
    threadStatus === "awaiting_followup";
  const canSubmit = !isBusy && Boolean(input.trim());

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages, phase, error]);

  const handleComposerKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  };

  return (
    <section
      aria-label="Chat"
      className="flex min-h-0 flex-1 flex-col bg-[#F7F6F2]"
    >
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-8 sm:px-7 lg:px-10">
        <div className="mx-auto flex min-h-full w-full max-w-[800px] flex-col">
          {messages.length === 0 ? (
            <div className="my-auto max-w-xl py-14 text-left sm:py-20">
              <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#171717] text-white shadow-sm">
                <Icon name="chat" className="h-6 w-6" />
              </span>
              <p className="mt-8 text-[10px] font-extrabold uppercase tracking-[0.18em] text-[#6B6A66]">
                Investigation workspace
              </p>
              <h2 className="mt-3 text-3xl font-extrabold tracking-[-0.035em] text-[#171717] sm:text-4xl">
                Start an investigation
              </h2>
              <p className="mt-4 max-w-lg text-sm leading-6 text-[#6B6A66] sm:text-base sm:leading-7">
                Describe the incident. CyberCase restores this persisted
                conversation and shows only data returned by the backend.
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
                        message.role === "user" ? "text-[#C9C7BF]" : "text-[#6B6A66]"
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

      <footer className="shrink-0 border-t border-[#DEDCD5] bg-[#F7F6F2]/95 px-3 pb-[max(12px,env(safe-area-inset-bottom))] pt-3 sm:px-7 sm:py-4 lg:px-10">
        <form onSubmit={onSubmit} className="mx-auto max-w-[800px]">
          <div className="flex items-end gap-2 rounded-2xl border border-[#C9C7BF] bg-white p-2 shadow-[0_8px_30px_rgba(23,23,23,0.07)] transition-[border-color,box-shadow] duration-150 focus-within:border-[#171717] focus-within:shadow-[0_10px_34px_rgba(23,23,23,0.1)] focus-within:ring-2 focus-within:ring-[#171717]/10 motion-reduce:transition-none">
            <textarea
              value={input}
              onChange={(event) => onInputChange(event.target.value)}
              onKeyDown={handleComposerKeyDown}
              disabled={isBusy}
              rows={1}
              placeholder={
                isAwaitingFollowUp
                  ? "Answer the assistant’s follow-up question"
                  : "Describe the incident or evidence"
              }
              aria-label="Investigation message"
              className="max-h-36 min-h-11 flex-1 resize-y bg-transparent px-2 py-2.5 text-base leading-6 text-[#171717] outline-none placeholder:text-[#8A8984] disabled:cursor-wait disabled:text-[#8A8984]"
            />

            <button
              type="submit"
              disabled={!canSubmit}
              aria-label="Send message"
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[#171717] text-white outline-none transition-[background-color,transform] duration-150 hover:bg-black active:scale-[0.97] focus-visible:ring-2 focus-visible:ring-[#171717] focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-[#DEDCD5] disabled:text-[#8A8984] motion-reduce:transform-none motion-reduce:transition-none"
            >
              <Icon name="send" className="h-5 w-5" />
            </button>
          </div>

          <p className="mt-2 px-1 text-xs leading-5 text-[#6B6A66]">
            {isAwaitingFollowUp
              ? "This answer continues the active backend-managed follow-up."
              : "Messages are saved to the selected chat after the backend accepts them."}
          </p>
        </form>
      </footer>
    </section>
  );
}
