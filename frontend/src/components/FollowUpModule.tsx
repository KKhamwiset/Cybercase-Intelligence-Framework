"use client";

import React, { useEffect, useRef } from "react";

export interface FollowUpEntry {
  question: string;
  answer: string;
}

interface FollowUpModuleProps {
  question: string;
  answer: string;
  entries: FollowUpEntry[];
  isSubmitting: boolean;
  onAnswerChange: (answer: string) => void;
  onSubmit: () => void;
}

export default function FollowUpModule({
  question,
  answer,
  entries,
  isSubmitting,
  onAnswerChange,
  onSubmit,
}: FollowUpModuleProps) {
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, [question]);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [entries]);

  return (
    <div className="mx-auto my-4 w-full max-w-3xl">
      <div className="overflow-hidden rounded-lg border border-black/15 bg-white shadow-sm">
        <div className="flex items-center gap-3 border-b border-black/10 bg-neutral-50 px-5 py-3">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-black text-sm font-black text-white">
            ?
          </span>
          <div>
            <p className="text-xs font-black uppercase text-black">
              More detail required
            </p>
            <p className="mt-0.5 text-[11px] font-semibold text-neutral">
              {entries.length > 0
                ? `${entries.length} clarification${entries.length > 1 ? "s" : ""} answered`
                : "Answer the analyst prompt to continue"}
            </p>
          </div>
        </div>

        {entries.length > 0 ? (
          <div className="space-y-3 border-b border-black/10 px-5 pt-4">
            {entries.map((entry, index) => (
              <div key={`${entry.question}-${index}`} className="space-y-1.5">
                <div className="flex items-start gap-2">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded border border-black/10 bg-white text-[9px] font-black text-neutral">
                    Q
                  </span>
                  <p className="text-sm font-semibold leading-snug text-secondary">
                    {entry.question}
                  </p>
                </div>
                <div className="flex items-start gap-2 pl-4">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded bg-black text-[9px] font-black text-white">
                    A
                  </span>
                  <p className="text-sm leading-snug text-neutral">{entry.answer}</p>
                </div>
              </div>
            ))}
          </div>
        ) : null}

        <form
          onSubmit={(event) => {
            event.preventDefault();
            onSubmit();
          }}
          className="space-y-4 p-5"
        >
          <div className="flex items-start gap-3">
            <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-black/10 bg-white text-sm font-black text-black">
              C
            </span>
            <p className="text-base font-black leading-relaxed text-black">
              {question}
            </p>
          </div>

          <div className="relative">
            <textarea
              ref={inputRef}
              value={answer}
              onChange={(event) => onAnswerChange(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  onSubmit();
                }
              }}
              placeholder="Type your answer here..."
              disabled={isSubmitting}
              rows={3}
              className="w-full resize-none rounded-md border border-black/10 bg-neutral-50 px-4 py-3 text-sm text-black outline-none transition placeholder:text-neutral focus:border-black focus:bg-white disabled:opacity-50"
            />
            <div className="pointer-events-none absolute bottom-2 right-2 text-[10px] text-neutral">
              Enter to send / Shift+Enter for new line
            </div>
          </div>

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={isSubmitting || !answer.trim()}
              className="btn-primary"
            >
              {isSubmitting ? "Sending..." : "Send Answer"}
            </button>
          </div>
        </form>
      </div>
      <div ref={scrollRef} />
    </div>
  );
}
