"use client";

import type { FormEvent, KeyboardEvent } from "react";

export interface FollowUpEntry {
  question: string;
  answer: string;
}

interface FollowUpModuleProps {
  question: string;
  rationale: string;
  answer: string;
  currentQuestion: number;
  totalQuestions: number;
  entries: FollowUpEntry[];
  isSubmitting: boolean;
  onAnswerChange: (answer: string) => void;
  onSubmit: () => void;
}

export default function FollowUpModule({
  question,
  rationale,
  answer,
  currentQuestion,
  totalQuestions,
  entries,
  isSubmitting,
  onAnswerChange,
  onSubmit,
}: FollowUpModuleProps) {
  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSubmit();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.ctrlKey && event.key === "Enter") {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  };

  const canSubmit = answer.trim().length > 0 && !isSubmitting;

  return (
    <div className="flex justify-start">
      <section
        aria-labelledby="follow-up-question"
        className="w-full max-w-[680px] rounded-2xl border border-gray-200 bg-white px-5 py-5 shadow-sm sm:px-6 sm:py-6"
      >
        <div className="flex flex-col gap-2 border-b border-gray-200 pb-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-[11px] font-extrabold uppercase tracking-[0.16em] text-gray-700">
            Assistant · Clarification
          </p>
          <p className="text-[11px] font-extrabold uppercase tracking-[0.14em] text-gray-500">
            Question {currentQuestion} of {totalQuestions}
          </p>
        </div>

        {entries.length > 0 && (
          <div className="mt-4 space-y-2" aria-label="Previous clarification answers">
            {entries.map((entry, index) => (
              <div
                key={`${entry.question}-${index}`}
                className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-3"
              >
                <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-gray-500">
                  Answered question {index + 1}
                </p>
                <p className="mt-1 text-sm font-semibold text-gray-900">
                  {entry.question}
                </p>
                <p className="mt-1 text-sm leading-6 text-gray-600">
                  {entry.answer}
                </p>
              </div>
            ))}
          </div>
        )}

        <div className="mt-5">
          <h2
            id="follow-up-question"
            className="text-lg font-extrabold leading-7 tracking-tight text-black sm:text-xl"
          >
            {question}
          </h2>
          <p className="mt-2 text-sm leading-6 text-gray-600">{rationale}</p>
        </div>

        <form onSubmit={handleSubmit} className="mt-5">
          <label
            htmlFor="follow-up-answer"
            className="text-sm font-bold text-gray-900"
          >
            Your answer
          </label>
          <textarea
            id="follow-up-answer"
            name="follow-up-answer"
            value={answer}
            onChange={(event) => onAnswerChange(event.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isSubmitting}
            required
            rows={4}
            placeholder="Add the evidence, system, or timeline details you know…"
            className="mt-2 min-h-28 w-full resize-y rounded-xl border border-gray-300 bg-white px-4 py-3 text-base leading-6 text-black outline-none transition focus:border-black focus:ring-2 focus:ring-black focus:ring-offset-2 disabled:cursor-wait disabled:bg-gray-100 disabled:text-gray-500"
          />

          <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs font-medium text-gray-500">
              Press Ctrl + Enter to send
            </p>
            <button
              type="submit"
              disabled={!canSubmit}
              className="min-h-11 w-full rounded-xl bg-black px-5 py-2.5 text-sm font-bold text-white transition hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2 active:scale-[0.99] disabled:cursor-not-allowed disabled:bg-gray-300 disabled:text-gray-600 sm:w-auto"
            >
              {isSubmitting ? "Sending answer…" : "Send answer"}
            </button>
          </div>

          <p className="sr-only" aria-live="polite" aria-atomic="true">
            {isSubmitting
              ? `Sending answer for question ${currentQuestion} of ${totalQuestions}.`
              : `Question ${currentQuestion} of ${totalQuestions} is ready for your answer.`}
          </p>
        </form>
      </section>
    </div>
  );
}
