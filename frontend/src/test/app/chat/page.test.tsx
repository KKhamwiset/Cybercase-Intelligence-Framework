import { render, screen, waitFor } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import ChatPage from "@/app/chat/page";
import {
  getChatThread,
  listChatThreads,
  type ChatThreadDetail,
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
      metadata_json: {},
      created_at: "2026-07-29T12:00:20Z",
    },
  ],
};

describe("active chat route", () => {
  beforeAll(() => {
    Object.defineProperty(Element.prototype, "scrollIntoView", {
      configurable: true,
      value: vi.fn(),
    });
  });

  beforeEach(() => {
    vi.mocked(listChatThreads).mockResolvedValue([thread]);
    vi.mocked(getChatThread).mockResolvedValue(thread);
  });

  it("keeps saved chat and awaiting composer without investigation navigation", async () => {
    render(<ChatPage />);

    expect(
      await screen.findByText("Which affected host produced this event?"),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Saved investigation").length).toBeGreaterThan(0);
    expect(screen.getByText("Recent chats")).toBeInTheDocument();
    expect(screen.getByText("Follow-up required")).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(
        /Answer the assistant.s follow-up question/,
      ),
    ).toBeEnabled();

    await waitFor(() => expect(getChatThread).toHaveBeenCalledWith(
      "thread-1",
      expect.any(AbortSignal),
    ));
    expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
    expect(screen.queryByText("Evidence")).not.toBeInTheDocument();
    expect(screen.queryByText("MITRE Mapping")).not.toBeInTheDocument();
    expect(screen.queryByText("Timeline")).not.toBeInTheDocument();
    expect(screen.queryByText("Report")).not.toBeInTheDocument();
    expect(screen.queryByText("Investigation views")).not.toBeInTheDocument();
  });
});
