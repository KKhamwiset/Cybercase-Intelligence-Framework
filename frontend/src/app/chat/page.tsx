"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent, FormEvent, ReactNode } from "react";
import Link from "next/link";
import FollowUpModule from "@/components/FollowUpModule";
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

const REPORT_TYPES: { value: ReportType; label: string }[] = [
  { value: "overview", label: "Overview" },
  { value: "subject", label: "Subject" },
  { value: "timeline", label: "Timeline" },
  { value: "vulnerability", label: "Vulnerability" },
];

const SUGGESTED_QUESTIONS = [
  "Map this phishing incident to MITRE ATT&CK and identify supporting evidence.",
  "What evidence is still missing before generating a CyberCase incident report?",
];

type CaseTab = "Inbox" | "Active" | "Archived";

const CASE_TABS: CaseTab[] = ["Inbox", "Active", "Archived"];

const NAV_ITEMS = [
  { label: "Home", href: "/" },
  { label: "Investigate", href: "/chat" },
  { label: "Reports", href: "/report" },
];

function buildReportTranscript(messages: ChatMessage[]): string {
  const userTurns = messages
    .filter((message) => message.role === "user")
    .map(
      (message, index) => `User turn ${index + 1}:\n${message.content.trim()}`,
    )
    .join("\n\n");

  const assistantTurns = messages
    .filter((message) => message.role === "assistant")
    .map(
      (message, index) =>
        `Assistant turn ${index + 1}:\n${message.content.trim()}`,
    )
    .join("\n\n");

  return [
    "Generate a CyberCase preliminary incident investigation report from this chat transcript.",
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
    return "border-black bg-black text-white";
  }

  if (
    value === "reported" ||
    value === "reviewed" ||
    value === "ai_generated"
  ) {
    return "border-black/30 bg-white text-black";
  }

  if (value === "inferred") {
    return "border-black/20 bg-neutral-100 text-neutral-700";
  }

  return "border-black/10 bg-neutral-50 text-neutral-500";
}

function StatusBadge({ value }: { value: string }) {
  return (
    <span
      className={`inline-flex rounded-md border px-2 py-1 text-[11px] font-bold uppercase ${statusClass(
        value,
      )}`}
    >
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
    <section className="border-t border-black/10 px-4 py-4">
      <h3 className="mb-3 text-[11px] font-black uppercase text-neutral">
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
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-lg border border-black bg-white text-xs font-black text-black">
          CC
        </div>
        <p className="mt-4 text-sm font-black text-black">
          No CyberCase report yet.
        </p>
        <p className="mt-1 text-xs leading-5 text-neutral">
          Build an investigation transcript, then generate a report from the
          collected evidence.
        </p>
      </div>
    </div>
  );
}

