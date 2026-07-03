"use client";

import type { ChangeEvent, FormEvent, RefObject } from "react";

import FollowUpModule from "@/components/FollowUpModule";
import type { FollowUpEntry } from "@/components/FollowUpModule";
import type { ChatMessage, QueryResponse } from "@/lib/api";

export const SUGGESTED_QUESTIONS = [
  "Map this phishing incident to MITRE ATT&CK and identify supporting evidence.",
  "What evidence is still missing before generating a CyberCase incident report?",
];

type InvestigationChatPanelProps = {
  title: string;
  subtitle: string;
  emptyTitle: string;
  emptyDescription: string;
  messages: ChatMessage[];
  input: string;
  selectedFile: File | null;
  isLoading: boolean;
  followUpResponse: QueryResponse | null;
  currentSessionId: string | null;
  followUpAnswer: string;
  followUpEntries: FollowUpEntry[];
  isFollowUpSubmitting: boolean;
  isReportLoading: boolean;
  canGenerateReport: boolean;
  messagesEndRef: RefObject<HTMLDivElement | null>;
  fileInputRef: RefObject<HTMLInputElement | null>;
  onInputChange: (value: string) => void;
  onFileChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onClearFile: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onGenerateReport: () => void;
  onFollowUpAnswerChange: (answer: string) => void;
  onFollowUpSubmit: () => void;
};

