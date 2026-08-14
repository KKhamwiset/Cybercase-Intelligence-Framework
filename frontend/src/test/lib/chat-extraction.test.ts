import { describe, expect, it } from "vitest";
import type { PersistedChatMessage } from "@/lib/api";
import {
  chatBaselineExtractionForMessage,
  latestChatExtractionForMessages,
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

function baselineRelationshipMetadata(
  relationshipOverrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    chat_extraction: {
      version: "baseline_extraction_v1",
      mode: "single_pass_llm",
      status: "candidate",
      prompt_version: "baseline_extraction_prompt_v2",
      provider: "anthropic",
      model: "claude-haiku-4-5-20251001",
      validation_status: "validated",
      latency_ms: 12,
      input_tokens: 10,
      output_tokens: 20,
      source_message_ids: ["message-1"],
      raw_response: null,
      case_summary: "An account sign-in from host-7 was reported.",
      entities: [
        {
          entity_id: "ENT-001",
          name: "Employee account",
          entity_type: "account",
          reported_role: null,
          confidence: "high",
          source_message_ids: ["message-1"],
        },
        {
          entity_id: "ENT-002",
          name: "host-7",
          entity_type: "host",
          reported_role: null,
          confidence: "high",
          source_message_ids: ["message-1"],
        },
      ],
      relationships: [
        {
          relationship_id: "REL-001",
          subject_entity_id: "ENT-001",
          predicate: "signed_in_from",
          object_entity_id: "ENT-002",
          statement: "The employee account signed in from host-7.",
          status: "reported",
          confidence: "high",
          source_message_ids: ["message-1"],
          ...relationshipOverrides,
        },
      ],
      evidence: [],
      timeline: [],
      missing_information: [],
      warnings: [],
    },
  };
}

describe("chat baseline extraction metadata", () => {
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
      relationships: [],
    });
  });

  it("returns the latest assistant extraction by descending ordinal", () => {
    const older = message(
      {
        chat_extraction: {
          version: "baseline_extraction_v1",
          mode: "single_pass_llm",
          status: "candidate",
          prompt_version: "baseline_extraction_prompt_v1",
          provider: "anthropic",
          model: "claude-sonnet-4-20250514",
          validation_status: "validated",
          latency_ms: 10,
          input_tokens: 10,
          output_tokens: 10,
          source_message_ids: ["message-1"],
          raw_response: null,
          case_summary: "Older summary.",
          entities: [],
          relationships: [],
          evidence: [
            {
              evidence_id: "E-OLD",
              title: "Older candidate",
              description: "Older description.",
              artifact_type: "log",
              status: "reported",
              confidence: "low",
              source_type: "user_reported",
              source_message_ids: ["message-1"],
            },
          ],
          timeline: [],
          missing_information: [],
          warnings: [],
        },
      },
      2,
    );
    const newer = message(
      {
        chat_extraction: {
          version: "baseline_extraction_v1",
          mode: "single_pass_llm",
          status: "candidate",
          prompt_version: "baseline_extraction_prompt_v1",
          provider: "anthropic",
          model: "claude-sonnet-4-20250514",
          validation_status: "validated",
          latency_ms: 10,
          input_tokens: 10,
          output_tokens: 10,
          source_message_ids: ["message-3"],
          raw_response: null,
          case_summary: "Newer summary.",
          entities: [],
          relationships: [],
          evidence: [
            {
              evidence_id: "E-NEW",
              title: "Latest candidate",
              description: "Latest description.",
              artifact_type: "log",
              status: "reported",
              confidence: "high",
              source_type: "user_reported",
              source_message_ids: ["message-3"],
            },
          ],
          timeline: [],
          missing_information: [],
          warnings: [],
        },
      },
      4,
    );

    expect(
      latestChatExtractionForMessages([newer, older]),
    ).toMatchObject({
      evidence: [{ evidence_id: "E-NEW", title: "Latest candidate" }],
    });
  });

  it("parses source-explicit entity relationships", () => {
    const extraction = chatBaselineExtractionForMessage(
      message(baselineRelationshipMetadata()),
    );

    expect(extraction).toMatchObject({
      status: "candidate",
      relationships: [
        {
          relationship_id: "REL-001",
          subject_entity_id: "ENT-001",
          predicate: "signed_in_from",
          object_entity_id: "ENT-002",
          status: "reported",
          source_message_ids: ["message-1"],
        },
      ],
    });
  });

  it("rejects a malformed present relationship collection or item", () => {
    const malformedCollection = baselineRelationshipMetadata();
    const extractionMetadata = malformedCollection.chat_extraction as Record<
      string,
      unknown
    >;
    extractionMetadata.relationships = { relationship_id: "REL-001" };

    expect(
      chatBaselineExtractionForMessage(message(malformedCollection)),
    ).toBeNull();
    expect(
      chatBaselineExtractionForMessage(
        message(baselineRelationshipMetadata({ predicate: "owns Host 7" })),
      ),
    ).toBeNull();
  });

  it("rejects unresolved relationship endpoints and self-edges", () => {
    expect(
      chatBaselineExtractionForMessage(
        message(
          baselineRelationshipMetadata({ object_entity_id: "ENT-404" }),
        ),
      ),
    ).toBeNull();
    expect(
      chatBaselineExtractionForMessage(
        message(
          baselineRelationshipMetadata({ object_entity_id: "ENT-001" }),
        ),
      ),
    ).toBeNull();
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
