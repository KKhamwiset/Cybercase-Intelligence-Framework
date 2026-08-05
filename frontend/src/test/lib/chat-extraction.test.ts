import { describe, expect, it } from "vitest";
import type { PersistedChatMessage } from "@/lib/api";
import {
  chatBaselineExtractionForMessage,
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

  it("parses the versioned baseline extraction and its provenance fields", () => {
    const extraction = chatBaselineExtractionForMessage(
      message({
        chat_extraction: {
          version: "baseline_extraction_v1",
          mode: "single_pass_llm",
          status: "candidate",
          prompt_version: "baseline_extraction_prompt_v1",
          provider: "anthropic",
          model: "claude-sonnet-4-20250514",
          validation_status: "validated",
          latency_ms: 12.5,
          input_tokens: 10,
          output_tokens: 20,
          source_message_ids: ["message-1"],
          raw_response: null,
          case_summary: "A phishing email was reported.",
          entities: [
            {
              entity_id: "ENT-001",
              name: "Microsoft 365 account",
              entity_type: "account",
              reported_role: "compromised account",
              confidence: "high",
              source_message_ids: ["message-1"],
            },
          ],
          evidence: [
            {
              evidence_id: "E-001",
              title: "Sign-in record",
              description: "A suspicious sign-in was reported.",
              artifact_type: "identity_log",
              status: "reported",
              confidence: "medium",
              source_type: "user_reported",
              source_message_ids: ["message-1"],
            },
          ],
          timeline: [
            {
              event_id: "T-001",
              timestamp: null,
              timestamp_text: "The exact time is unknown.",
              event: "A suspicious sign-in was reported.",
              actors: [],
              evidence_ids: ["E-001"],
              status: "unknown",
              confidence: "unknown",
              source_message_ids: ["message-1"],
            },
          ],
          missing_information: [],
          warnings: [],
        },
      }),
    );

    expect(extraction).toMatchObject({
      mode: "single_pass_llm",
      status: "candidate",
      case_summary: "A phishing email was reported.",
      evidence: [{ source_type: "user_reported" }],
      timeline: [{ timestamp: null, status: "unknown" }],
    });
  });

  it("parses an explicit baseline extraction failure without inventing items", () => {
    const extraction = chatBaselineExtractionForMessage(
      message({
        chat_extraction: {
          version: "baseline_extraction_v1",
          mode: "single_pass_llm",
          status: "failed",
          prompt_version: "baseline_extraction_prompt_v1",
          provider: "anthropic",
          model: "claude-sonnet-4-20250514",
          validation_status: "failed",
          latency_ms: 3,
          input_tokens: null,
          output_tokens: null,
          source_message_ids: ["message-1"],
          raw_response: null,
          failure_code: "extraction_invalid_json",
          failure_message: "The extraction model did not return valid JSON.",
        },
      }),
    );

    expect(extraction).toMatchObject({
      mode: "single_pass_llm",
      status: "failed",
      failure_code: "extraction_invalid_json",
    });
  });
});
