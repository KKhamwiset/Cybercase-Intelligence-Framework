"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";

import InvestigationCaseList from "@/components/chat/InvestigationCaseList";
import type {
  CaseTab,
  InvestigationCaseRow,
} from "@/components/chat/InvestigationCaseList";
import InvestigationChatPanel from "@/components/chat/InvestigationChatPanel";
import InvestigationReportPanel from "@/components/chat/InvestigationReportPanel";
import type { FollowUpEntry } from "@/components/FollowUpModule";
import {
  chatContinue,
  generateReport,
  queryRagFile,
  resumeRag,
  resumeReport,
} from "@/lib/api";
import type {
  ChatMessage,
  QueryResponse,
  ReportType,
  ReportWorkflowResponse,
} from "@/lib/api";

type InvestigationWorkspaceProps = {
  title?: string;
  subtitle?: string;
  emptyTitle?: string;
  emptyDescription?: string;
  showCaseList?: boolean;
  initialPrompt?: string;
  initialDisplayMessage?: string;
  autoRunInitialPrompt?: boolean;
  contextPrefix?: string;
};

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

export default function InvestigationWorkspace({
  title = "Current CyberCase Investigation",
  subtitle,
  emptyTitle = "Start your investigation.",
  emptyDescription = "Submit an incident narrative, upload evidence, map attacker behaviour to MITRE ATT&CK, and generate a structured CyberCase report.",
  showCaseList = true,
  initialPrompt = "",
  initialDisplayMessage,
  autoRunInitialPrompt = false,
  contextPrefix = "",
}: InvestigationWorkspaceProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [followUpResponse, setFollowUpResponse] =
    useState<QueryResponse | null>(null);
  const [followUpAnswer, setFollowUpAnswer] = useState("");
  const [followUpEntries, setFollowUpEntries] = useState<FollowUpEntry[]>([]);
  const [isFollowUpSubmitting, setIsFollowUpSubmitting] = useState(false);
  const [reportType, setReportType] = useState<ReportType>("overview");
  const [reportWorkflow, setReportWorkflow] =
    useState<ReportWorkflowResponse | null>(null);
  const [latestRetrievalContextId, setLatestRetrievalContextId] = useState("");
  const [reportSourceRetrievalContextId, setReportSourceRetrievalContextId] =
    useState("");
  const [retrievalRefreshedAfterFollowUp, setRetrievalRefreshedAfterFollowUp] =
    useState(false);
  const [reportFollowupAnswer, setReportFollowupAnswer] = useState("");
  const [reportSourceCount, setReportSourceCount] = useState(0);
  const [isReportLoading, setIsReportLoading] = useState(false);
  const [reportError, setReportError] = useState("");
  const [activeTab, setActiveTab] = useState<CaseTab>("Inbox");
  const [isReportOpen, setIsReportOpen] = useState(true);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const autoRunRef = useRef(false);

  const hasMessages = messages.length > 0;
  const reportIsStale =
    reportWorkflow !== null &&
    (messages.length !== reportSourceCount ||
      latestRetrievalContextId !== reportSourceRetrievalContextId);
  const reportHasRefreshedContext = Boolean(
    reportWorkflow &&
      retrievalRefreshedAfterFollowUp &&
      latestRetrievalContextId &&
      latestRetrievalContextId !== reportSourceRetrievalContextId,
  );
  const canGenerateReport = Boolean(latestRetrievalContextId);
  const reportButtonLabel = !canGenerateReport
    ? "Complete RAG analysis first"
    : reportHasRefreshedContext
      ? "Regenerate from refreshed context"
      : reportWorkflow
        ? "Regenerate from investigation"
        : "Generate from investigation";
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

  const caseRows: InvestigationCaseRow[] = useMemo(
    () => [
      {
        name: hasMessages ? title : "New Investigation",
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
    [hasMessages, latestUserMessage, title],
  );

  const chatSubtitle =
    subtitle ??
    (hasMessages
      ? `${messages.length} investigation entries`
      : "Ready for incident intake and evidence review");

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const runInvestigation = useCallback(
    async ({
      query,
      file,
      displayContent,
      includeContextPrefix = true,
    }: {
      query: string;
      file: File | null;
      displayContent?: string;
      includeContextPrefix?: boolean;
    }) => {
      if ((!query.trim() && !file) || isLoading) {
        return;
      }
      const trimmedContextPrefix = contextPrefix.trim();
      const apiQuery =
        includeContextPrefix && trimmedContextPrefix
          ? [
              trimmedContextPrefix,
              "",
              "Current analyst message:",
              query.trim() || "Analyze the attached evidence file.",
            ].join("\n")
          : query;

      const userMessage: ChatMessage = {
        role: "user",
        content: file
          ? `${displayContent || query || "Analyze this document"}\n\nAttached file: ${file.name}`
          : displayContent || query,
      };

      setMessages((previous) => [...previous, userMessage]);
      setIsLoading(true);
      setFollowUpAnswer("");
      setFollowUpEntries([]);

      try {
        let response: QueryResponse;

        if (currentSessionId) {
          response = await resumeRag(currentSessionId, query);
        } else if (file) {
          response = await queryRagFile(file, apiQuery);
        } else {
          response = await chatContinue(apiQuery, messages);
        }

        if (response.status === "followup") {
          setCurrentSessionId(response.session_id || null);
          setFollowUpResponse(response);
          setLatestRetrievalContextId("");
          setRetrievalRefreshedAfterFollowUp(false);
        } else {
          setCurrentSessionId(null);
          setFollowUpResponse(null);
          setLatestRetrievalContextId(response.retrieval_context_id || "");
          setRetrievalRefreshedAfterFollowUp(false);

          const answer =
            response.answer && response.answer.trim()
              ? response.answer
              : "Not enough context to answer this question. Try providing more evidence or ask about MITRE ATT&CK techniques, malware analysis, Thai cyber law, or incident response.";

          setMessages((previous) => [
            ...previous,
            {
              role: "assistant",
              content: answer,
            },
          ]);
        }
      } catch (error) {
        console.error("Chat error:", error);

        setMessages((previous) => [
          ...previous,
          {
            role: "assistant",
            content:
              "Sorry, something went wrong while processing this CyberCase investigation. Please try again.",
          },
        ]);
      } finally {
        setIsLoading(false);
      }
    },
    [contextPrefix, currentSessionId, isLoading, messages],
  );

  useEffect(() => {
    if (!autoRunInitialPrompt || !initialPrompt.trim() || autoRunRef.current) {
      return;
    }

    autoRunRef.current = true;
    void runInvestigation({
      query: initialPrompt,
      file: null,
      displayContent: initialDisplayMessage || initialPrompt,
      includeContextPrefix: false,
    });
  }, [
    autoRunInitialPrompt,
    initialDisplayMessage,
    initialPrompt,
    runInvestigation,
  ]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const currentInput = input;
    const currentFile = selectedFile;

    setInput("");
    setSelectedFile(null);

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }

    await runInvestigation({
      query: currentInput,
      file: currentFile,
    });
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    setSelectedFile(file);
  };

  const handleClearFile = () => {
    setSelectedFile(null);

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleFollowUpSubmit = async () => {
    if (
      !followUpResponse ||
      followUpResponse.status !== "followup" ||
      !followUpAnswer.trim() ||
      isFollowUpSubmitting
    ) {
      return;
    }

    const activeQuestion =
      followUpResponse.followup_question ||
      "I need more information about this incident.";
    const activeSessionId = followUpResponse.session_id || currentSessionId || "";
    const currentAnswer = followUpAnswer;

    if (!activeSessionId) {
      return;
    }

    setFollowUpAnswer("");
    setIsFollowUpSubmitting(true);

    try {
      const response = await resumeRag(activeSessionId, currentAnswer);
      const entry: FollowUpEntry = {
        question: activeQuestion,
        answer: currentAnswer,
      };

      setFollowUpEntries((previous) => [...previous, entry]);
      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          content: `Follow-up question:\n${activeQuestion}`,
        },
        {
          role: "user",
          content: `Follow-up answer:\n${currentAnswer}`,
        },
      ]);

      if (response.status === "followup") {
        setFollowUpResponse(response);
        setCurrentSessionId(response.session_id || activeSessionId);
        return;
      }

      const retrievalContextId = response.retrieval_context_id || "";
      const answer =
        response.answer && response.answer.trim()
          ? response.answer
          : "Thanks, I have enough context to continue the CyberCase investigation.";

      setFollowUpResponse(null);
      setCurrentSessionId(null);
      setFollowUpEntries([]);
      setLatestRetrievalContextId(retrievalContextId);
      setRetrievalRefreshedAfterFollowUp(Boolean(retrievalContextId));
      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          content: answer,
        },
      ]);
    } catch (error) {
      console.error("Follow-up error:", error);
      setFollowUpAnswer(currentAnswer);
    } finally {
      setIsFollowUpSubmitting(false);
    }
  };

  const handleGenerateReport = async () => {
    if (!canGenerateReport || isReportLoading) {
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
      setReportSourceRetrievalContextId(latestRetrievalContextId);
      setRetrievalRefreshedAfterFollowUp(false);
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
      setReportSourceRetrievalContextId(latestRetrievalContextId);
      setRetrievalRefreshedAfterFollowUp(false);
    } catch (error) {
      console.error("Report resume failed:", error);
      setReportError("Could not resume the CyberCase report session.");
    } finally {
      setIsReportLoading(false);
    }
  };

  const gridColumns = showCaseList
    ? isReportOpen
      ? "lg:grid-cols-[250px_minmax(0,1fr)] xl:grid-cols-[250px_minmax(0,1fr)_390px]"
      : "lg:grid-cols-[250px_minmax(0,1fr)] xl:grid-cols-[250px_minmax(0,1fr)_56px]"
    : isReportOpen
      ? "xl:grid-cols-[minmax(0,1fr)_390px]"
      : "xl:grid-cols-[minmax(0,1fr)_56px]";

  return (
    <div className={`grid h-full min-h-0 grid-cols-1 ${gridColumns}`}>
      {showCaseList ? (
        <InvestigationCaseList
          activeTab={activeTab}
          caseRows={caseRows}
          onActiveTabChange={setActiveTab}
        />
      ) : null}

      <InvestigationChatPanel
        title={title}
        subtitle={chatSubtitle}
        emptyTitle={emptyTitle}
        emptyDescription={emptyDescription}
        messages={messages}
        input={input}
        selectedFile={selectedFile}
        isLoading={isLoading}
        followUpResponse={followUpResponse}
        currentSessionId={currentSessionId}
        followUpAnswer={followUpAnswer}
        followUpEntries={followUpEntries}
        isFollowUpSubmitting={isFollowUpSubmitting}
        isReportLoading={isReportLoading}
        canGenerateReport={canGenerateReport}
        messagesEndRef={messagesEndRef}
        fileInputRef={fileInputRef}
        onInputChange={setInput}
        onFileChange={handleFileChange}
        onClearFile={handleClearFile}
        onSubmit={handleSubmit}
        onGenerateReport={handleGenerateReport}
        onFollowUpAnswerChange={setFollowUpAnswer}
        onFollowUpSubmit={handleFollowUpSubmit}
      />

      <InvestigationReportPanel
        isOpen={isReportOpen}
        reportWorkflow={reportWorkflow}
        reportType={reportType}
        reportButtonLabel={reportButtonLabel}
        reportIsStale={reportIsStale}
        retrievalRefreshed={retrievalRefreshedAfterFollowUp}
        isReportLoading={isReportLoading}
        reportError={reportError}
        canGenerateReport={canGenerateReport}
        reportFollowupAnswer={reportFollowupAnswer}
        onClose={() => setIsReportOpen(false)}
        onOpen={() => setIsReportOpen(true)}
        onReportTypeChange={setReportType}
        onGenerateReport={handleGenerateReport}
        onReportFollowupAnswerChange={setReportFollowupAnswer}
        onResumeReport={handleResumeReport}
      />
    </div>
  );
}
