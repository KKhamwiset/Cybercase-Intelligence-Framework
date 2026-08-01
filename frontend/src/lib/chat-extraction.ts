import type {
  ChatDemoEvidence,
  ChatDemoExtraction,
  ChatDemoTimelineEvent,
  PersistedChatMessage,
} from "@/lib/api";

export function chatDemoExtractionForMessage(
  message: PersistedChatMessage,
): ChatDemoExtraction | null {
  const raw = message.metadata_json.chat_extraction;
  if (!isRecord(raw) || raw.mode !== "deterministic_demo") return null;

  const evidence = Array.isArray(raw.evidence)
    ? raw.evidence.flatMap(parseEvidence)
    : [];
  const timeline = Array.isArray(raw.timeline)
    ? raw.timeline.flatMap(parseTimeline)
    : [];

  return {
    version: typeof raw.version === "number" ? raw.version : 1,
    mode: "deterministic_demo",
    status: "candidate",
    disclaimer:
      typeof raw.disclaimer === "string"
        ? raw.disclaimer
        : "Demo candidates must be verified against the original source.",
    evidence,
    timeline,
  };
}

export function latestChatDemoExtractionForMessages(
  messages: PersistedChatMessage[],
): ChatDemoExtraction | null {
  const latestMessage = [...messages]
    .sort((left, right) => right.ordinal - left.ordinal)
    .find(
      (message) =>
        message.role === "assistant" &&
        chatDemoExtractionForMessage(message) !== null,
    );

  return latestMessage ? chatDemoExtractionForMessage(latestMessage) : null;
}

function parseEvidence(value: unknown): ChatDemoEvidence[] {
  if (!isRecord(value)) return [];
  if (
    typeof value.evidence_id !== "string" ||
    typeof value.title !== "string" ||
    typeof value.description !== "string"
  ) {
    return [];
  }
  return [
    {
      evidence_id: value.evidence_id,
      title: value.title,
      description: value.description,
      status: "reported",
      confidence: "low",
      source_type: "chat_text",
    },
  ];
}

function parseTimeline(value: unknown): ChatDemoTimelineEvent[] {
  if (!isRecord(value)) return [];
  if (
    typeof value.event_id !== "string" ||
    typeof value.event !== "string" ||
    !Array.isArray(value.evidence_ids) ||
    !value.evidence_ids.every((item) => typeof item === "string")
  ) {
    return [];
  }
  return [
    {
      event_id: value.event_id,
      timestamp: typeof value.timestamp === "string" ? value.timestamp : null,
      event: value.event,
      status: "reported",
      evidence_ids: value.evidence_ids,
      source_type: "chat_text",
    },
  ];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
