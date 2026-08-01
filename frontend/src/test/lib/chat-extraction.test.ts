import { describe, expect, it } from "vitest";
import type { PersistedChatMessage } from "@/lib/api";
import {
  chatDemoExtractionForMessage,
  latestChatDemoExtractionForMessages,
} from "@/lib/chat-extraction";

function message(
  metadata_json: Record<string, unknown>,
  ordinal = 1,
): PersistedChatMessage {
  return {
    id: `message-${ordinal}`,
    thread_id: "thread-1",
    ordinal,
    role: "assistant",
    content: "The analysis is complete.",
    retrieval_context_id: null,
    metadata_json,
    created_at: "2026-08-01T12:00:00Z",
  };
}

describe("chat demo extraction metadata", () => {
  it("accepts persisted evidence and timeline candidates", () => {
    const extraction = chatDemoExtractionForMessage(
      message({
        chat_extraction: {
          version: 1,
          mode: "deterministic_demo",
          status: "candidate",
          disclaimer: "Verify this demo output.",
          evidence: [
            {
              evidence_id: "E-001",
              title: "Endpoint log",
              description: "The endpoint log recorded a new process.",
            },
          ],
          timeline: [
            {
              event_id: "T-001",
              timestamp: "12:30",
              event: "A new process was recorded.",
              evidence_ids: ["E-001"],
            },
          ],
        },
      }),
    );

    expect(extraction).toMatchObject({
      mode: "deterministic_demo",
      evidence: [{ evidence_id: "E-001" }],
      timeline: [{ timestamp: "12:30", evidence_ids: ["E-001"] }],
    });
  });

  it("ignores non-demo metadata", () => {
    expect(
      chatDemoExtractionForMessage(message({ mitre_table: [] })),
    ).toBeNull();
  });

  it("returns the latest assistant extraction by descending ordinal", () => {
    const older = message(
      {
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
      2,
    );
    const newer = message(
      {
        chat_extraction: {
          mode: "deterministic_demo",
          evidence: [
            {
              evidence_id: "E-NEW",
              title: "Latest candidate",
              description: "Latest description.",
            },
          ],
          timeline: [],
        },
      },
      4,
    );

    expect(
      latestChatDemoExtractionForMessages([newer, older]),
    ).toMatchObject({
      evidence: [{ evidence_id: "E-NEW", title: "Latest candidate" }],
    });
  });
});
