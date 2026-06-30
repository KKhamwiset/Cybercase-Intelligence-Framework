"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent, FormEvent, ReactNode } from "react";
import {
  chatContinue,
  generateReport,
  queryRagFile,
  resumeRag,
  resumeReport,
} from "@/lib/api";
import type {
  ChatMessage,
  CyberCaseReport,
  QueryResponse,
  ReportType,
  ReportWorkflowResponse,
} from "@/lib/api";
import Link from "next/link";
import FollowUpModule from "@/components/FollowUpModule";

const REPORT_TYPES: { value: ReportType; label: string }[] = [
  { value: "overview", label: "Overview" },
  { value: "subject", label: "Subject" },
  { value: "timeline", label: "Timeline" },
  { value: "vulnerability", label: "Vulnerability" },
];

function buildReportTranscript(messages: ChatMessage[]): string {
  const userTurns = messages
    .filter((message) => message.role === "user")
    .map((message, index) => `User turn ${index + 1}:\n${message.content.trim()}`)
    .join("\n\n");

  const assistantTurns = messages
    .filter((message) => message.role === "assistant")
    .map((message, index) => `Assistant turn ${index + 1}:\n${message.content.trim()}`)
    .join("\n\n");

  return [
    "Generate a CyberCase preliminary report from this chat transcript.",
    "Treat user turns as submitted case details. Treat assistant turns as analysis context that still requires evidence review.",
    "",
    "User-provided case details:",
    userTurns || "No user case details captured.",
    "",
    "Assistant analysis context:",
    assistantTurns || "No assistant analysis captured.",
  ].join("\n");
}

function reportCompleteness(reportWorkflow: ReportWorkflowResponse | null) {
  return (
    reportWorkflow?.completeness ??
    reportWorkflow?.report?.case_information_completeness ??
    null
  );
}

function statusClass(value: string): string {
  if (value === "confirmed" || value === "approved") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  if (value === "reported" || value === "reviewed" || value === "ai_generated") {
    return "border-sky-200 bg-sky-50 text-sky-700";
  }
  if (value === "inferred") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  return "border-gray-200 bg-gray-50 text-neutral";
}

function StatusBadge({ value }: { value: string }) {
  return (
    <span className={`inline-flex rounded-md border px-2 py-1 text-[11px] font-bold uppercase ${statusClass(value)}`}>
      {value.replace("_", " ")}
    </span>
  );
}

function ReportSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="border-t border-gray-200 px-5 py-5">
      <h3 className="mb-3 text-xs font-bold uppercase tracking-widest text-neutral">
        {title}
      </h3>
      {children}
    </section>
  );
}

function EmptyReportState() {
  return (
    <div className="flex min-h-64 items-center justify-center px-6 text-center">
      <div>
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-lg border border-gray-200 bg-gray-50 text-primary">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="22"
            height="22"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" />
            <path d="M14 2v4a2 2 0 0 0 2 2h4" />
            <path d="M10 13h4" />
            <path d="M10 17h6" />
          </svg>
        </div>
        <p className="mt-4 text-sm font-semibold text-primary">No report yet.</p>
      </div>
    </div>
  );
}

