import type {
  ChatBaselineEntity,
  ChatBaselineEvidence,
  ChatBaselineExtraction,
  ChatBaselineExtractionFailure,
  ChatBaselineMissingInformation,
  ChatBaselineRelationship,
  ChatBaselineTimelineEvent,
  ChatExtraction,
  PersistedChatMessage,
} from "@/lib/api";

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

  if (
    (raw.entities !== undefined && !Array.isArray(raw.entities)) ||
    (raw.evidence !== undefined && !Array.isArray(raw.evidence)) ||
    (raw.timeline !== undefined && !Array.isArray(raw.timeline)) ||
    (raw.relationships !== undefined && !Array.isArray(raw.relationships)) ||
    (raw.missing_information !== undefined &&
      !Array.isArray(raw.missing_information))
  ) {
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
    warnings === null
  ) {
    return null;
  }

  const entityIds = new Set<string>();
  for (const entity of entities) {
    if (entityIds.has(entity.entity_id)) return null;
    entityIds.add(entity.entity_id);
  }

  const evidenceIds = new Set<string>();
  for (const item of evidence) {
    if (evidenceIds.has(item.evidence_id)) return null;
    evidenceIds.add(item.evidence_id);
  }

  const timelineIds = new Set<string>();
  for (const event of timeline) {
    if (timelineIds.has(event.event_id)) return null;
    if (event.evidence_ids.some((id) => !evidenceIds.has(id))) return null;
    timelineIds.add(event.event_id);
  }

  const rawRelationships = Array.isArray(raw.relationships)
    ? raw.relationships
    : [];
  const relationships = rawRelationships.flatMap(parseBaselineRelationship);
  if (relationships.length !== rawRelationships.length) return null;

  const relationshipIds = new Set<string>();
  const semanticEdges = new Set<string>();
  for (const relationship of relationships) {
    if (relationshipIds.has(relationship.relationship_id)) return null;
    if (
      !entityIds.has(relationship.subject_entity_id) ||
      !entityIds.has(relationship.object_entity_id) ||
      relationship.subject_entity_id === relationship.object_entity_id
    ) {
      return null;
    }
    const semanticEdge = `${relationship.subject_entity_id}\u0000${relationship.predicate}\u0000${relationship.object_entity_id}`;
    if (semanticEdges.has(semanticEdge)) return null;
    relationshipIds.add(relationship.relationship_id);
    semanticEdges.add(semanticEdge);
  }

  return {
    ...metadata,
    status: "candidate",
    validation_status: "validated",
    case_summary: raw.case_summary,
    entities,
    relationships,
    evidence,
    timeline,
    missing_information: missingInformation,
    warnings: warnings ?? [],
  };
}

export function chatExtractionForMessage(
  message: PersistedChatMessage,
): ChatExtraction | null {
  return chatBaselineExtractionForMessage(message);
}

export function latestChatExtractionForMessages(
  messages: PersistedChatMessage[],
): ChatExtraction | null {
  const latestMessage = [...messages]
    .sort((left, right) => right.ordinal - left.ordinal)
    .find((message) => chatExtractionForMessage(message) !== null);
  return latestMessage ? chatExtractionForMessage(latestMessage) : null;
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

function parseBaselineRelationship(value: unknown): ChatBaselineRelationship[] {
  if (!isRecord(value)) return [];
  if (
    !isNonEmptyString(value.relationship_id) ||
    !isNonEmptyString(value.subject_entity_id) ||
    !isRelationshipPredicate(value.predicate) ||
    !isNonEmptyString(value.object_entity_id) ||
    !isNonEmptyString(value.statement) ||
    !isRelationshipStatus(value.status) ||
    !isConfidence(value.confidence) ||
    !isStringArray(value.source_message_ids) ||
    value.source_message_ids.length === 0 ||
    new Set(value.source_message_ids).size !== value.source_message_ids.length
  ) {
    return [];
  }
  return [
    {
      relationship_id: value.relationship_id,
      subject_entity_id: value.subject_entity_id,
      predicate: value.predicate,
      object_entity_id: value.object_entity_id,
      statement: value.statement,
      status: value.status,
      confidence: value.confidence,
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

function isRelationshipStatus(
  value: unknown,
): value is ChatBaselineRelationship["status"] {
  return (
    value === "reported" ||
    value === "suspected" ||
    value === "contradicted" ||
    value === "not_established"
  );
}

function isRelationshipPredicate(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length <= 80 &&
    /^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$/.test(value)
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