function ReportContent({ report }: { report: CyberCaseReport }) {
  return (
    <div>
      <section className="px-4 pb-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-[11px] font-black uppercase text-neutral">
              CyberCase {report.report_type} report
            </p>
            <h2 className="mt-2 text-lg font-black leading-snug text-black">
              {report.title}
            </h2>
          </div>

          <StatusBadge value={report.review_status} />
        </div>

        <p className="mt-4 text-sm leading-6 text-secondary">
          {report.executive_case_summary}
        </p>
      </section>

      <ReportSection title="Case Completeness">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-bold text-black">
              {report.case_information_completeness.status}
            </p>
            <p className="mt-1 text-xs leading-5 text-neutral">
              {report.case_information_completeness.missing_fields.length
                ? report.case_information_completeness.missing_fields.join(", ")
                : "All required preliminary fields are present."}
            </p>
          </div>

          <span className="text-3xl font-black text-black">
            {report.case_information_completeness.percentage}%
          </span>
        </div>

        <div className="mt-4 h-2 overflow-hidden rounded bg-neutral-200">
          <div
            className="h-full bg-black"
            style={{
              width: `${report.case_information_completeness.percentage}%`,
            }}
          />
        </div>
      </ReportSection>

      <ReportSection title="Evidence & Indicators">
        {report.evidence_and_indicators_table.length ? (
          <div className="space-y-3">
            {report.evidence_and_indicators_table
              .slice(0, 6)
              .map((indicator) => (
                <div
                  key={indicator.indicator_id}
                  className="border border-black/10 bg-white p-3"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[11px] font-black uppercase text-neutral">
                      {indicator.indicator_type}
                    </span>
                    <StatusBadge value={indicator.status} />
                  </div>

                  <p className="mt-2 break-all text-sm font-bold text-black">
                    {indicator.value}
                  </p>
                </div>
              ))}
          </div>
        ) : (
          <p className="text-sm text-neutral">No indicators listed.</p>
        )}
      </ReportSection>

      <ReportSection title="MITRE ATT&CK Mapping">
        {report.mitre_attack_assessment.length ? (
          <div className="space-y-3">
            {report.mitre_attack_assessment.slice(0, 5).map((mapping) => (
              <div
                key={`${mapping.technique_id}-${mapping.technique_name}`}
                className="border border-black/10 bg-white p-3"
              >
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <p className="text-sm font-black text-black">
                    {mapping.technique_id} {mapping.technique_name}
                  </p>
                  <StatusBadge value={mapping.mapping_status} />
                </div>

                <p className="mt-2 text-xs leading-5 text-neutral">
                  {mapping.justification}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-neutral">
            No supported MITRE ATT&CK mapping yet.
          </p>
        )}
      </ReportSection>

      <ReportSection title="Recommended Next Steps">
        {report.investigation_next_steps.length ? (
          <ul className="space-y-2 text-sm leading-6 text-secondary">
            {report.investigation_next_steps.slice(0, 6).map((step) => (
              <li key={step} className="flex gap-2">
                <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-black" />
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
  const [followUpResponse, setFollowUpResponse] =
    useState<QueryResponse | null>(null);
  const [reportType, setReportType] = useState<ReportType>("overview");
  const [reportWorkflow, setReportWorkflow] =
    useState<ReportWorkflowResponse | null>(null);
  const [latestRetrievalContextId, setLatestRetrievalContextId] = useState("");
  const [reportFollowupAnswer, setReportFollowupAnswer] = useState("");
  const [reportSourceCount, setReportSourceCount] = useState(0);
  const [isReportLoading, setIsReportLoading] = useState(false);
  const [reportError, setReportError] = useState("");
  const [activeTab, setActiveTab] = useState<CaseTab>("Inbox");
  const [isReportOpen, setIsReportOpen] = useState(true);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const report = reportWorkflow?.report ?? null;
  const completeness = reportCompleteness(reportWorkflow);
  const hasMessages = messages.length > 0;
  const reportIsStale =
    reportWorkflow !== null && messages.length !== reportSourceCount;
  const reportButtonLabel = reportWorkflow ? "Regenerate" : "Generate";
  const chatTranscript = useMemo(
    () => buildReportTranscript(messages),
    [messages],
  );

  const latestUserMessage = useMemo(() => {
    for (let index = messages.length - 1; index >= 0; index -= 1) {
      if (messages[index].role === "user") {
        return messages[index];
      }
    }

    return null;
  }, [messages]);

  const caseRows = useMemo(
    () => [
      {
        name: hasMessages
          ? "Current CyberCase Investigation"
          : "New Investigation",
        owner: "CyberCase AI",
        time: hasMessages ? "Live" : "Draft",
        active: true,
        preview:
          latestUserMessage?.content.split("\n")[0] ||
          "Start with a case narrative, log, or evidence file.",
      },
      {
        name: "Phishing wire transfer",
        owner: "Analyst queue",
        time: "09:42 AM",
        active: false,
        preview:
          "Email header, proxy log, and bank transfer evidence under review.",
      },
      {
        name: "Credential stuffing",
        owner: "Review lane",
        time: "Yesterday",
        active: false,
        preview: "Login anomaly cluster needs MITRE confidence review.",
      },
      {
        name: "Endpoint malware",
        owner: "Report lane",
        time: "Mon",
        active: false,
        preview: "Persistence and command execution findings drafted.",
      },
    ],
    [hasMessages, latestUserMessage],
  );

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
            : "Not enough context to answer this question. Try providing more evidence or ask about MITRE ATT&CK techniques, malware analysis, Thai cyber law, or incident response.";

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
        content:
          "Sorry, something went wrong while processing this CyberCase investigation. Please try again.",
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

    setIsReportOpen(true);
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
      setReportError(
        "CyberCase report generation failed. Check the backend and try again.",
      );
    } finally {
      setIsReportLoading(false);
    }
  };

  const handleResumeReport = async () => {
    if (
      !reportWorkflow?.session_id ||
      !reportFollowupAnswer.trim() ||
      isReportLoading
    ) {
      return;
    }

    setIsReportOpen(true);
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
      setReportError("Could not resume the CyberCase report session.");
    } finally {
      setIsReportLoading(false);
    }
  };

  return (
    <main className="h-screen overflow-hidden bg-white text-black">
      <div className="flex h-full w-full overflow-hidden bg-white">
        <aside className="hidden w-56 shrink-0 flex-col border-r border-black/10 bg-white px-4 py-5 md:flex">
          <Link
            href="/"
            className="flex items-center gap-2 text-base font-black tracking-tight"
          >
            <span className="flex h-7 w-7 items-center justify-center bg-black text-[10px] text-white">
              CC
            </span>
            <span>CyberCase</span>
          </Link>

          <p className="mt-2 text-[10px] font-bold uppercase tracking-[0.13em] text-neutral">
            Intelligence Framework
          </p>

          <nav className="mt-7 space-y-1 text-[11px] font-bold">
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.label}
                href={item.href}
                className={`block px-3 py-2 ${
                  item.label === "Investigate"
                    ? "bg-black text-white"
                    : "text-neutral hover:bg-neutral-100 hover:text-black"
                }`}
              >
                {item.label}
              </Link>
            ))}
          </nav>

          <div className="mt-auto border-t border-black/10 pt-4">
            <p className="text-xs font-semibold text-neutral">Workspace</p>
            <p className="mt-1 truncate text-sm font-black">
              CyberCase Operations
            </p>
          </div>
        </aside>

        <section className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-16 shrink-0 items-center justify-between border-b border-black/10 bg-white px-4 md:px-6">
            <div className="flex items-center gap-3">
              <button
                type="button"
                className="flex h-8 w-8 items-center justify-center bg-black text-[10px] font-black text-white md:hidden"
              >
                CC
              </button>

              <div>
                <p className="text-sm font-black">CyberCase Investigate</p>
                <p className="hidden text-[11px] font-semibold text-neutral sm:block">
                  Evidence-led cyber investigation workspace
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="hidden text-xs font-semibold text-neutral sm:inline">
                Case workspace
              </span>

              <button
                type="button"
                onClick={() => setIsReportOpen((open) => !open)}
                className="border border-black px-3 py-2 text-xs font-black transition hover:bg-black hover:text-white"
                aria-pressed={isReportOpen}
                aria-label={
                  isReportOpen ? "Hide report panel" : "Show report panel"
                }
              >
                {isReportOpen ? "Hide Report" : "Show Report"}
              </button>
            </div>
          </header>

          <div
            className={`grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[250px_minmax(0,1fr)] ${
              isReportOpen
                ? "xl:grid-cols-[250px_minmax(0,1fr)_390px]"
                : "xl:grid-cols-[250px_minmax(0,1fr)_56px]"
            }`}
          >
            <aside className="hidden min-h-0 flex-col border-r border-black/10 bg-white lg:flex">
              <div className="border-b border-black/10 p-4">
                <label htmlFor="case-search" className="sr-only">
                  Search cases
                </label>

                <input
                  id="case-search"
                  type="search"
                  placeholder="Search cases"
                  className="w-full border border-black/10 bg-neutral-50 px-3 py-2 text-sm outline-none placeholder:text-neutral focus:border-black"
                />

                <div className="mt-3 grid grid-cols-3 gap-1 rounded-md bg-neutral-100 p-1">
                  {CASE_TABS.map((tab) => (
                    <button
                      key={tab}
                      type="button"
                      onClick={() => setActiveTab(tab)}
                      className={`rounded px-2 py-1.5 text-[11px] font-black ${
                        activeTab === tab
                          ? "bg-white text-black shadow-sm"
                          : "text-neutral"
                      }`}
                    >
                      {tab}
                    </button>
                  ))}
                </div>
              </div>

              <div className="min-h-0 flex-1 overflow-y-auto p-3">
                <div className="space-y-2">
                  {caseRows.map((item) => (
                    <button
                      key={item.name}
                      type="button"
                      className={`w-full rounded-lg border p-3 text-left transition ${
                        item.active
                          ? "border-black bg-neutral-50"
                          : "border-transparent bg-white hover:border-black/10 hover:bg-neutral-50"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-black">
                            {item.name}
                          </p>
                          <p className="mt-1 truncate text-[11px] font-semibold text-neutral">
                            {item.owner}
                          </p>
                        </div>

                        <span className="shrink-0 text-[11px] font-semibold text-neutral">
                          {item.time}
                        </span>
                      </div>

                      <p className="mt-3 line-clamp-2 text-xs leading-5 text-neutral">
                        {item.preview}
                      </p>
                    </button>
                  ))}
                </div>
              </div>
            </aside>

            <section className="flex min-h-0 flex-col bg-[#f5f5f5]">
              <div className="flex h-16 shrink-0 items-center justify-between border-b border-black/10 bg-white px-4">
                <div className="flex min-w-0 items-center gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-black text-[10px] font-black text-white">
                    CC
                  </div>

                  <div className="min-w-0">
                    <p className="truncate text-sm font-black">
                      Current CyberCase Investigation
                    </p>
                    <p className="truncate text-xs font-semibold text-neutral">
                      {hasMessages
                        ? `${messages.length} investigation entries`
                        : "Ready for incident intake and evidence review"}
                    </p>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={handleGenerateReport}
                  disabled={!hasMessages || isReportLoading}
                  className="bg-black px-3 py-2 text-xs font-black text-white transition hover:bg-neutral-800 disabled:cursor-not-allowed disabled:bg-neutral-200 disabled:text-neutral"
                >
                  {isReportLoading ? "Working" : "Report"}
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
                            Start your investigation.
                          </h1>

                          <p className="mt-2 max-w-lg text-sm leading-6 text-neutral">
                            Submit an incident narrative, upload evidence, map
                            attacker behaviour to MITRE ATT&CK, and generate a
                            structured CyberCase report.
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
                            onClick={() => setInput(question)}
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
                        message.role === "user"
                          ? "justify-end"
                          : "justify-start"
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
                            message.role === "user"
                              ? "text-white/60"
                              : "text-neutral"
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

                  {followUpResponse &&
                  followUpResponse.status === "followup" ? (
                    <FollowUpModule
                      question={
                        followUpResponse.followup_question ||
                        "I need more information about this incident."
                      }
                      sessionId={followUpResponse.session_id || ""}
                      onResolved={(response) => {
                        setFollowUpResponse(null);
                        setCurrentSessionId(null);
                        setLatestRetrievalContextId(
                          response.retrieval_context_id || "",
                        );

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
                <form
                  onSubmit={handleSubmit}
                  className="mx-auto max-w-3xl space-y-2"
                >
                  {selectedFile ? (
                    <div className="flex items-center justify-between gap-3 border border-black/10 bg-neutral-50 px-3 py-2 text-xs font-semibold">
                      <span className="truncate">
                        Attached: {selectedFile.name}
                      </span>

                      <button
                        type="button"
                        onClick={() => {
                          setSelectedFile(null);

                          if (fileInputRef.current) {
                            fileInputRef.current.value = "";
                          }
                        }}
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
                      onChange={handleFileChange}
                      disabled={isLoading}
                      className="sr-only"
                    />

                    <input
                      type="text"
                      value={input}
                      onChange={(event) => setInput(event.target.value)}
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

            {isReportOpen ? (
              <aside className="flex min-h-0 flex-col border-t border-black/10 bg-[#fafafa] xl:border-l xl:border-t-0">
                <div className="shrink-0 border-b border-black/10 bg-white px-4 py-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="mono-label">CyberCase Output</p>
                      <h2 className="mt-1 text-lg font-black text-black">
                        Investigation Report
                      </h2>
                    </div>

                    <div className="flex items-center gap-2">
                      {completeness ? (
                        <span className="rounded-md bg-black px-2.5 py-1.5 text-xs font-black text-white">
                          {completeness.percentage}%
                        </span>
                      ) : null}

                      <button
                        type="button"
                        onClick={() => setIsReportOpen(false)}
                        className="border border-black/10 px-2 py-1 text-xs font-black hover:border-black"
                        aria-label="Collapse report panel"
                      >
                        X
                      </button>
                    </div>
                  </div>

                  <div className="mt-4 grid grid-cols-2 gap-2">
                    {REPORT_TYPES.map((option) => (
                      <button
                        key={option.value}
                        type="button"
                        onClick={() => setReportType(option.value)}
                        aria-pressed={reportType === option.value}
                        className={`rounded-md border px-3 py-2 text-left text-xs font-black transition-colors ${
                          reportType === option.value
                            ? "border-black bg-black text-white"
                            : "border-black/10 bg-white text-neutral hover:border-black hover:text-black"
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
                    className="mt-3 w-full rounded-md bg-black px-4 py-3 text-sm font-black text-white transition-colors hover:bg-neutral-800 disabled:cursor-not-allowed disabled:bg-neutral-200 disabled:text-neutral"
                  >
                    {isReportLoading
                      ? "Building report..."
                      : `${reportButtonLabel} from investigation`}
                  </button>

                  {reportIsStale ? (
                    <p className="mt-2 text-xs font-semibold text-neutral">
                      Investigation context changed after the last report.
                    </p>
                  ) : null}

                  {reportError ? (
                    <p className="mt-3 border border-black/10 bg-white p-3 text-sm text-secondary">
                      {reportError}
                    </p>
                  ) : null}
                </div>

                <div className="min-h-0 flex-1 overflow-y-auto py-4">
                  {reportWorkflow?.status === "followup" ? (
                    <section className="mx-4 border border-black/15 bg-white p-4">
                      <p className="mono-label">Follow-up Required</p>

                      <p className="mt-3 text-sm leading-6 text-secondary">
                        {reportWorkflow.followup_question ||
                          "Please provide more case detail."}
                      </p>

                      <textarea
                        value={reportFollowupAnswer}
                        onChange={(event) =>
                          setReportFollowupAnswer(event.target.value)
                        }
                        className="mt-3 min-h-24 w-full resize-y border border-black/10 bg-white p-3 text-sm text-black outline-none placeholder:text-neutral focus:border-black"
                        placeholder="Provide the missing investigation detail."
                      />

                      <button
                        type="button"
                        onClick={handleResumeReport}
                        disabled={
                          !reportFollowupAnswer.trim() || isReportLoading
                        }
                        className="mt-3 rounded-md bg-black px-4 py-2 text-sm font-black text-white disabled:cursor-not-allowed disabled:bg-neutral-200 disabled:text-neutral"
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
            ) : (
              <aside className="hidden min-h-0 border-l border-black/10 bg-white xl:flex xl:flex-col xl:items-center xl:justify-center">
                <button
                  type="button"
                  onClick={() => setIsReportOpen(true)}
                  className="flex h-10 w-10 items-center justify-center rounded-full bg-black text-[10px] font-black text-white"
                  aria-label="Open report panel"
                >
                  CC
                </button>
              </aside>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
