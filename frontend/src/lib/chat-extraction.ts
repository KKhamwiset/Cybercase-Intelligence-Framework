import type {
  ChatBaselineEntity,
  ChatBaselineEvidence,
  ChatBaselineExtraction,
  ChatBaselineExtractionFailure,
  ChatBaselineMissingInformation,
  ChatBaselineTimelineEvent,
  ChatDemoEvidence,
  ChatDemoExtraction,
  ChatDemoTimelineEvent,
  ChatExtraction,
  PersistedChatMessage,
} from "@/lib/api";

export function chatDemoExtractionForMessage(
  message: PersistedChatMessage,
): ChatDemoExtraction | null {
  if (message.role !== "assistant") return null;
  const raw = message.metadata_json.chat_extraction;
  if (!isRecord(raw) || raw.mode !== "deterministic_demo") return null;

  const evidence = Array.isArray(raw.evidence)
    ? raw.evidence.flatMap(parseDemoEvidence)
    : [];
  const timeline = Array.isArray(raw.timeline)
    ? raw.timeline.flatMap(parseDemoTimeline)
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

export function chatBaselineExtractionForMessage(
  message: PersistedChatMessage,
): ChatBaselineExtraction | ChatBaselineExtractionFailure | null {
  if (message.role !== "assistant") return null;
  const raw = message.metadata_json.chat_extraction;
  if (!isRecord(raw)) return null;
  if (
    raw.version !== "baseline_extraction_v1" ||
    raw.mode !== "single_pass_llm"
  ) {
    return null;
  }

  const metadata = baselineMetadata(raw);
  if (raw.status === "failed") {
    if (typeof raw.failure_code !== "string") return null;
    return {
      ...metadata,
      status: "failed",
      validation_status: "failed",
      failure_code: raw.failure_code,
      failure_message:
        typeof raw.failure_message === "string"
          ? raw.failure_message
          : "The extraction did not produce a validated result.",
    };
  }
  if (raw.status !== "candidate" || typeof raw.case_summary !== "string") {
    return null;
  }

  const entities = Array.isArray(raw.entities)
    ? raw.entities.flatMap(parseBaselineEntity)
    : [];
  const evidence = Array.isArray(raw.evidence)
    ? raw.evidence.flatMap(parseBaselineEvidence)
    : [];
  const timeline = Array.isArray(raw.timeline)
    ? raw.timeline.flatMap(parseBaselineTimeline)
    : [];
  const missingInformation = Array.isArray(raw.missing_information)
    ? raw.missing_information.flatMap(parseBaselineMissingInformation)
    : [];
  const warnings = parseStringArray(raw.warnings);
  if (
    (Array.isArray(raw.entities) && entities.length !== raw.entities.length) ||
    (Array.isArray(raw.evidence) && evidence.length !== raw.evidence.length) ||
    (Array.isArray(raw.timeline) && timeline.length !== raw.timeline.length) ||
    (Array.isArray(raw.missing_information) &&
      missingInformation.length !== raw.missing_information.length) ||
    (raw.warnings !== undefined && warnings === null)
  ) {
    return null;
  }

  return {
    ...metadata,
    status: "candidate",
    validation_status: "validated",
    case_summary: raw.case_summary,
    entities,
    evidence,
    timeline,
    missing_information: missingInformation,
    warnings: warnings ?? [],
  };
}

export function chatExtractionForMessage(
  message: PersistedChatMessage,
): ChatExtraction | null {
  return (
    chatBaselineExtractionForMessage(message) ??
    chatDemoExtractionForMessage(message)
  );
}

export function latestChatExtractionForMessages(
  messages: PersistedChatMessage[],
): ChatExtraction | null {
  const latestMessage = [...messages]
    .sort((left, right) => right.ordinal - left.ordinal)
    .find((message) => chatExtractionForMessage(message) !== null);
  return latestMessage ? chatExtractionForMessage(latestMessage) : null;
}

function parseDemoEvidence(value: unknown): ChatDemoEvidence[] {
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

function parseDemoTimeline(value: unknown): ChatDemoTimelineEvent[] {
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

function parseBaselineEntity(value: unknown): ChatBaselineEntity[] {
  if (!isRecord(value)) return [];
  if (
    !isNonEmptyString(value.entity_id) ||
    !isNonEmptyString(value.name) ||
    !isNonEmptyString(value.entity_type) ||
    !isConfidence(value.confidence) ||
    !isStringArray(value.source_message_ids)
  ) {
    return [];
  }
  if (value.reported_role !== null && !isNonEmptyString(value.reported_role)) {
    return [];
  }
  return [
    {
      entity_id: value.entity_id,
      name: value.name,
      entity_type: value.entity_type,
      reported_role: value.reported_role ?? null,
      confidence: value.confidence,
      source_message_ids: value.source_message_ids,
    },
  ];
}

function parseBaselineEvidence(value: unknown): ChatBaselineEvidence[] {
  if (!isRecord(value)) return [];
  if (
    !isNonEmptyString(value.evidence_id) ||
    !isNonEmptyString(value.title) ||
    !isNonEmptyString(value.description) ||
    !isNonEmptyString(value.artifact_type) ||
    !isReportedStatus(value.status) ||
    !isConfidence(value.confidence) ||
    value.source_type !== "user_reported" ||
    !isStringArray(value.source_message_ids)
  ) {
    return [];
  }
  return [
    {
      evidence_id: value.evidence_id,
      title: value.title,
      description: value.description,
      artifact_type: value.artifact_type,
      status: value.status,
      confidence: value.confidence,
      source_type: "user_reported",
      source_message_ids: value.source_message_ids,
    },
  ];
}

function parseBaselineTimeline(value: unknown): ChatBaselineTimelineEvent[] {
  if (!isRecord(value)) return [];
  if (
    !isNonEmptyString(value.event_id) ||
    !isNonEmptyString(value.event) ||
    !isStringArray(value.actors) ||
    !isStringArray(value.evidence_ids) ||
    !isReportedStatus(value.status) ||
    !isConfidence(value.confidence) ||
    !isStringArray(value.source_message_ids)
  ) {
    return [];
  }
  if (
    value.timestamp !== null &&
    value.timestamp !== undefined &&
    !isNonEmptyString(value.timestamp)
  ) {
    return [];
  }
  if (
    value.timestamp_text !== null &&
    value.timestamp_text !== undefined &&
    !isNonEmptyString(value.timestamp_text)
  ) {
    return [];
  }
  return [
    {
      event_id: value.event_id,
      timestamp: value.timestamp ?? null,
      timestamp_text: value.timestamp_text ?? null,
      event: value.event,
      actors: value.actors,
      evidence_ids: value.evidence_ids,
      status: value.status,
      confidence: value.confidence,
      source_message_ids: value.source_message_ids,
    },
  ];
}

function parseBaselineMissingInformation(
  value: unknown,
): ChatBaselineMissingInformation[] {
  if (!isRecord(value)) return [];
  if (
    !isNonEmptyString(value.missing_id) ||
    !isNonEmptyString(value.description) ||
    !isImportance(value.importance) ||
    !isStringArray(value.source_message_ids)
  ) {
    return [];
  }
  return [
    {
      missing_id: value.missing_id,
      description: value.description,
      importance: value.importance,
      source_message_ids: value.source_message_ids,
    },
  ];
}

function baselineMetadata(raw: Record<string, unknown>) {
  return {
    version: "baseline_extraction_v1" as const,
    mode: "single_pass_llm" as const,
    prompt_version:
      typeof raw.prompt_version === "string"
        ? raw.prompt_version
        : "baseline_extraction_prompt_v1",
    provider: typeof raw.provider === "string" ? raw.provider : "unknown",
    model: typeof raw.model === "string" ? raw.model : "unknown",
    latency_ms: typeof raw.latency_ms === "number" ? raw.latency_ms : 0,
    input_tokens: typeof raw.input_tokens === "number" ? raw.input_tokens : null,
    output_tokens:
      typeof raw.output_tokens === "number" ? raw.output_tokens : null,
    source_message_ids: isStringArray(raw.source_message_ids)
      ? raw.source_message_ids
      : [],
    raw_response: typeof raw.raw_response === "string" ? raw.raw_response : null,
  };
}

function isConfidence(value: unknown): value is ChatBaselineEntity["confidence"] {
  return (
    value === "high" ||
    value === "medium" ||
    value === "low" ||
    value === "unknown"
  );
}

function isReportedStatus(value: unknown): value is ChatBaselineEvidence["status"] {
  return (
    value === "reported" || value === "unknown" || value === "not_confirmed"
  );
}

function isImportance(
  value: unknown,
): value is ChatBaselineMissingInformation["importance"] {
  return (
    value === "material" ||
    value === "important" ||
    value === "useful" ||
    value === "unknown"
  );
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function parseStringArray(value: unknown): string[] | null {
  if (value === undefined) return [];
  return isStringArray(value) ? value : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
