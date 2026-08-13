"use client";

import { useEffect, useState } from "react";
import {
  downloadChatReportPdf,
  generateChatReport,
  getApiErrorMessage,
  listChatReports,
  type ChatReportRead,
  type ChatStructuredReport,
  type ThreadStatus,
} from "@/lib/api";
import { Icon } from "./icons";

interface ChatReportViewProps {
  threadId: string | null;
  threadTitle: string;
  threadStatus: ThreadStatus | null;
  hasMessages: boolean;
  hasValidatedExtraction: boolean;
  onOpenChat: () => void;
}

export function ChatReportView({
  threadId,
  threadTitle,
  threadStatus,
  hasMessages,
  hasValidatedExtraction,
  onOpenChat,
}: ChatReportViewProps) {
  const [reports, setReports] = useState<ChatReportRead[]>([]);
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(Boolean(threadId));
  const [isGenerating, setIsGenerating] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [generationError, setGenerationError] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    if (!threadId) return () => controller.abort();

    void listChatReports(threadId, controller.signal)
      .then((savedReports) => {
        if (controller.signal.aborted) return;
        setReports(savedReports);
        setSelectedReportId(savedReports[0]?.report_id ?? null);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setLoadError(
          getApiErrorMessage(error, "Saved reports could not be loaded."),
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });

    return () => controller.abort();
  }, [threadId]);

  const selectedReport =
    reports.find((report) => report.report_id === selectedReportId) ??
    reports[0] ??
    null;
  const canGenerate =
    Boolean(threadId) &&
    hasMessages &&
    (threadStatus === "idle" || threadStatus === "answered") &&
    hasValidatedExtraction &&
    !isGenerating;

  async function handleGenerate(): Promise<void> {
    if (!threadId || !canGenerate) return;
    setIsGenerating(true);
    setGenerationError(null);
    setDownloadError(null);
    try {
      const generated = await generateChatReport(threadId, reportRequestKey());
      setReports((current) => [
        generated,
        ...current.filter((report) => report.report_id !== generated.report_id),
      ]);
      setSelectedReportId(generated.report_id);
    } catch (error: unknown) {
      setGenerationError(
        getApiErrorMessage(error, "The report could not be generated."),
      );
    } finally {
      setIsGenerating(false);
    }
  }

  async function handleDownloadPdf(report: ChatReportRead): Promise<void> {
    if (
      !threadId ||
      report.persistence_status !== "completed" ||
      !report.report ||
      isDownloading
    ) {
      return;
    }
    setIsDownloading(true);
    setDownloadError(null);
    try {
      const blob = await downloadChatReportPdf(threadId, report.report_id);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `cybercase-report-v${report.version_number}.pdf`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (error: unknown) {
      setDownloadError(
        getApiErrorMessage(error, "The PDF could not be downloaded."),
      );
    } finally {
      setIsDownloading(false);
    }
  }

  return (
    <section
      id="workspace-report-panel"
      role="tabpanel"
      aria-label="Report generation"
      className="min-h-0 flex-1 overflow-y-auto bg-[#F7F6F2] px-4 py-8 sm:px-7 lg:px-10"
    >
      <div className="mx-auto w-full max-w-[1080px]">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl">
            <p className="text-[10px] font-extrabold uppercase tracking-[0.18em] text-[#6B6A66]">
              Evidence &amp; timeline
            </p>
            <h1 className="mt-3 text-3xl font-extrabold tracking-[-0.035em] text-[#171717] sm:text-4xl">
              Digital-forensics report
            </h1>
            <p className="mt-4 text-sm leading-6 text-[#6B6A66] sm:text-base sm:leading-7">
              Generate one durable, backend-validated report from this chat&apos;s
              user-authored case messages, validated extraction, and persisted
              MITRE mapping rows.
            </p>
          </div>
          <span className="rounded-full border border-[#C9C7BF] bg-white px-3 py-1.5 text-[10px] font-extrabold uppercase tracking-[0.12em] text-[#6B6A66]">
            Provisional / Unverified
          </span>
        </div>

        <div className="mt-7 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => void handleGenerate()}
            disabled={!canGenerate}
            className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-[#171717] px-4 text-sm font-bold text-white outline-none transition-colors hover:bg-[#333333] focus-visible:ring-2 focus-visible:ring-[#171717] focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-[#E8E6E0] disabled:text-[#8A8984]"
          >
            {isGenerating && (
              <span
                className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white"
                aria-hidden="true"
              />
            )}
            {isGenerating ? "Generating report..." : "Generate report"}
          </button>
          <button
            type="button"
            onClick={onOpenChat}
            className="inline-flex min-h-11 items-center rounded-xl border border-[#C9C7BF] bg-white px-4 text-sm font-bold text-[#171717] outline-none transition-colors hover:border-[#171717] hover:bg-[#FCFBF8] focus-visible:ring-2 focus-visible:ring-[#171717] focus-visible:ring-offset-2"
          >
            Return to Chat
          </button>
        </div>

        <div className="mt-5 rounded-xl border border-[#DEDCD5] bg-[#FCFBF8] px-4 py-3 text-sm leading-6 text-[#6B6A66]">
          {readinessMessage({
            hasMessages,
            hasValidatedExtraction,
            threadId,
            threadStatus,
          })}
        </div>

        {loadError && <InlineError message={loadError} />}
        {generationError && <InlineError message={generationError} />}
        {downloadError && <InlineError message={downloadError} />}

        {isLoading ? (
          <div className="mt-8 rounded-2xl border border-[#DEDCD5] bg-[#FCFBF8] p-6 text-sm text-[#6B6A66]">
            Loading saved report versions...
          </div>
        ) : reports.length > 0 ? (
          <div className="mt-8 grid gap-6 lg:grid-cols-[220px_minmax(0,1fr)]">
            <aside className="rounded-2xl border border-[#DEDCD5] bg-[#FCFBF8] p-4">
              <p className="text-[10px] font-extrabold uppercase tracking-[0.16em] text-[#6B6A66]">
                Saved versions
              </p>
              <div className="mt-3 space-y-2" aria-label="Saved report versions">
                {reports.map((report) => (
                  <button
                    key={report.report_id}
                    type="button"
                    onClick={() => setSelectedReportId(report.report_id)}
                    className={`w-full rounded-xl border px-3 py-3 text-left outline-none transition-colors focus-visible:ring-2 focus-visible:ring-[#171717] ${
                      report.report_id === selectedReport?.report_id
                        ? "border-[#171717] bg-[#171717] text-white"
                        : "border-[#DEDCD5] bg-white text-[#171717] hover:border-[#171717]"
                    }`}
                  >
                    <span className="block text-sm font-extrabold">
                      Version {report.version_number}
                    </span>
                    <span
                      className={`mt-1 block text-[10px] font-bold uppercase tracking-[0.1em] ${
                        report.report_id === selectedReport?.report_id
                          ? "text-white/70"
                          : "text-[#6B6A66]"
                      }`}
                    >
                      {report.persistence_status === "completed"
                        ? "Validated output"
                        : "Generation failed"}
                    </span>
                  </button>
                ))}
              </div>
            </aside>
            {selectedReport && (
              <PersistedReportCard
                report={selectedReport}
                threadTitle={threadTitle}
                isDownloading={isDownloading}
                onDownloadPdf={() => void handleDownloadPdf(selectedReport)}
              />
            )}
          </div>
        ) : (
          <div className="mt-8 max-w-3xl rounded-2xl border border-dashed border-[#C9C7BF] bg-[#FCFBF8] p-6 sm:p-8">
            <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#171717] text-white shadow-sm">
              <Icon name="report" className="h-6 w-6" />
            </span>
            <h2 className="mt-5 text-xl font-extrabold tracking-tight text-[#171717]">
              No saved report for this chat
            </h2>
            <p className="mt-3 text-sm leading-6 text-[#6B6A66]">
              Complete the chat and wait for the validated baseline extraction,
              then generate a report. Previous report attempts will remain
              available here as versioned history.
            </p>
          </div>
        )}
      </div>
    </section>
  );
}

function PersistedReportCard({
  report,
  threadTitle,
  isDownloading,
  onDownloadPdf,
}: {
  report: ChatReportRead;
  threadTitle: string;
  isDownloading: boolean;
  onDownloadPdf: () => void;
}) {
  return (
    <article
      aria-label="Persisted report"
      className="min-w-0 rounded-2xl border border-[#C9C7BF] bg-[#FCFBF8] p-5 shadow-[0_4px_18px_rgba(23,23,23,0.05)] sm:p-8"
    >
      <header className="border-b border-[#DEDCD5] pb-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-[10px] font-extrabold uppercase tracking-[0.16em] text-[#6B6A66]">
            Version {report.version_number} · Backend persisted
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full border border-[#C9C7BF] bg-white px-2.5 py-1 text-[10px] font-extrabold uppercase tracking-[0.12em] text-[#6B6A66]">
              {report.persistence_status === "completed"
                ? "Provisional / Unverified"
                : "Generation failed"}
            </span>
            {report.persistence_status === "completed" && report.report && (
              <button
                type="button"
                onClick={onDownloadPdf}
                disabled={isDownloading}
                className="rounded-full border border-[#171717] bg-[#171717] px-2.5 py-1 text-[10px] font-extrabold uppercase tracking-[0.12em] text-white transition-colors hover:bg-[#333333] disabled:cursor-wait disabled:opacity-60"
              >
                {isDownloading ? "Preparing PDF..." : "Download PDF"}
              </button>
            )}
          </div>
        </div>
        <h2 className="mt-2 text-2xl font-extrabold tracking-[-0.03em] text-[#171717]">
          {report.report?.title ?? threadTitle}
        </h2>
        <p className="mt-2 text-xs text-[#6B6A66]">
          Extraction {report.extraction_version} · {report.model}
        </p>
      </header>

      {report.persistence_status === "failed" || !report.report ? (
        <ReportFailure report={report} />
      ) : (
        <StructuredReportView report={report.report} />
      )}
    </article>
  );
}

function StructuredReportView({ report }: { report: ChatStructuredReport }) {
  return (
    <>
      <div className="divide-y divide-[#DEDCD5]">
        {report.sections.map((section) => {
          const claims = report.claims.filter(
            (claim) => claim.section_id === section.section_id,
          );
          return (
            <section key={section.section_id} className="py-6 first:pt-7 last:pb-2">
              <h3 className="text-lg font-extrabold tracking-tight text-[#171717]">
                {section.heading}
              </h3>
              <div className="mt-3 space-y-3 text-sm leading-6 text-[#6B6A66]">
                {section.paragraphs.map((paragraph, index) => (
                  <p key={`${section.section_id}-paragraph-${index}`}>{paragraph}</p>
                ))}
              </div>
              {section.items.length > 0 && (
                <ul className="mt-4 list-disc space-y-2 pl-5 text-sm leading-6 text-[#171717]">
                  {section.items.map((item, index) => (
                    <li key={`${section.section_id}-item-${index}`}>{item}</li>
                  ))}
                </ul>
              )}
              {claims.length > 0 && (
                <div className="mt-5 space-y-3">
                  {claims.map((claim) => (
                    <div
                      key={claim.claim_id}
                      className="rounded-xl border border-[#DEDCD5] bg-white p-3"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-[10px] font-extrabold uppercase tracking-[0.1em] text-[#6B6A66]">
                          {claim.claim_id}
                        </span>
                        <span className="rounded-full border border-[#DEDCD5] px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.08em] text-[#6B6A66]">
                          {claim.support_type.replaceAll("_", " ")}
                        </span>
                      </div>
                      <p className="mt-2 text-sm leading-6 text-[#171717]">{claim.text}</p>
                    </div>
                  ))}
                </div>
              )}
            </section>
          );
        })}
      </div>
      {report.limitations.length > 0 && (
        <div className="mt-6 border-t border-[#DEDCD5] pt-5">
          <h3 className="text-sm font-extrabold uppercase tracking-[0.12em] text-[#6B6A66]">
            Report limitations
          </h3>
          <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-6 text-[#6B6A66]">
            {report.limitations.map((limitation, index) => (
              <li key={`limitation-${index}`}>{limitation}</li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}

function ReportFailure({ report }: { report: ChatReportRead }) {
  return (
    <div className="mt-6 rounded-xl border border-[#F0B8B2] bg-[#FFF6F4] p-4">
      <h3 className="text-sm font-extrabold text-[#B42318]">
        Report generation failed
      </h3>
      <p className="mt-2 text-sm leading-6 text-[#6B6A66]">
        {report.failure_message ?? "The backend did not produce a validated report."}
      </p>
      {report.failure_code && (
        <p className="mt-2 text-xs font-bold uppercase tracking-[0.1em] text-[#B42318]">
          Failure code: {report.failure_code}
        </p>
      )}
      {report.validation_errors.length > 0 && (
        <ul className="mt-3 list-disc space-y-1 pl-5 text-xs leading-5 text-[#6B6A66]">
          {report.validation_errors.map((error, index) => (
            <li key={`validation-error-${index}`}>{error}</li>
          ))}
        </ul>
      )}
      <p className="mt-4 text-sm font-semibold text-[#171717]">
        Resolve the issue, then generate another version. This failed attempt is
        preserved in report history.
      </p>
    </div>
  );
}

function InlineError({ message }: { message: string }) {
  return (
    <div className="mt-5 rounded-xl border border-[#F0B8B2] bg-[#FFF6F4] px-4 py-3 text-sm leading-6 text-[#B42318]">
      {message}
    </div>
  );
}

function readinessMessage({
  hasMessages,
  hasValidatedExtraction,
  threadId,
  threadStatus,
}: {
  hasMessages: boolean;
  hasValidatedExtraction: boolean;
  threadId: string | null;
  threadStatus: ThreadStatus | null;
}): string {
  if (!threadId || !hasMessages) {
    return "A persisted chat message is required before a report can be generated.";
  }
  if (threadStatus === "processing") {
    return "The chat is still processing. Wait for the terminal answer before generating a report.";
  }
  if (threadStatus === "awaiting_followup") {
    return "Answer the pending clarification in Chat before generating a report.";
  }
  if (threadStatus === "failed") {
    return "The latest chat response failed. Resolve it before generating a report.";
  }
  if (!hasValidatedExtraction) {
    return "A validated baseline extraction is not available yet. Complete a terminal chat answer first.";
  }
  return "Ready. The backend will freeze this thread snapshot and persist the validated report version.";
}

function reportRequestKey(): string | undefined {
  if (typeof globalThis.crypto?.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }
  return `report-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
