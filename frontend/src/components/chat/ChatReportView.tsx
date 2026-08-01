"use client";

import { useState } from "react";
import type {
  ChatDemoExtraction,
  PersistedChatMessage,
} from "@/lib/api";
import {
  buildChatDemoReport,
  type ChatDemoReport,
} from "@/lib/chat-demo-report";
import { Icon } from "./icons";

interface ChatReportViewProps {
  threadTitle: string;
  messages: PersistedChatMessage[];
  latestExtraction: ChatDemoExtraction | null;
  onOpenChat: () => void;
}

interface GeneratedReport {
  sourceKey: string;
  report: ChatDemoReport;
}

export function ChatReportView({
  threadTitle,
  messages,
  latestExtraction,
  onOpenChat,
}: ChatReportViewProps) {
  const [generatedReport, setGeneratedReport] =
    useState<GeneratedReport | null>(null);
  const sourceKey = reportSourceKey(threadTitle, messages, latestExtraction);
  const report =
    generatedReport?.sourceKey === sourceKey ? generatedReport.report : null;
  const hasMessages = messages.length > 0;

  function handleGenerate(): void {
    if (!hasMessages) return;
    setGeneratedReport({
      sourceKey,
      report: buildChatDemoReport(messages, latestExtraction, threadTitle),
    });
  }

  return (
    <section
      id="workspace-report-panel"
      role="tabpanel"
      aria-label="Report generation"
      className="min-h-0 flex-1 overflow-y-auto bg-[#F7F6F2] px-4 py-8 sm:px-7 lg:px-10"
    >
      <div className="mx-auto w-full max-w-[980px]">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-2xl">
            <p className="text-[10px] font-extrabold uppercase tracking-[0.18em] text-[#6B6A66]">
              Report generation
            </p>
            <h1 className="mt-3 text-3xl font-extrabold tracking-[-0.035em] text-[#171717] sm:text-4xl">
              Demo report workspace
            </h1>
            <p className="mt-4 text-sm leading-6 text-[#6B6A66] sm:text-base sm:leading-7">
              Generate a deterministic, client-side report from the selected
              thread&apos;s persisted messages. This output is for demonstration
              and analyst review only.
            </p>
          </div>
          <span className="rounded-full border border-[#C9C7BF] bg-white px-3 py-1.5 text-[10px] font-extrabold uppercase tracking-[0.12em] text-[#6B6A66]">
            Demo only / Unverified
          </span>
        </div>

        <div className="mt-7 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={handleGenerate}
            disabled={!hasMessages}
            className="inline-flex min-h-11 items-center rounded-xl bg-[#171717] px-4 text-sm font-bold text-white outline-none transition-colors hover:bg-[#333333] focus-visible:ring-2 focus-visible:ring-[#171717] focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-[#E8E6E0] disabled:text-[#8A8984]"
          >
            Generate demo report
          </button>
          <button
            type="button"
            onClick={onOpenChat}
            className="inline-flex min-h-11 items-center rounded-xl border border-[#C9C7BF] bg-white px-4 text-sm font-bold text-[#171717] outline-none transition-colors hover:border-[#171717] hover:bg-[#FCFBF8] focus-visible:ring-2 focus-visible:ring-[#171717] focus-visible:ring-offset-2"
          >
            Return to Chat
          </button>
        </div>

        {!hasMessages ? (
          <div className="mt-8 max-w-2xl rounded-2xl border border-dashed border-[#C9C7BF] bg-[#FCFBF8] p-6 sm:p-8">
            <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#171717] text-white shadow-sm">
              <Icon name="report" className="h-6 w-6" />
            </span>
            <h2 className="mt-5 text-xl font-extrabold tracking-tight text-[#171717]">
              No persisted messages in this thread
            </h2>
            <p className="mt-3 text-sm leading-6 text-[#6B6A66]">
              Send and persist a chat message before generating the demo report.
              No report is generated for an empty thread.
            </p>
          </div>
        ) : report ? (
          <GeneratedReportView report={report} />
        ) : (
          <div className="mt-8 max-w-2xl rounded-2xl border border-[#DEDCD5] bg-[#FCFBF8] p-6 sm:p-8">
            <h2 className="text-xl font-extrabold tracking-tight text-[#171717]">
              Ready to generate
            </h2>
            <p className="mt-3 text-sm leading-6 text-[#6B6A66]">
              The report will remain limited to this selected thread. It will
              be marked incomplete and unverified when no persisted extraction
              is available.
            </p>
          </div>
        )}
      </div>
    </section>
  );
}

function GeneratedReportView({ report }: { report: ChatDemoReport }) {
  return (
    <article
      aria-label="Generated demo report"
      className="mt-8 rounded-2xl border border-[#C9C7BF] bg-[#FCFBF8] p-5 shadow-[0_4px_18px_rgba(23,23,23,0.05)] sm:p-8"
    >
      <header className="border-b border-[#DEDCD5] pb-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-[10px] font-extrabold uppercase tracking-[0.16em] text-[#6B6A66]">
            Selected thread
          </p>
          <span className="rounded-full border border-[#C9C7BF] bg-white px-2.5 py-1 text-[10px] font-extrabold uppercase tracking-[0.12em] text-[#6B6A66]">
            {report.incomplete ? "Incomplete / Unverified" : "Unverified demo"}
          </span>
        </div>
        <h2 className="mt-2 text-2xl font-extrabold tracking-[-0.03em] text-[#171717]">
          {report.threadTitle}
        </h2>
      </header>

      <div className="divide-y divide-[#DEDCD5]">
        {report.sections.map((section) => (
          <section key={section.heading} className="py-6 first:pt-7 last:pb-2">
            <h3 className="text-lg font-extrabold tracking-tight text-[#171717]">
              {section.heading}
            </h3>
            <div className="mt-3 space-y-3 text-sm leading-6 text-[#6B6A66]">
              {section.paragraphs.map((paragraph, index) => (
                <p key={`${section.heading}-paragraph-${index}`}>{paragraph}</p>
              ))}
            </div>
            {section.items.length > 0 && (
              <ul className="mt-4 list-disc space-y-2 pl-5 text-sm leading-6 text-[#171717]">
                {section.items.map((item, index) => (
                  <li key={`${section.heading}-item-${index}`}>{item}</li>
                ))}
              </ul>
            )}
          </section>
        ))}
      </div>
    </article>
  );
}

function reportSourceKey(
  threadTitle: string,
  messages: PersistedChatMessage[],
  extraction: ChatDemoExtraction | null,
): string {
  return JSON.stringify({
    threadTitle,
    messages: messages.map((message) => ({
      id: message.id,
      ordinal: message.ordinal,
      role: message.role,
      content: message.content,
      metadata_json: message.metadata_json,
    })),
    extraction,
  });
}
