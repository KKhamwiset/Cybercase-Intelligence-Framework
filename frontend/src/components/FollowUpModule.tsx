"use client";

import React, { useState, useRef, useEffect } from "react";
import { resumeRag, QueryResponse } from "@/lib/api";

/**
 * Represents one completed follow-up exchange.
 */
interface FollowUpEntry {
  question: string;
  answer: string;
}

interface FollowUpModuleProps {
  /** The follow-up question the AI is asking. */
  question: string;
  /** The session_id returned alongside the follow-up. */
  sessionId: string;
  /**
   * Called once the follow-up loop ends with status === "completed".
   * The final answer lives in `response.answer`.
   */
  onResolved: (response: QueryResponse) => void;
  /**
   * Called if *every* attempt fails after retries.
   * Receives the last error message.
   */
  onError?: (error: string) => void;
}

/**
 * FollowUpModule — interactive UI for the AI's follow-up / clarification loop.
 *
 * The backend RAG agent may not have enough context on the first pass and will
 * return `{ status: "followup", followup_question, session_id }`. This component
 * presents that question, collects the user's answer, and sends it back via
 * `POST /api/v1/rag/resume` (the `resumeRag` API helper).  If the agent needs
 * yet another clarification the loop repeats until `status: "completed"`.
 *
 * Drop it into `chat/page.tsx` right below the last assistant message (or
 * wherever the ChatMessages are rendered) and pass it the props from the last
 * `QueryResponse` with `status === "followup"`.
 */
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

  // Auto-focus the input whenever a new question appears
  useEffect(() => {
    inputRef.current?.focus();
  }, [activeQuestion]);

  // Scroll exchange history into view
  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [entries]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!answer.trim() || isSubmitting) return;

    const currentAnswer = answer;
    setAnswer("");
    setIsSubmitting(true);

    try {
      const response = await resumeRag(activeSessionId, currentAnswer);

      // Record the completed exchange
      setEntries((prev) => [
        ...prev,
        { question: activeQuestion, answer: currentAnswer },
      ]);

      if (response.status === "followup") {
        // Another round — update the question and session, keep going
        setFollowUpOverride({
          sourceQuestion: question,
          sourceSessionId: sessionId,
          question: response.followup_question || "I need more information.",
          sessionId: response.session_id || activeSessionId,
        });
      } else {
        // Completed — hand the final answer to the parent
        onResolved(response);
      }
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Unknown error during follow-up";
      console.error("[FollowUpModule] error:", message);
      onError?.(message);
      // Restore the answer so the user can retry
      setAnswer(currentAnswer);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto my-4 animate-in fade-in slide-in-from-bottom-2 duration-300">
      {/* ── Card shell ── */}
      <div className="bg-white rounded-2xl border border-amber-300 shadow-sm overflow-hidden">

        {/* ── Header bar ── */}
        <div className="flex items-center gap-3 px-5 py-3 bg-amber-50 border-b border-amber-200">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-amber-100 text-amber-600">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <circle cx="12" cy="12" r="10" />
              <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
              <path d="M12 17h.01" />
            </svg>
          </span>
          <div>
            <p className="text-xs font-bold uppercase tracking-widest text-amber-700">
              Assistant needs more detail
            </p>
            <p className="text-[11px] text-amber-500 mt-0.5">
              {entries.length > 0
                ? `${entries.length} clarification${entries.length > 1 ? "s" : ""} answered`
                : "Please provide additional information to continue"}
            </p>
          </div>
        </div>

        {/* ── Past exchanges (collapsible history) ── */}
        {entries.length > 0 && (
          <div className="px-5 pt-4 space-y-3 border-b border-gray-100">
            {entries.map((entry, idx) => (
              <div key={idx} className="space-y-1.5">
                {/* The previously-asked question */}
                <div className="flex items-start gap-2">
                  <span className="shrink-0 mt-0.5 flex h-5 w-5 items-center justify-center rounded bg-gray-100 text-[9px] font-bold text-neutral">
                    Q
                  </span>
                  <p className="text-sm text-secondary font-medium leading-snug">
                    {entry.question}
                  </p>
                </div>
                {/* The user's answer */}
                <div className="flex items-start gap-2 pl-4">
                  <span className="shrink-0 mt-0.5 flex h-5 w-5 items-center justify-center rounded bg-primary text-[9px] font-bold text-white">
                    A
                  </span>
                  <p className="text-sm text-neutral leading-snug">
                    {entry.answer}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* ── Current question + answer form ── */}
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {/* Active follow-up question */}
          <div className="flex items-start gap-3">
            <span className="shrink-0 mt-0.5 flex h-7 w-7 items-center justify-center rounded-lg bg-primary text-white">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="m3 21 1.9-5.7a8.5 8.5 0 1 1 3.8 3.8z" />
              </svg>
            </span>
            <p className="text-base font-semibold text-primary leading-relaxed">
              {activeQuestion}
            </p>
          </div>

          {/* Answer textarea */}
          <div className="relative">
            <textarea
              ref={inputRef}
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit(e);
                }
              }}
              placeholder="Type your answer here…"
              disabled={isSubmitting}
              rows={3}
              className="w-full resize-none rounded-xl border border-amber-200 bg-amber-50/40 px-4 py-3 text-sm text-primary placeholder:text-amber-300 focus:border-primary focus:bg-white focus:outline-none focus:ring-1 focus:ring-amber-200 transition-all disabled:opacity-50"
            />
            <div className="absolute bottom-2 right-2 text-[10px] text-amber-300 pointer-events-none">
              Enter to send · Shift+Enter for new line
            </div>
          </div>

          {/* Submit button */}
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={isSubmitting || !answer.trim()}
              className="inline-flex items-center gap-2 rounded-xl bg-amber-500 hover:bg-amber-600 disabled:bg-gray-300 text-white text-sm font-semibold px-6 py-2.5 transition-colors disabled:cursor-not-allowed shadow-sm active:scale-[0.97] transform"
            >
              {isSubmitting ? (
                <>
                  <svg
                    className="animate-spin h-4 w-4"
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                    />
                  </svg>
                  Sending…
                </>
              ) : (
                <>
                  Send Answer
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="m22 2-7 20-4-9-9-4Z" />
                    <path d="M22 2 11 13" />
                  </svg>
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Invisible scroll anchor */}
      <div ref={scrollRef} />
    </div>
  );
}
