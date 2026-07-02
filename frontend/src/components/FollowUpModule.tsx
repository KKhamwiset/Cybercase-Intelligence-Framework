"use client";

import React, { useEffect, useRef, useState } from "react";
import { QueryResponse, resumeRag } from "@/lib/api";

interface FollowUpEntry {
  question: string;
  answer: string;
}

interface FollowUpModuleProps {
  question: string;
  sessionId: string;
  onResolved: (response: QueryResponse) => void;
  onError?: (error: string) => void;
}

export default function FollowUpModule({
  question,
  sessionId,
  onResolved,
  onError,
}: FollowUpModuleProps) {
  const [answer, setAnswer] = useState("");
  const [entries, setEntries] = useState<FollowUpEntry[]>([]);
  const [followUpOverride, setFollowUpOverride] = useState<{
    sourceQuestion: string;
    sourceSessionId: string;
    question: string;
    sessionId: string;
  } | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const activeQuestion =
    followUpOverride?.sourceQuestion === question &&
    followUpOverride.sourceSessionId === sessionId
      ? followUpOverride.question
      : question;
  const activeSessionId =
    followUpOverride?.sourceQuestion === question &&
    followUpOverride.sourceSessionId === sessionId
      ? followUpOverride.sessionId
      : sessionId;

  useEffect(() => {
    inputRef.current?.focus();
  }, [activeQuestion]);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [entries]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!answer.trim() || isSubmitting) {
      return;
    }

    const currentAnswer = answer;
    setAnswer("");
    setIsSubmitting(true);

    try {
      const response = await resumeRag(activeSessionId, currentAnswer);

      setEntries((previous) => [
        ...previous,
        { question: activeQuestion, answer: currentAnswer },
      ]);

      if (response.status === "followup") {
        setFollowUpOverride({
          sourceQuestion: question,
          sourceSessionId: sessionId,
          question: response.followup_question || "I need more information.",
          sessionId: response.session_id || activeSessionId,
        });
      } else {
        onResolved(response);
      }
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Unknown error during follow-up";
      console.error("[FollowUpModule] error:", message);
      onError?.(message);
      setAnswer(currentAnswer);
    } finally {
      setIsSubmitting(false);
    }
  };

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

        <form onSubmit={handleSubmit} className="space-y-4 p-5">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-black/10 bg-white text-sm font-black text-black">
              C
            </span>
            <p className="text-base font-black leading-relaxed text-black">
              {activeQuestion}
            </p>
          </div>

          <div className="relative">
            <textarea
              ref={inputRef}
              value={answer}
              onChange={(event) => setAnswer(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  handleSubmit(event);
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