function ReportContent({ report }: { report: CyberCaseReport }) {
  return (
    <div>
      <section className="px-5 pb-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-widest text-neutral">
              {report.report_type} report
            </p>
            <h2 className="mt-2 text-lg font-extrabold leading-snug text-primary">
              {report.title}
            </h2>
          </div>
          <StatusBadge value={report.review_status} />
        </div>
        <p className="mt-4 text-sm leading-6 text-secondary">
          {report.executive_case_summary}
        </p>
      </section>

      <ReportSection title="Completeness">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-semibold text-primary">
              {report.case_information_completeness.status}
            </p>
            <p className="mt-1 text-xs text-neutral">
              {report.case_information_completeness.missing_fields.length
                ? report.case_information_completeness.missing_fields.join(", ")
                : "All required preliminary fields are present."}
            </p>
          </div>
          <span className="text-3xl font-black text-primary">
            {report.case_information_completeness.percentage}%
          </span>
        </div>
        <div className="mt-4 h-2 overflow-hidden rounded bg-gray-100">
          <div
            className="h-full bg-primary"
            style={{ width: `${report.case_information_completeness.percentage}%` }}
          />
        </div>
      </ReportSection>

      <ReportSection title="Indicators">
        {report.evidence_and_indicators_table.length ? (
          <div className="space-y-3">
            {report.evidence_and_indicators_table.slice(0, 6).map((indicator) => (
              <div
                key={indicator.indicator_id}
                className="rounded-md border border-gray-200 bg-gray-50 p-3"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[11px] font-bold uppercase text-neutral">
                    {indicator.indicator_type}
                  </span>
                  <StatusBadge value={indicator.status} />
                </div>
                <p className="mt-2 break-all text-sm font-semibold text-primary">
                  {indicator.value}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-neutral">No indicators listed.</p>
        )}
      </ReportSection>

      <ReportSection title="MITRE ATT&CK">
        {report.mitre_attack_assessment.length ? (
          <div className="space-y-3">
            {report.mitre_attack_assessment.slice(0, 5).map((mapping) => (
              <div key={mapping.technique_id} className="rounded-md border border-gray-200 p-3">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <p className="text-sm font-bold text-primary">
                    {mapping.technique_id} {mapping.technique_name}
                  </p>
                  <StatusBadge value={mapping.mapping_status} />
                </div>
                <p className="mt-2 text-xs leading-5 text-secondary">
                  {mapping.justification}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-neutral">No supported mapping yet.</p>
        )}
      </ReportSection>

      <ReportSection title="Next Steps">
        {report.investigation_next_steps.length ? (
          <ul className="space-y-2 text-sm leading-6 text-secondary">
            {report.investigation_next_steps.slice(0, 6).map((step) => (
              <li key={step} className="flex gap-2">
                <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                <span>{step}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-neutral">No next steps listed.</p>
        )}
      </ReportSection>
    </div>
  );
}

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [followUpResponse, setFollowUpResponse] = useState<QueryResponse | null>(null);
  const [reportType, setReportType] = useState<ReportType>("overview");
  const [reportWorkflow, setReportWorkflow] = useState<ReportWorkflowResponse | null>(null);
  const [latestRetrievalContextId, setLatestRetrievalContextId] = useState("");
  const [reportFollowupAnswer, setReportFollowupAnswer] = useState("");
  const [reportSourceCount, setReportSourceCount] = useState(0);
  const [isReportLoading, setIsReportLoading] = useState(false);
  const [reportError, setReportError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const report = reportWorkflow?.report ?? null;
  const completeness = reportCompleteness(reportWorkflow);
  const hasMessages = messages.length > 0;
  const reportIsStale = reportWorkflow !== null && messages.length !== reportSourceCount;
  const reportButtonLabel = reportWorkflow ? "Regenerate" : "Generate";
  const chatTranscript = useMemo(() => buildReportTranscript(messages), [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if ((!input.trim() && !selectedFile) || isLoading) {
      return;
    }

    const currentInput = input;
    const currentFile = selectedFile;
    const userMessage: ChatMessage = {
      role: "user",
      content: currentFile
        ? `${currentInput || "Analyze this document"}\n\nAttached file: ${currentFile.name}`
        : currentInput,
    };

    setMessages((previous) => [...previous, userMessage]);
    setInput("");
    setSelectedFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
    setIsLoading(true);

    try {
      let response: QueryResponse;
      if (currentSessionId) {
        response = await resumeRag(currentSessionId, currentInput);
      } else if (currentFile) {
        response = await queryRagFile(currentFile, currentInput);
      } else {
        response = await chatContinue(currentInput, messages);
      }

      if (response.status === "followup") {
        setCurrentSessionId(response.session_id || null);
        setFollowUpResponse(response);
        setLatestRetrievalContextId("");
      } else {
        setCurrentSessionId(null);
        setFollowUpResponse(null);
        setLatestRetrievalContextId(response.retrieval_context_id || "");
        const answer =
          response.answer && response.answer.trim()
            ? response.answer
            : "Not enough context to answer this question. Try rephrasing or ask about MITRE ATT&CK techniques, malware analysis, or cybersecurity incidents.";
        const aiMessage: ChatMessage = {
          role: "assistant",
          content: answer,
        };
        setMessages((previous) => [...previous, aiMessage]);
      }
    } catch (error) {
      console.error("Chat error:", error);
      const errorMessage: ChatMessage = {
        role: "assistant",
        content: "Sorry, something went wrong while processing your request. Please try again.",
      };
      setMessages((previous) => [...previous, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    setSelectedFile(file);
  };

  const handleGenerateReport = async () => {
    if (!hasMessages || isReportLoading) {
      return;
    }

    setIsReportLoading(true);
    setReportError("");
    setReportFollowupAnswer("");

    try {
      const result = await generateReport(
        chatTranscript,
        reportType,
        false,
        false,
        latestRetrievalContextId,
      );
      setReportWorkflow(result);
      setReportSourceCount(messages.length);
    } catch (error) {
      console.error("Report generation failed:", error);
      setReportError("Report generation failed. Check the backend and try again.");
    } finally {
      setIsReportLoading(false);
    }
  };

  const handleResumeReport = async () => {
    if (!reportWorkflow?.session_id || !reportFollowupAnswer.trim() || isReportLoading) {
      return;
    }

    setIsReportLoading(true);
    setReportError("");

    try {
      const result = await resumeReport(
        reportWorkflow.session_id,
        reportFollowupAnswer.trim(),
      );
      setReportWorkflow(result);
      setReportFollowupAnswer("");
      setReportSourceCount(messages.length);
    } catch (error) {
      console.error("Report resume failed:", error);
      setReportError("Could not resume the report session.");
    } finally {
      setIsReportLoading(false);
    }
  };

  return (
    <div className="flex h-screen flex-col bg-background font-sans">
      <nav className="relative z-10 flex items-center justify-between border-b border-gray-200 bg-white px-6 py-4 shadow-sm lg:px-12">
        <Link
          href="/"
          className="flex min-w-0 items-center gap-3 text-xl font-bold tracking-tight text-primary transition-opacity hover:opacity-80"
        >
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded bg-primary text-sm text-white">
            C
          </div>
          <span className="truncate">CyberCase Framework</span>
        </Link>
        <div className="hidden items-center gap-6 md:flex">
          <span className="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium uppercase tracking-widest text-neutral">
            Chat + Report
          </span>
          <Link
            href="/"
            className="text-sm font-medium text-neutral transition-colors hover:text-primary"
          >
            Exit Chat
          </Link>
        </div>
      </nav>

      <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[minmax(0,1fr)_460px] xl:grid-cols-[minmax(0,1fr)_520px]">
        <section className="flex min-h-0 flex-col">
          <main className="min-h-0 flex-1 overflow-y-auto p-4 md:p-8">
            <div className="mx-auto max-w-4xl space-y-6">
              {messages.length === 0 && (
                <div className="flex flex-col items-center justify-center space-y-6 py-20 text-center">
                  <div className="flex h-16 w-16 rotate-[-3deg] items-center justify-center rounded-2xl bg-primary text-white shadow-lg">
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width="32"
                      height="32"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="m3 21 1.9-5.7a8.5 8.5 0 1 1 3.8 3.8z" />
                    </svg>
                  </div>
                  <div className="space-y-2">
                    <h1 className="text-3xl font-extrabold tracking-tight text-primary">
                      Investigation chat
                    </h1>
                    <p className="mx-auto max-w-md text-neutral">
                      Ask about MITRE ATT&CK, malware analysis, cyber incidents, or Thai cyber law.
                    </p>
                  </div>
                  <div className="grid w-full max-w-lg grid-cols-1 gap-3 md:grid-cols-2">
                    {[
                      "Map this phishing case to MITRE ATT&CK.",
                      "What evidence is missing for this incident?",
                    ].map((question) => (
                      <button
                        key={question}
                        type="button"
                        onClick={() => setInput(question)}
                        className="rounded-xl border border-gray-200 bg-white px-4 py-3 text-left text-sm font-medium text-secondary shadow-sm transition-all hover:border-primary hover:bg-gray-50"
                      >
                        {question}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((message, index) => (
                <div
                  key={`${message.role}-${index}`}
                  className={`flex animate-in fade-in slide-in-from-bottom-2 duration-300 ${
                    message.role === "user" ? "justify-end" : "justify-start"
                  }`}
                >
                  <div
                    className={`max-w-[85%] rounded-2xl px-5 py-4 md:max-w-[78%] ${
                      message.role === "user"
                        ? "rounded-br-none bg-primary text-white shadow-md"
                        : "rounded-bl-none border border-gray-200 bg-white text-primary shadow-sm"
                    }`}
                  >
                    <div className="mb-1 text-[10px] font-bold uppercase opacity-50">
                      {message.role === "user" ? "You" : "Assistant"}
                    </div>
                    <p className="whitespace-pre-wrap text-sm font-medium leading-relaxed md:text-base">
                      {message.content}
                    </p>
                  </div>
                </div>
              ))}

              {followUpResponse && followUpResponse.status === "followup" && (
                <FollowUpModule
                  question={followUpResponse.followup_question || "I need more information."}
                  sessionId={followUpResponse.session_id || ""}
                  onResolved={(response) => {
                    setFollowUpResponse(null);
                    setCurrentSessionId(null);
                    setLatestRetrievalContextId(response.retrieval_context_id || "");
                    const aiMessage: ChatMessage = {
                      role: "assistant",
                      content: response.answer,
                    };
                    setMessages((previous) => [...previous, aiMessage]);
                  }}
                  onError={(error) => {
                    console.error("Follow-up error:", error);
                    setFollowUpResponse(null);
                  }}
                />
              )}

              {isLoading && (
                <div className="flex animate-pulse justify-start">
                  <div className="rounded-2xl rounded-bl-none border border-gray-200 bg-white px-5 py-4 shadow-sm">
                    <div className="flex space-x-2 py-2">
                      <div className="h-2 w-2 animate-bounce rounded-full bg-primary" />
                      <div
                        className="h-2 w-2 animate-bounce rounded-full bg-primary"
                        style={{ animationDelay: "150ms" }}
                      />
                      <div
                        className="h-2 w-2 animate-bounce rounded-full bg-primary"
                        style={{ animationDelay: "300ms" }}
                      />
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          </main>

          <footer className="border-t border-gray-200 bg-white p-4 md:p-6">
            <div className="mx-auto max-w-4xl">
              <form onSubmit={handleSubmit} className="space-y-3">
                <div className="flex flex-col gap-3 rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 md:flex-row md:items-center">
                  <label className="flex flex-1 cursor-pointer items-center gap-3 text-sm font-medium text-primary">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-gray-200 bg-white">
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
                        <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" />
                        <path d="M14 2v4a2 2 0 0 0 2 2h4" />
                        <path d="M10 12H8" />
                        <path d="M16 16H8" />
                        <path d="M16 20H8" />
                      </svg>
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate">
                        {selectedFile ? selectedFile.name : "Attach PDF or image"}
                      </span>
                      <span className="block text-xs font-normal text-neutral">
                        PDF, PNG, JPG, or JPEG
                      </span>
                    </span>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
                      onChange={handleFileChange}
                      disabled={isLoading}
                      className="sr-only"
                    />
                  </label>

                  {selectedFile && (
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedFile(null);
                        if (fileInputRef.current) {
                          fileInputRef.current.value = "";
                        }
                      }}
                      disabled={isLoading}
                      className="h-10 rounded-xl border border-gray-200 bg-white px-3 text-xs font-bold uppercase tracking-widest text-neutral transition-colors hover:text-primary disabled:opacity-50"
                    >
                      Clear
                    </button>
                  )}
                </div>

                <div className="group relative flex items-center">
                  <input
                    type="text"
                    value={input}
                    onChange={(event) => setInput(event.target.value)}
                    placeholder={
                      currentSessionId
                        ? "Answer the follow-up question..."
                        : selectedFile
                          ? "Ask what to analyze from this file..."
                          : "Ask about MITRE ATT&CK, malware analysis, or cyber incidents..."
                    }
                    disabled={isLoading}
                    className={`w-full rounded-2xl border bg-gray-50 py-5 pl-6 pr-16 text-primary shadow-sm outline-none transition-all group-hover:shadow-md disabled:opacity-50 ${
                      currentSessionId
                        ? "border-amber-300 ring-1 ring-amber-100"
                        : "border-gray-200 focus:border-primary focus:bg-white"
                    }`}
                  />
                  <button
                    type="submit"
                    disabled={isLoading || (!input.trim() && !selectedFile)}
                    className="absolute right-3 rounded-xl bg-primary p-3 text-white shadow-sm transition-all hover:bg-secondary active:scale-95 disabled:bg-neutral disabled:opacity-50"
                    aria-label="Send message"
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width="20"
                      height="20"
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
                  </button>
                </div>
              </form>
            </div>
          </footer>
        </section>

        <aside className="flex min-h-0 flex-col border-t border-gray-200 bg-white lg:border-l lg:border-t-0">
          <div className="shrink-0 border-b border-gray-200 px-5 py-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-xs font-bold uppercase tracking-widest text-neutral">
                  Report area
                </p>
                <h2 className="mt-1 text-xl font-extrabold text-primary">
                  Case report
                </h2>
              </div>
              {completeness ? (
                <span className="rounded-md bg-primary px-2.5 py-1.5 text-xs font-black text-white">
                  {completeness.percentage}%
                </span>
              ) : null}
            </div>

            <div className="mt-4 grid grid-cols-2 gap-2">
              {REPORT_TYPES.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setReportType(option.value)}
                  aria-pressed={reportType === option.value}
                  className={`rounded-md border px-3 py-2 text-left text-xs font-bold transition-colors ${
                    reportType === option.value
                      ? "border-primary bg-primary text-white"
                      : "border-gray-200 bg-white text-secondary hover:border-primary"
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>

            <button
              type="button"
              onClick={handleGenerateReport}
              disabled={!hasMessages || isReportLoading}
              className="mt-3 w-full rounded-md bg-primary px-4 py-3 text-sm font-bold text-white transition-colors hover:bg-secondary disabled:cursor-not-allowed disabled:bg-neutral disabled:opacity-60"
            >
              {isReportLoading ? "Working..." : `${reportButtonLabel} from chat`}
            </button>

            {reportIsStale ? (
              <p className="mt-2 text-xs font-medium text-amber-700">
                Chat changed after the last report.
              </p>
            ) : null}
            {reportError ? (
              <p className="mt-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                {reportError}
              </p>
            ) : null}
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto py-5">
            {reportWorkflow?.status === "followup" ? (
              <section className="mx-5 rounded-md border border-amber-200 bg-amber-50 p-4">
                <p className="text-xs font-bold uppercase tracking-widest text-amber-700">
                  Follow-up required
                </p>
                <p className="mt-3 text-sm leading-6 text-secondary">
                  {reportWorkflow.followup_question || "Please provide more case detail."}
                </p>
                <textarea
                  value={reportFollowupAnswer}
                  onChange={(event) => setReportFollowupAnswer(event.target.value)}
                  className="mt-3 min-h-24 w-full resize-y rounded-md border border-amber-200 bg-white p-3 text-sm text-primary outline-none focus:border-primary"
                  placeholder="Provide the missing report detail."
                />
                <button
                  type="button"
                  onClick={handleResumeReport}
                  disabled={!reportFollowupAnswer.trim() || isReportLoading}
                  className="mt-3 rounded-md bg-primary px-4 py-2 text-sm font-bold text-white disabled:cursor-not-allowed disabled:bg-neutral disabled:opacity-60"
                >
                  Resume report
                </button>
              </section>
            ) : report ? (
              <ReportContent report={report} />
            ) : (
              <EmptyReportState />
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}