export default function InvestigationChatPanel({
  title,
  subtitle,
  emptyTitle,
  emptyDescription,
  messages,
  input,
  selectedFile,
  isLoading,
  followUpResponse,
  currentSessionId,
  followUpAnswer,
  followUpEntries,
  isFollowUpSubmitting,
  isReportLoading,
  canGenerateReport,
  messagesEndRef,
  fileInputRef,
  onInputChange,
  onFileChange,
  onClearFile,
  onSubmit,
  onGenerateReport,
  onFollowUpAnswerChange,
  onFollowUpSubmit,
}: InvestigationChatPanelProps) {
  return (
    <section className="flex min-h-0 flex-col bg-[#f5f5f5]">
      <div className="flex h-16 shrink-0 items-center justify-between border-b border-black/10 bg-white px-4">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-black text-[10px] font-black text-white">
            CC
          </div>

          <div className="min-w-0">
            <p className="truncate text-sm font-black">{title}</p>
            <p className="truncate text-xs font-semibold text-neutral">
              {subtitle}
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={onGenerateReport}
          disabled={!canGenerateReport || isReportLoading}
          className="bg-black px-3 py-2 text-xs font-black text-white transition hover:bg-neutral-800 disabled:cursor-not-allowed disabled:bg-neutral-200 disabled:text-neutral"
        >
          {isReportLoading ? "Working" : canGenerateReport ? "Report" : "Need context"}
        </button>
      </div>

      <main className="min-h-0 flex-1 overflow-y-auto px-4 py-5">
        <div className="mx-auto max-w-3xl space-y-4">
          {messages.length === 0 ? (
            <div className="border border-black/15 bg-white p-5">
              <p className="mono-label">CyberCase Intelligence</p>

              <div className="mt-4 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <h1 className="text-2xl font-black tracking-tight">
                    {emptyTitle}
                  </h1>

                  <p className="mt-2 max-w-lg text-sm leading-6 text-neutral">
                    {emptyDescription}
                  </p>
                </div>

                <span className="border border-black/10 px-2 py-1 text-[11px] font-black uppercase text-neutral">
                  CyberCase AI
                </span>
              </div>

              <div className="mt-5 grid gap-2 sm:grid-cols-2">
                {SUGGESTED_QUESTIONS.map((question) => (
                  <button
                    key={question}
                    type="button"
                    onClick={() => onInputChange(question)}
                    className="rounded-md border border-black/10 bg-neutral-50 px-3 py-3 text-left text-sm font-semibold leading-5 transition hover:border-black hover:bg-white"
                  >
                    {question}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {messages.map((message, index) => (
            <div
              key={`${message.role}-${index}`}
              className={`flex items-end gap-2 ${
                message.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              {message.role === "assistant" ? (
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-black text-[10px] font-black text-white">
                  CC
                </div>
              ) : null}

              <div
                className={`max-w-[84%] border px-4 py-3 md:max-w-[76%] ${
                  message.role === "user"
                    ? "bg-black text-white"
                    : "border border-black/10 bg-white text-black"
                }`}
              >
                <div
                  className={`mb-1 text-[10px] font-black uppercase ${
                    message.role === "user" ? "text-white/60" : "text-neutral"
                  }`}
                >
                  {message.role === "user" ? "You" : "CyberCase AI"}
                </div>

                <p className="whitespace-pre-wrap text-sm font-medium leading-relaxed">
                  {message.content}
                </p>
              </div>

              {message.role === "user" ? (
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-black/10 bg-white text-xs font-black text-black">
                  Y
                </div>
              ) : null}
            </div>
          ))}

          {followUpResponse && followUpResponse.status === "followup" ? (
            <FollowUpModule
              question={
                followUpResponse.followup_question ||
                "I need more information about this incident."
              }
              answer={followUpAnswer}
              entries={followUpEntries}
              isSubmitting={isFollowUpSubmitting}
              onAnswerChange={onFollowUpAnswerChange}
              onSubmit={onFollowUpSubmit}
            />
          ) : null}

          {isLoading ? (
            <div className="flex justify-start">
              <div className="border border-black/15 bg-white px-5 py-4">
                <div className="flex space-x-2 py-2">
                  <div className="h-2 w-2 animate-bounce rounded-full bg-black" />
                  <div
                    className="h-2 w-2 animate-bounce rounded-full bg-black"
                    style={{ animationDelay: "150ms" }}
                  />
                  <div
                    className="h-2 w-2 animate-bounce rounded-full bg-black"
                    style={{ animationDelay: "300ms" }}
                  />
                </div>
              </div>
            </div>
          ) : null}

          <div ref={messagesEndRef} />
        </div>
      </main>

      <footer className="shrink-0 border-t border-black/10 bg-white p-3">
        <form onSubmit={onSubmit} className="mx-auto max-w-3xl space-y-2">
          {selectedFile ? (
            <div className="flex items-center justify-between gap-3 border border-black/10 bg-neutral-50 px-3 py-2 text-xs font-semibold">
              <span className="truncate">Attached: {selectedFile.name}</span>

              <button
                type="button"
                onClick={onClearFile}
                disabled={isLoading}
                className="font-black hover:underline disabled:opacity-50"
              >
                Clear
              </button>
            </div>
          ) : null}

          <div className="flex items-center gap-2 border border-black bg-white px-2 py-2 focus-within:border-black">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isLoading}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-black/10 text-lg font-black transition hover:bg-neutral-100 disabled:opacity-50"
              aria-label="Attach evidence file"
            >
              +
            </button>

            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
              onChange={onFileChange}
              disabled={isLoading}
              className="sr-only"
            />

            <input
              type="text"
              value={input}
              onChange={(event) => onInputChange(event.target.value)}
              placeholder={
                currentSessionId
                  ? "Answer the follow-up question..."
                  : selectedFile
                    ? "Ask what to analyze from this evidence..."
                    : "Describe the incident, provide evidence, or ask a question..."
              }
              disabled={isLoading}
              className="min-w-0 flex-1 bg-transparent px-2 py-2 text-sm outline-none placeholder:text-neutral disabled:opacity-50"
            />

            <button
              type="submit"
              disabled={isLoading || (!input.trim() && !selectedFile)}
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-black text-sm font-black text-white transition hover:bg-neutral-800 disabled:cursor-not-allowed disabled:bg-neutral-200 disabled:text-neutral"
              aria-label="Send investigation message"
            >
              &gt;
            </button>
          </div>
        </form>
      </footer>
    </section>
  );
}
