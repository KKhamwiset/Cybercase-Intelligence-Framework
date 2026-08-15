/**
 * API client for the persistent chat workspace.
 */
import axios from "axios";

const CHAT_POLL_REQUEST_TIMEOUT_MS = 15_000;

export function getApiBaseUrl(): string {
  let url = process.env.NEXT_PUBLIC_API_URL;
  if (!url) {
    if (typeof window !== "undefined") {
      throw new Error(
        "NEXT_PUBLIC_API_URL is not set. The application cannot start.",
      );
    }
    return "http://build-time-placeholder";
  }

  if (!url.startsWith("http")) {
    url = "https://" + url;
  }

  if (!url.endsWith("/api/v1") && !url.endsWith("/api/v1/")) {
    url = url.endsWith("/") ? url + "api/v1" : url + "/api/v1";
  }

  return url;
}

export type ThreadStatus =
  | "idle"
  | "processing"
  | "awaiting_followup"
  | "answered"
  | "failed";

export type ChatMessageAction = "ask" | "add_case_info";

export type RunStatus = "queued" | "running" | "completed" | "failed";

export interface ChatThreadRead {
  id: string;
  title: string;
  status: ThreadStatus;
  created_at: string;
  updated_at: string;
}

export interface PersistedChatMessage {
  id: string;
  thread_id: string;
  ordinal: number;
  role: "user" | "assistant";
  content: string;
  retrieval_context_id: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ChatThreadDetail extends ChatThreadRead {
  messages: PersistedChatMessage[];
}

export interface ChatRun {
  id: string;
  thread_id: string;
  request_message_id: string;
  operation: "query" | "resume";
  status: RunStatus;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatMessageAccepted {
  message: PersistedChatMessage;
  run: ChatRun;
}

export type ChatReportSupportType =
  | "user_reported"
  | "extraction_candidate"
  | "general_technical_knowledge"
  | "mitre_mapping_candidate"
  | "unknown";

export interface ChatReportClaim {
  claim_id: string;
  section_id: string;
  text: string;
  support_type: ChatReportSupportType;
  evidence_ids: string[];
  timeline_event_ids: string[];
  mitre_technique_ids: string[];
}

export interface ChatReportSection {
  section_id: string;
  heading: string;
  paragraphs: string[];
  items: string[];
}

export interface ChatStructuredReport {
  report_version: "baseline_report_v1";
  status: "provisional_unverified";
  title: string;
  sections: ChatReportSection[];
  claims: ChatReportClaim[];
  limitations: string[];
}

export interface ChatReportRead {
  report_id: string;
  thread_id: string;
  version_number: number;
  idempotency_key: string;
  source_snapshot_hash: string;
  extraction_id: string;
  extraction_version: string;
  prompt_version: string;
  provider: string;
  model: string;
  decoding_settings: Record<string, unknown>;
  persistence_status: "completed" | "failed";
  validation_status: "validated" | "failed";
  report: ChatStructuredReport | null;
  validation_errors: string[];
  failure_code: string | null;
  failure_message: string | null;
  created_at: string;
  finished_at: string | null;
  latency_ms: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
}

export type ChatExtractionConfidence = "high" | "medium" | "low" | "unknown";
export type ChatReportedStatus = "reported" | "unknown" | "not_confirmed";
export type ChatRelationshipStatus =
  | "reported"
  | "suspected"
  | "contradicted"
  | "not_established";

export interface ChatBaselineEntity {
  entity_id: string;
  name: string;
  entity_type: string;
  reported_role: string | null;
  confidence: ChatExtractionConfidence;
  source_message_ids: string[];
}

export interface ChatBaselineRelationship {
  relationship_id: string;
  subject_entity_id: string;
  predicate: string;
  object_entity_id: string;
  statement: string;
  status: ChatRelationshipStatus;
  confidence: ChatExtractionConfidence;
  source_message_ids: string[];
}

export interface ChatBaselineEvidence {
  evidence_id: string;
  title: string;
  description: string;
  artifact_type: string;
  status: ChatReportedStatus;
  confidence: ChatExtractionConfidence;
  source_type: "user_reported";
  source_message_ids: string[];
}

export interface ChatBaselineTimelineEvent {
  event_id: string;
  timestamp: string | null;
  timestamp_text: string | null;
  event: string;
  actors: string[];
  evidence_ids: string[];
  status: ChatReportedStatus;
  confidence: ChatExtractionConfidence;
  source_message_ids: string[];
}

export interface ChatBaselineMissingInformation {
  missing_id: string;
  description: string;
  importance: "material" | "important" | "useful" | "unknown";
  source_message_ids: string[];
}

export interface ChatBaselineExtraction {
  version: "baseline_extraction_v1";
  mode: "single_pass_llm";
  status: "candidate";
  case_summary: string;
  entities: ChatBaselineEntity[];
  relationships: ChatBaselineRelationship[];
  evidence: ChatBaselineEvidence[];
  timeline: ChatBaselineTimelineEvent[];
  missing_information: ChatBaselineMissingInformation[];
  warnings: string[];
  prompt_version: string;
  provider: string;
  model: string;
  validation_status: "validated";
  latency_ms: number;
  input_tokens: number | null;
  output_tokens: number | null;
  source_message_ids: string[];
  raw_response: string | null;
}

export interface ChatBaselineExtractionFailure {
  version: "baseline_extraction_v1";
  mode: "single_pass_llm";
  status: "failed";
  prompt_version: string;
  provider: string;
  model: string;
  validation_status: "failed";
  latency_ms: number;
  input_tokens: number | null;
  output_tokens: number | null;
  source_message_ids: string[];
  raw_response: string | null;
  failure_code: string;
  failure_message: string;
}

export type ChatExtraction =
  | ChatBaselineExtraction
  | ChatBaselineExtractionFailure;

export const listChatThreads = async (
  signal?: AbortSignal,
): Promise<ChatThreadRead[]> => {
  const response = await axios.get<ChatThreadRead[]>(`${getApiBaseUrl()}/chats`, {
    signal,
  });
  return response.data;
};

export const createChatThread = async (
  title: string = "New chat",
  signal?: AbortSignal,
): Promise<ChatThreadRead> => {
  const response = await axios.post<ChatThreadRead>(
    `${getApiBaseUrl()}/chats`,
    { title },
    { signal },
  );
  return response.data;
};

export const getChatThread = async (
  threadId: string,
  signal?: AbortSignal,
): Promise<ChatThreadDetail> => {
  const response = await axios.get<ChatThreadDetail>(
    `${getApiBaseUrl()}/chats/${encodeURIComponent(threadId)}`,
    { signal, timeout: CHAT_POLL_REQUEST_TIMEOUT_MS },
  );
  return response.data;
};

export const updateChatThread = async (
  threadId: string,
  title: string,
  signal?: AbortSignal,
): Promise<ChatThreadRead> => {
  const response = await axios.patch<ChatThreadRead>(
    `${getApiBaseUrl()}/chats/${encodeURIComponent(threadId)}`,
    { title },
    { signal },
  );
  return response.data;
};

export const deleteChatThread = async (
  threadId: string,
  signal?: AbortSignal,
): Promise<void> => {
  await axios.delete(`${getApiBaseUrl()}/chats/${encodeURIComponent(threadId)}`, {
    signal,
  });
};

export const createChatMessage = async (
  threadId: string,
  content: string,
  idempotencyKey: string,
  signal?: AbortSignal,
  action?: ChatMessageAction,
): Promise<ChatMessageAccepted> => {
  const response = await axios.post<ChatMessageAccepted>(
    `${getApiBaseUrl()}/chats/${encodeURIComponent(threadId)}/messages`,
    {
      content,
      idempotency_key: idempotencyKey,
      ...(action ? { action } : {}),
    },
    { signal },
  );
  return response.data;
};

export const getChatRun = async (
  threadId: string,
  runId: string,
  signal?: AbortSignal,
): Promise<ChatRun> => {
  const response = await axios.get<ChatRun>(
    `${getApiBaseUrl()}/chats/${encodeURIComponent(threadId)}/runs/${encodeURIComponent(runId)}`,
    { signal, timeout: CHAT_POLL_REQUEST_TIMEOUT_MS },
  );
  return response.data;
};

export const listChatReports = async (
  threadId: string,
  signal?: AbortSignal,
): Promise<ChatReportRead[]> => {
  const response = await axios.get<ChatReportRead[]>(
    `${getApiBaseUrl()}/chats/${encodeURIComponent(threadId)}/reports`,
    { signal },
  );
  return response.data;
};

export const getChatReport = async (
  threadId: string,
  reportId: string,
  signal?: AbortSignal,
): Promise<ChatReportRead> => {
  const response = await axios.get<ChatReportRead>(
    `${getApiBaseUrl()}/chats/${encodeURIComponent(threadId)}/reports/${encodeURIComponent(reportId)}`,
    { signal },
  );
  return response.data;
};

export const downloadChatReportPdf = async (
  threadId: string,
  reportId: string,
  signal?: AbortSignal,
): Promise<Blob> => {
  const response = await axios.get<Blob>(
    `${getApiBaseUrl()}/chats/${encodeURIComponent(threadId)}/reports/${encodeURIComponent(reportId)}/pdf`,
    { signal, responseType: "blob", timeout: 120_000 },
  );
  return response.data;
};

export const generateChatReport = async (
  threadId: string,
  idempotencyKey?: string,
  signal?: AbortSignal,
): Promise<ChatReportRead> => {
  const response = await axios.post<ChatReportRead>(
    `${getApiBaseUrl()}/chats/${encodeURIComponent(threadId)}/reports`,
    idempotencyKey ? { idempotency_key: idempotencyKey } : {},
    { signal, timeout: 120_000 },
  );
  return response.data;
};

export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data;
    if (typeof data === "string" && data.trim()) return data.trim();
    if (data && typeof data === "object" && "detail" in data) {
      const detail = (data as { detail?: unknown }).detail;
      if (typeof detail === "string" && detail.trim()) return detail.trim();
      if (Array.isArray(detail) && detail.length > 0) {
        const first = detail[0];
        if (typeof first === "string" && first.trim()) return first.trim();
        if (
          first &&
          typeof first === "object" &&
          "msg" in first &&
          typeof first.msg === "string"
        ) {
          return first.msg.trim();
        }
      }
    }
  }
  if (error instanceof Error && error.message.trim()) {
    return error.message.trim();
  }
  return fallback;
}
