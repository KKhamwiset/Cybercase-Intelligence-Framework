import { describe, expect, it } from "vitest";
import type { PersistedChatMessage } from "@/lib/api";
import {
  activeChatFollowUpForThread,
  filterSupersededClarificationAnswers,
  latestUserAnswerBetween,
} from "@/lib/chat-followup";

function message(
  ordinal: number,
  role: PersistedChatMessage["role"],
  content: string,
  metadata_json: Record<string, unknown> = {},
): PersistedChatMessage {
  return {
    id: `message-${ordinal}`,
    thread_id: "thread-1",
    ordinal,
    role,
    content,
    retrieval_context_id: null,
    metadata_json,
    created_at: `2026-07-31T12:00:${String(ordinal).padStart(2, "0")}Z`,
  };
}

function clarification(
  ordinal: number,
  content: string,
  round: number,
): PersistedChatMessage {
  return message(ordinal, "assistant", content, {
    chat_followup: {
      kind: "clarification",
      root_ordinal: 1,
      round,
    },
  });
}

describe("chat follow-up projection", () => {
  it("selects the latest user answer before the next assistant message", () => {
    const question = clarification(2, "Which host was affected?", 1);
    const firstAnswer = message(3, "user", "old-host");
    const editedAnswer = message(4, "user", "edited-host");
    const nextQuestion = clarification(5, "When was it observed?", 2);

    expect(
      latestUserAnswerBetween(
        [nextQuestion, editedAnswer, question, firstAnswer],
        question.ordinal,
        nextQuestion.ordinal,
      ),
    ).toEqual(editedAnswer);

    expect(
      activeChatFollowUpForThread(
        [nextQuestion, editedAnswer, question, firstAnswer],
        "awaiting_followup",
      ),
    ).toMatchObject({
      question: nextQuestion.content,
      entries: [{ question: question.content, answer: editedAnswer.content }],
    });
  });

  it("omits superseded retry answers from a terminal metadata-backed transcript", () => {
    const messages = [
      message(1, "user", "Investigate this event."),
      clarification(2, "Which host was affected?", 1),
      message(3, "user", "old-host"),
      message(4, "user", "edited-host"),
      clarification(5, "When was it observed?", 2),
      message(6, "user", "old-time"),
      message(7, "user", "edited-time"),
      message(8, "assistant", "The terminal analysis is complete."),
    ];

    expect(
      filterSupersededClarificationAnswers(messages).map(
        (persistedMessage) => persistedMessage.content,
      ),
    ).toEqual([
      "Investigate this event.",
      "Which host was affected?",
      "edited-host",
      "When was it observed?",
      "edited-time",
      "The terminal analysis is complete.",
    ]);
  });

  it("uses the latest assistant message for metadata-free legacy fallback", () => {
    const messages = [
      message(1, "user", "Investigate this event."),
      message(2, "assistant", "The first clarification question."),
      message(3, "assistant", "The latest clarification question."),
    ];

    expect(
      activeChatFollowUpForThread(messages, "awaiting_followup"),
    ).toEqual({
      question: "The latest clarification question.",
      entries: [],
      rootOrdinal: 1,
    });
  });
});
