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
  getChatRun,
  getChatThread,
  listChatThreads,
  type ChatMessageAccepted,
  type ChatThreadDetail,
  type PersistedChatMessage,
} from "@/lib/api";

vi.mock("@/lib/api", () => ({
  createChatMessage: vi.fn(),
  createChatThread: vi.fn(),
  deleteChatThread: vi.fn(),
  getApiErrorMessage: vi.fn(
    (_error: unknown, fallback: string) => fallback,
  ),
  getChatRun: vi.fn(),
  getChatThread: vi.fn(),
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

  it("generates the selected thread's client-side demo report on demand", async () => {
    await renderLoadedPage();
    fireEvent.click(screen.getByRole("tab", { name: "Report generation" }));

    expect(screen.getByText("Demo report workspace")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate demo report" })).toBeEnabled();
    expect(
      screen.queryByRole("heading", { name: /1\. Case Summary/ }),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Generate demo report" }));

    expect(
      screen.getByRole("heading", { name: /1\. Case Summary/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /7\. System Limitations/ }),
    ).toBeInTheDocument();
    expect(screen.getByText("Incomplete / Unverified")).toBeInTheDocument();
    expect(screen.getByText("No persisted extraction evidence candidates are available.")).toBeInTheDocument();
  });

  it("switches workspace views from the mobile selector", async () => {
    await renderLoadedPage();
    const selector = screen.getByLabelText("Select workspace");

    fireEvent.change(selector, { target: { value: "report" } });

    expect(screen.getByText("Demo report workspace")).toBeInTheDocument();
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
    fireEvent.click(screen.getByRole("button", { name: "Generate demo report" }));

    expect(
      screen.getByRole("heading", { name: "Other investigation" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Other thread narrative.")).toBeInTheDocument();
    expect(screen.queryByText("Investigate this PowerShell event.")).not.toBeInTheDocument();
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
