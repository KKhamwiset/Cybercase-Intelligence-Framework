import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import {
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import ChatPage from "@/app/chat/page";
import {
  createChatMessage,
  downloadChatReportPdf,
  generateChatReport,
  getChatRun,
  getChatThread,
  listChatReports,
  listChatThreads,
  type ChatMessageAccepted,
  type ChatReportRead,
  type ChatThreadDetail,
  type PersistedChatMessage,
} from "@/lib/api";

vi.mock("@/lib/api", () => ({
  createChatMessage: vi.fn(),
  createChatThread: vi.fn(),
  deleteChatThread: vi.fn(),
  downloadChatReportPdf: vi.fn(),
  generateChatReport: vi.fn(),
  getApiErrorMessage: vi.fn(
    (_error: unknown, fallback: string) => fallback,
  ),
  getChatRun: vi.fn(),
  getChatThread: vi.fn(),
  listChatReports: vi.fn(),
  listChatThreads: vi.fn(),
  updateChatThread: vi.fn(),
}));

const thread: ChatThreadDetail = {
  id: "thread-1",
  title: "Saved investigation",
  status: "awaiting_followup",
  created_at: "2026-07-29T12:00:00Z",
  updated_at: "2026-07-29T12:01:00Z",
  messages: [
    {
      id: "message-1",
      thread_id: "thread-1",
      ordinal: 1,
      role: "user",
      content: "Investigate this PowerShell event.",
      retrieval_context_id: null,
      metadata_json: {},
      created_at: "2026-07-29T12:00:10Z",
    },
    {
      id: "message-2",
      thread_id: "thread-1",
      ordinal: 2,
      role: "assistant",
      content: "Which affected host produced this event?",
      retrieval_context_id: null,
      metadata_json: {
        chat_followup: {
          kind: "clarification",
          source_run_id: "run-root",
          root_ordinal: 1,
          round: 1,
        },
      },
      created_at: "2026-07-29T12:00:20Z",
    },
  ],
};

function userMessage(
  ordinal: number,
  content: string,
): PersistedChatMessage {
  return {
    id: `message-${ordinal}`,
    thread_id: thread.id,
    ordinal,
    role: "user",
    content,
    retrieval_context_id: null,
    metadata_json: {},
    created_at: `2026-07-29T12:00:${ordinal}0Z`,
  };
}

function followUpMessage(
  ordinal: number,
  content: string,
  round: number,
): PersistedChatMessage {
  return {
    id: `message-${ordinal}`,
    thread_id: thread.id,
    ordinal,
    role: "assistant",
    content,
    retrieval_context_id: null,
    metadata_json: {
      chat_followup: {
        kind: "clarification",
        source_run_id: `run-${round}`,
        root_ordinal: 1,
        round,
      },
    },
    created_at: `2026-07-29T12:00:${ordinal}0Z`,
  };
}

function accepted(
  message: PersistedChatMessage,
  runId: string,
): ChatMessageAccepted {
  return {
    message,
    run: {
      id: runId,
      thread_id: thread.id,
      request_message_id: message.id,
      operation: "query",
      status: "queued",
      error_code: null,
      error_message: null,
      created_at: "2026-07-29T12:02:00Z",
      updated_at: "2026-07-29T12:02:00Z",
    },
  };
}

function makeReportReadyThread(): ChatThreadDetail {
  const terminalAssistant: PersistedChatMessage = {
    ...thread.messages[1],
    content: "The persisted terminal answer.",
    retrieval_context_id: "context-1",
    metadata_json: {
      mitre_table: [],
      chat_extraction: {
        version: "baseline_extraction_v1",
        mode: "single_pass_llm",
        status: "candidate",
        case_summary: "A reported PowerShell event requires review.",
        entities: [],
        evidence: [],
        timeline: [],
        missing_information: [],
        warnings: [],
        prompt_version: "baseline_extraction_prompt_v1",
        provider: "anthropic",
        model: "claude-haiku-4-5-20251001",
        validation_status: "validated",
        latency_ms: 10,
        input_tokens: 10,
        output_tokens: 10,
        source_message_ids: ["message-1"],
        raw_response: null,
      },
    },
  };
  return {
    ...thread,
    status: "idle",
    messages: [thread.messages[0], terminalAssistant],
  };
}

function makeReport(version: number): ChatReportRead {
  const sectionIds = [
    "executive_summary",
    "case_background_scope",
    "evidence_findings",
    "individuals_accounts_systems_roles",
    "chronological_timeline",
    "technical_analysis_mitre",
    "conclusions_limitations_next_steps",
  ];
  const headings = [
    "Executive Summary",
    "Case Background and Scope",
    "Evidence Findings",
    "Individuals, Accounts, Systems, and Reported Roles",
    "Chronological Timeline",
    "Technical Analysis and MITRE ATT&CK Mapping",
    "Conclusions, Limitations, and Recommended Next Investigative Steps",
  ];
  return {
    report_id: `report-${version}`,
    thread_id: "thread-1",
    version_number: version,
    idempotency_key: `request-${version}`,
    source_snapshot_hash: `hash-${version}`,
    extraction_id: "message-2",
    extraction_version: "baseline_extraction_v1",
    prompt_version: "chat_report_prompt_v1",
    provider: "anthropic",
    model: "claude-haiku-4-5-20251001",
    decoding_settings: { temperature: 0, max_output_tokens: 4096 },
    persistence_status: "completed",
    validation_status: "validated",
    report: {
      report_version: "baseline_report_v1",
      status: "provisional_unverified",
      title: `Persisted report version ${version}`,
      sections: sectionIds.map((section_id, index) => ({
        section_id,
        heading: headings[index],
        paragraphs: [`Persisted report version ${version}.`],
        items: [],
      })),
      claims: [],
      limitations: ["Provisional and unverified."],
    },
    validation_errors: [],
    failure_code: null,
    failure_message: null,
    created_at: "2026-07-29T12:03:00Z",
    finished_at: "2026-07-29T12:03:01Z",
    latency_ms: 100,
    input_tokens: 100,
    output_tokens: 100,
  };
}

function makeFailedReport(code: string): ChatReportRead {
  return {
    ...makeReport(1),
    persistence_status: "failed",
    validation_status: "failed",
    report: null,
    validation_errors: ["model response was not valid JSON"],
    failure_code: code,
    failure_message: "The report model output failed validation.",
  };
}

async function renderLoadedPage(): Promise<void> {
  render(<ChatPage />);
  await waitFor(() =>
    expect(getChatThread).toHaveBeenCalledWith(
      thread.id,
      expect.any(AbortSignal),
    ),
  );
}

describe("active chat route", () => {
  beforeAll(() => {
    Object.defineProperty(Element.prototype, "scrollIntoView", {
      configurable: true,
      value: vi.fn(),
    });
  });

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(listChatThreads).mockResolvedValue([thread]);
    vi.mocked(getChatThread).mockResolvedValue(thread);
    vi.mocked(listChatReports).mockResolvedValue([]);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("renders the persisted follow-up question as an ordinary assistant message", async () => {
    render(<ChatPage />);

    expect(
      await screen.findByText("Which affected host produced this event?"),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Saved investigation").length).toBeGreaterThan(0);
    expect(screen.getByText("Recent chats")).toBeInTheDocument();
    expect(screen.getByText("Follow-up required")).toBeInTheDocument();
    expect(screen.getByLabelText("Chat message")).toBeEnabled();
    expect(
      screen.queryByLabelText("Clarification answer"),
    ).not.toBeInTheDocument();

    await waitFor(() => expect(getChatThread).toHaveBeenCalledWith(
      "thread-1",
      expect.any(AbortSignal),
    ));
    expect(screen.getByRole("tablist", { name: "Workspace views" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Chat" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("tab", { name: "Evidence & timeline" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Report generation" })).toBeInTheDocument();
    expect(
      screen.queryByText(
        "Which endpoint or service first showed signs of compromise?",
      ),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(
        "What evidence confirms when the suspicious activity began?",
      ),
    ).not.toBeInTheDocument();
  });

  it("switches to the selected thread's latest extraction and removes it from the transcript", async () => {
    const extractedThread: ChatThreadDetail = {
      ...thread,
      status: "idle",
      messages: [
        thread.messages[0],
        {
          ...thread.messages[1],
          content: "Older assistant extraction.",
          metadata_json: {
            chat_extraction: {
              mode: "deterministic_demo",
              evidence: [
                {
                  evidence_id: "E-OLD",
                  title: "Older candidate",
                  description: "Older description.",
                },
              ],
              timeline: [],
            },
          },
        },
        {
          ...thread.messages[0],
          id: "message-3",
          ordinal: 3,
          content: "Additional incident detail.",
          created_at: "2026-07-29T12:01:00Z",
        },
        {
          ...thread.messages[1],
          id: "message-4",
          ordinal: 4,
          content: "Latest assistant extraction.",
          metadata_json: {
            chat_extraction: {
              mode: "deterministic_demo",
              evidence: [
                {
                  evidence_id: "E-NEW",
                  title: "Latest candidate",
                  description: "Latest description.",
                },
              ],
              timeline: [
                {
                  event_id: "T-NEW",
                  timestamp: "12:30",
                  event: "Latest event.",
                  evidence_ids: ["E-NEW"],
                },
              ],
            },
          },
        },
      ],
    };
    vi.mocked(getChatThread).mockReset().mockResolvedValue(extractedThread);

    await renderLoadedPage();
    expect(screen.getByText("Latest assistant extraction.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Evidence & timeline" }));

    expect(
      screen.getByRole("heading", { name: "Chat-reported candidates" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Latest candidate")).toBeInTheDocument();
    expect(screen.getByText("Latest event.")).toBeInTheDocument();
    expect(screen.queryByText("Latest assistant extraction.")).not.toBeInTheDocument();
    expect(screen.queryByText("Older candidate")).not.toBeInTheDocument();
  });

  it("shows an empty extraction state for a thread without persisted extraction", async () => {
    await renderLoadedPage();
    fireEvent.click(screen.getByRole("tab", { name: "Evidence & timeline" }));

    expect(screen.getByText("No extraction for this chat yet")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Return to Chat" })).toBeInTheDocument();
  });

  it("shows backend report readiness and blocks generation during follow-up", async () => {
    await renderLoadedPage();
    fireEvent.click(screen.getByRole("tab", { name: "Report generation" }));

    expect(screen.getByText("Digital-forensics report")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate report" })).toBeDisabled();
    expect(
      screen.getByText(
        "Answer the pending clarification in Chat before generating a report.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText("Demo report workspace")).not.toBeInTheDocument();
  });

  it("loads persisted report history and generates a backend version", async () => {
    const reportReadyThread = makeReportReadyThread();
    const savedReport = makeReport(1);
    const generatedReport = makeReport(2);
    vi.mocked(getChatThread).mockResolvedValue(reportReadyThread);
    vi.mocked(listChatReports).mockResolvedValue([savedReport]);
    vi.mocked(generateChatReport).mockResolvedValue(generatedReport);

    await renderLoadedPage();
    fireEvent.click(screen.getByRole("tab", { name: "Report generation" }));

    expect(await screen.findByText("Persisted report version 1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate report" })).toBeEnabled();

    fireEvent.click(screen.getByRole("button", { name: "Generate report" }));

    expect(await screen.findByText("Persisted report version 2")).toBeInTheDocument();
    expect(generateChatReport).toHaveBeenCalledWith(
      "thread-1",
      expect.any(String),
    );
    expect(screen.getAllByText("Provisional / Unverified").length).toBeGreaterThan(0);
    expect(listChatReports).toHaveBeenCalledWith("thread-1", expect.any(AbortSignal));
  });

  it("downloads the selected validated report as a PDF", async () => {
    const reportReadyThread = makeReportReadyThread();
    const savedReport = makeReport(1);
    vi.mocked(getChatThread).mockResolvedValue(reportReadyThread);
    vi.mocked(listChatReports).mockResolvedValue([savedReport]);
    vi.mocked(downloadChatReportPdf).mockResolvedValue(
      new Blob(["%PDF-test"], { type: "application/pdf" }),
    );
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: vi.fn().mockReturnValue("blob:report"),
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: vi.fn(),
    });

    await renderLoadedPage();
    fireEvent.click(screen.getByRole("tab", { name: "Report generation" }));
    expect(await screen.findByText("Persisted report version 1")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Download PDF" }));

    await waitFor(() =>
      expect(downloadChatReportPdf).toHaveBeenCalledWith("thread-1", "report-1"),
    );
  });

  it("renders an actionable persisted backend failure", async () => {
    const reportReadyThread = makeReportReadyThread();
    vi.mocked(getChatThread).mockResolvedValue(reportReadyThread);
    vi.mocked(listChatReports).mockResolvedValue([
      makeFailedReport("report_validation_failed"),
    ]);

    await renderLoadedPage();
    fireEvent.click(screen.getByRole("tab", { name: "Report generation" }));

    expect(
      await screen.findByText("The report model output failed validation."),
    ).toBeInTheDocument();
    expect(screen.getByText("Failure code: report_validation_failed")).toBeInTheDocument();
    expect(
      screen.getByText(/failed attempt is preserved in report history/i),
    ).toBeInTheDocument();
  });

  it("switches workspace views from the mobile selector", async () => {
    await renderLoadedPage();
    const selector = screen.getByLabelText("Select workspace");

    fireEvent.change(selector, { target: { value: "report" } });

    expect(screen.getByText("Digital-forensics report")).toBeInTheDocument();
    expect(selector).toHaveValue("report");
  });

  it("keeps the generated report scoped to the newly selected thread", async () => {
    const otherThread: ChatThreadDetail = {
      id: "thread-2",
      title: "Other investigation",
      status: "idle",
      created_at: "2026-07-29T13:00:00Z",
      updated_at: "2026-07-29T13:01:00Z",
      messages: [
        {
          ...thread.messages[0],
          id: "message-other-1",
          thread_id: "thread-2",
          content: "Other thread narrative.",
        },
      ],
    };
    vi.mocked(listChatThreads).mockResolvedValue([thread, otherThread]);
    vi.mocked(getChatThread).mockImplementation(async (threadId) =>
      threadId === otherThread.id ? otherThread : thread,
    );

    await renderLoadedPage();
    fireEvent.change(screen.getByLabelText("Select saved chat"), {
      target: { value: otherThread.id },
    });
    expect(await screen.findByText("Other thread narrative.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Report generation" }));

    expect(await screen.findByText("No saved report for this chat")).toBeInTheDocument();
    expect(screen.queryByText("Demo report workspace")).not.toBeInTheDocument();
  });

  it("uses only the latest assistant message as the awaiting legacy fallback", async () => {
    const legacyThread: ChatThreadDetail = {
      ...thread,
      messages: thread.messages.map((message) => ({
        ...message,
        metadata_json: {},
      })),
    };
    vi.mocked(getChatThread).mockReset().mockResolvedValue(legacyThread);

    await renderLoadedPage();

    expect(
      screen.getByText("Which affected host produced this event?"),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Chat message")).toBeEnabled();
  });

  it("blocks blank answers, keeps plain Enter multiline, and submits Ctrl+Enter exactly once", async () => {
    await renderLoadedPage();
    const answer = screen.getByLabelText("Chat message");
    const send = screen.getByRole("button", { name: "Send message" });

    expect(send).toBeDisabled();
    fireEvent.change(answer, { target: { value: "   " } });
    fireEvent.keyDown(answer, {
      key: "Enter",
      code: "Enter",
      ctrlKey: true,
    });
    expect(createChatMessage).not.toHaveBeenCalled();

    fireEvent.change(answer, { target: { value: "host-7\nsecond line" } });
    fireEvent.keyDown(answer, { key: "Enter", code: "Enter" });
    expect(createChatMessage).not.toHaveBeenCalled();
    expect(answer).toHaveValue("host-7\nsecond line");

    vi.mocked(createChatMessage).mockImplementation(
      () => new Promise<ChatMessageAccepted>(() => undefined),
    );
    fireEvent.keyDown(answer, {
      key: "Enter",
      code: "Enter",
      ctrlKey: true,
    });

    await waitFor(() => expect(createChatMessage).toHaveBeenCalledTimes(1));
    expect(answer).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Send message" }),
    ).toBeDisabled();
    fireEvent.keyDown(answer, {
      key: "Enter",
      code: "Enter",
      ctrlKey: true,
    });
    expect(createChatMessage).toHaveBeenCalledTimes(1);
  });

  it("submits Cmd+NumpadEnter exactly once", async () => {
    await renderLoadedPage();
    const answer = screen.getByLabelText("Chat message");
    fireEvent.change(answer, { target: { value: "host-7" } });
    vi.mocked(createChatMessage).mockImplementation(
      () => new Promise<ChatMessageAccepted>(() => undefined),
    );

    fireEvent.keyDown(answer, {
      key: "Enter",
      code: "NumpadEnter",
      metaKey: true,
    });

    await waitFor(() => expect(createChatMessage).toHaveBeenCalledTimes(1));
  });

  it("keeps the ordinary composer enabled and reuses its key after a pre-accept failure", async () => {
    const ordinaryThread: ChatThreadDetail = {
      ...thread,
      status: "idle",
      messages: [
        thread.messages[0],
        {
          ...thread.messages[1],
          content: "The previous analysis is complete.",
          metadata_json: {},
        },
      ],
    };
    vi.mocked(listChatThreads).mockResolvedValue([ordinaryThread]);
    vi.mocked(getChatThread).mockReset().mockResolvedValue(ordinaryThread);
    vi.spyOn(window.crypto, "randomUUID").mockReturnValue(
      "00000000-0000-4000-8000-000000000003",
    );
    vi.mocked(createChatMessage)
      .mockRejectedValueOnce(new Error("network unavailable"))
      .mockImplementationOnce(
        () => new Promise<ChatMessageAccepted>(() => undefined),
      );
    await renderLoadedPage();

    const composer = screen.getByLabelText("Chat message");
    fireEvent.change(composer, {
      target: { value: "Investigate a second event" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));

    await screen.findByRole("alert");
    expect(screen.getByLabelText("Chat message")).toBeEnabled();
    expect(screen.getByLabelText("Chat message")).toHaveValue(
      "Investigate a second event",
    );
    expect(screen.getByRole("button", { name: "Send message" })).toBeEnabled();

    fireEvent.click(screen.getByRole("button", { name: "Send message" }));

    await waitFor(() => expect(createChatMessage).toHaveBeenCalledTimes(2));
    expect(vi.mocked(createChatMessage).mock.calls[0][2]).toBe(
      "00000000-0000-4000-8000-000000000003",
    );
    expect(vi.mocked(createChatMessage).mock.calls[1][2]).toBe(
      "00000000-0000-4000-8000-000000000003",
    );
  });

  it("preserves the answer and idempotency key across a pre-accept error and retry", async () => {
    vi.spyOn(window.crypto, "randomUUID").mockReturnValue(
      "00000000-0000-4000-8000-000000000001",
    );
    vi.mocked(createChatMessage)
      .mockRejectedValueOnce(new Error("network unavailable"))
      .mockImplementationOnce(
        () => new Promise<ChatMessageAccepted>(() => undefined),
      );
    await renderLoadedPage();

    const answer = screen.getByLabelText("Chat message");
    fireEvent.change(answer, { target: { value: "host-7" } });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));

    expect(
      await screen.findByRole("button", { name: "Send message" }),
    ).toBeEnabled();
    expect(screen.getByLabelText("Chat message")).toHaveValue(
      "host-7",
    );
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));

    await waitFor(() => expect(createChatMessage).toHaveBeenCalledTimes(2));
    expect(vi.mocked(createChatMessage).mock.calls[0][2]).toBe(
      "00000000-0000-4000-8000-000000000001",
    );
    expect(vi.mocked(createChatMessage).mock.calls[1][2]).toBe(
      "00000000-0000-4000-8000-000000000001",
    );
  });

  it("keeps an accepted failed follow-up retryable with the same content and key", async () => {
    const answerOne = userMessage(3, "host-7");
    const acceptedOne = accepted(answerOne, "run-1");
    const failedDetail: ChatThreadDetail = {
      ...thread,
      status: "awaiting_followup",
      messages: [...thread.messages, answerOne],
    };
    vi.spyOn(window.crypto, "randomUUID").mockReturnValue(
      "00000000-0000-4000-8000-000000000002",
    );
    vi.mocked(getChatThread)
      .mockReset()
      .mockResolvedValueOnce(thread)
      .mockResolvedValueOnce(failedDetail);
    vi.mocked(getChatRun).mockResolvedValue({
      ...acceptedOne.run,
      status: "failed",
      error_code: "rag_unavailable",
      error_message: "RAG service unavailable",
    });
    vi.mocked(createChatMessage)
      .mockResolvedValueOnce(acceptedOne)
      .mockImplementationOnce(
        () => new Promise<ChatMessageAccepted>(() => undefined),
      );
    await renderLoadedPage();
    vi.useFakeTimers();

    fireEvent.change(screen.getByLabelText("Chat message"), {
      target: { value: "host-7" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    await act(async () => {
      await Promise.resolve();
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(screen.getByRole("alert")).toHaveTextContent(
      "RAG service unavailable",
    );
    expect(screen.getByLabelText("Chat message")).toHaveValue(
      "host-7",
    );
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    await act(async () => {
      await Promise.resolve();
    });

    expect(createChatMessage).toHaveBeenCalledTimes(2);
    expect(vi.mocked(createChatMessage).mock.calls[0].slice(1, 3)).toEqual(
      vi.mocked(createChatMessage).mock.calls[1].slice(1, 3),
    );
  });

  it("uses an edited retry answer when the backend persists a second clarification", async () => {
    const oldAnswer = userMessage(3, "old-host");
    const editedAnswer = userMessage(4, "edited-host");
    const questionTwo = followUpMessage(
      5,
      "When was the event first observed?",
      2,
    );
    const acceptedOld = accepted(oldAnswer, "run-old");
    const acceptedEdited = accepted(editedAnswer, "run-edited");
    const failedDetail: ChatThreadDetail = {
      ...thread,
      status: "awaiting_followup",
      messages: [...thread.messages, oldAnswer],
    };
    const secondDetail: ChatThreadDetail = {
      ...thread,
      status: "awaiting_followup",
      messages: [...thread.messages, oldAnswer, editedAnswer, questionTwo],
    };
    vi.mocked(getChatThread)
      .mockReset()
      .mockResolvedValueOnce(thread)
      .mockResolvedValueOnce(failedDetail)
      .mockResolvedValueOnce(secondDetail);
    vi.mocked(createChatMessage)
      .mockResolvedValueOnce(acceptedOld)
      .mockResolvedValueOnce(acceptedEdited);
    vi.mocked(getChatRun)
      .mockResolvedValueOnce({
        ...acceptedOld.run,
        status: "failed",
        error_code: "rag_unavailable",
        error_message: "RAG service unavailable",
      })
      .mockResolvedValueOnce({ ...acceptedEdited.run, status: "completed" });
    await renderLoadedPage();
    vi.useFakeTimers();

    const answer = screen.getByLabelText("Chat message");
    fireEvent.change(answer, { target: { value: "old-host" } });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    await act(async () => {
      await Promise.resolve();
      await vi.advanceTimersByTimeAsync(1000);
    });

    fireEvent.change(screen.getByLabelText("Chat message"), {
      target: { value: "edited-host" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    await act(async () => {
      await Promise.resolve();
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(screen.getByText(questionTwo.content)).toBeInTheDocument();
    expect(screen.getByText(editedAnswer.content)).toBeInTheDocument();
    expect(screen.queryByText(oldAnswer.content)).not.toBeInTheDocument();
  });

  it("recovers a persisted answer after a lost POST response when the thread is reselected", async () => {
    const answer = userMessage(3, "host-7");
    const finalAnswer: PersistedChatMessage = {
      id: "message-4",
      thread_id: thread.id,
      ordinal: 4,
      role: "assistant",
      content: "The recovered terminal analysis is complete.",
      retrieval_context_id: "retrieval-1",
      metadata_json: {},
      created_at: "2026-07-29T12:03:00Z",
    };
    const terminalDetail: ChatThreadDetail = {
      ...thread,
      status: "idle",
      messages: [...thread.messages, answer, finalAnswer],
    };
    vi.mocked(getChatThread)
      .mockReset()
      .mockResolvedValueOnce(thread)
      .mockResolvedValueOnce(terminalDetail);
    vi.mocked(createChatMessage).mockRejectedValueOnce(
      new Error("response lost after acceptance"),
    );
    await renderLoadedPage();

    fireEvent.change(screen.getByLabelText("Chat message"), {
      target: { value: answer.content },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    expect(
      await screen.findByRole("button", { name: "Send message" }),
    ).toBeEnabled();

    fireEvent.change(screen.getByLabelText("Select saved chat"), {
      target: { value: thread.id },
    });

    expect(
      await screen.findByText(finalAnswer.content),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Chat message")).toBeEnabled();
    expect(screen.queryByText("More detail required")).not.toBeInTheDocument();
  });

  it("retains prior Q/A for a second follow-up, then restores the terminal transcript and composer", async () => {
    const answerOne = userMessage(3, "host-7");
    const questionTwo = followUpMessage(
      4,
      "When was the event first observed?",
      2,
    );
    const secondDetail: ChatThreadDetail = {
      ...thread,
      status: "awaiting_followup",
      messages: [...thread.messages, answerOne, questionTwo],
    };
    const answerTwo = userMessage(5, "09:32 UTC");
    const finalAnswer: PersistedChatMessage = {
      id: "message-6",
      thread_id: thread.id,
      ordinal: 6,
      role: "assistant",
      content: "The persisted terminal analysis is complete.",
      retrieval_context_id: "retrieval-1",
      metadata_json: {},
      created_at: "2026-07-29T12:03:00Z",
    };
    const terminalDetail: ChatThreadDetail = {
      ...thread,
      status: "idle",
      messages: [
        ...thread.messages,
        answerOne,
        questionTwo,
        answerTwo,
        finalAnswer,
      ],
    };
    const acceptedOne = accepted(answerOne, "run-1");
    const acceptedTwo = accepted(answerTwo, "run-2");
    vi.mocked(getChatThread)
      .mockReset()
      .mockResolvedValueOnce(thread)
      .mockResolvedValueOnce(secondDetail)
      .mockResolvedValueOnce(terminalDetail);
    vi.mocked(createChatMessage)
      .mockResolvedValueOnce(acceptedOne)
      .mockResolvedValueOnce(acceptedTwo);
    vi.mocked(getChatRun)
      .mockResolvedValueOnce({ ...acceptedOne.run, status: "completed" })
      .mockResolvedValueOnce({ ...acceptedTwo.run, status: "completed" });
    await renderLoadedPage();
    vi.useFakeTimers();

    fireEvent.change(screen.getByLabelText("Chat message"), {
      target: { value: "host-7" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    await act(async () => {
      await Promise.resolve();
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(
      screen.getByText("When was the event first observed?"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Which affected host produced this event?"),
    ).toBeInTheDocument();
    expect(screen.getByText("host-7")).toBeInTheDocument();
    expect(screen.getByLabelText("Chat message")).toHaveValue("");

    fireEvent.change(screen.getByLabelText("Chat message"), {
      target: { value: "09:32 UTC" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    await act(async () => {
      await Promise.resolve();
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(
      screen.queryByText("More detail required"),
    ).not.toBeInTheDocument();
    expect(screen.getByLabelText("Chat message")).toBeEnabled();
    expect(
      screen.getByText("The persisted terminal analysis is complete."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Which affected host produced this event?"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("When was the event first observed?"),
    ).toBeInTheDocument();
    expect(screen.getByText("09:32 UTC")).toBeInTheDocument();
  });
});
