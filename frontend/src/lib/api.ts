/**
 * API Client for CyberCase Framework Backend
 */
import axios from "axios";

const CHAT_POLL_REQUEST_TIMEOUT_MS = 15_000;

function getApiBaseUrl(): string {
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
    url = `https://${url}`;
  }

  if (!url.endsWith("/api/v1") && !url.endsWith("/api/v1/")) {
    url = url.endsWith("/") ? `${url}api/v1` : `${url}/api/v1`;
  }

  return url;
}

interface HealthStatus {
  status: string;
  database: "loading" | "connected" | "error" | "disconnected";
  version: string;
}

export async function getHealthStatus(): Promise<HealthStatus> {
  const baseUrl = getApiBaseUrl();
  try {
    const response = await axios.get<HealthStatus>(`${baseUrl}/health`, {
      timeout: 5000,
    });

    return response.data;
  } catch (error) {
    console.error("Health check failed:", error);
    return {
      status: "error",
      database: "error",
      version: "unknown",
    };
  }
}

export interface MitreContextEntry {
  technique_id?: string;
  name?: string;
  entity_type?: string;
  tactic?: string | null;
  score?: number | null;
  source?: string;
  relevance?: string;
  description?: string;
  mitre_url?: string | null;
  [key: string]: unknown;
}

export interface QueryResponse {
  status: "completed" | "followup";
  answer: string;
  followup_question?: string;
  session_id?: string;
  retrieval_context_id?: string | null;
  mitre_table?: MitreContextEntry[];
}

export type ThreadStatus =
  | "idle"
  | "processing"
  | "awaiting_followup"
  | "failed";

export type RunStatus = "queued" | "running" | "completed" | "failed";

export interface ChatThreadRead {
  id: string;
  title: string;
  status: ThreadStatus;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
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
  messages: ChatMessage[];
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
  message: ChatMessage;
  run: ChatRun;
}

export type SourceType =
  | "case_description"
  | "evidence_text"
  | "follow_up_answer"
  | "retrieved_context";

export interface AnalysisSource {
  source_id: string;
  source_type: SourceType;
  normalized_text: string;
  text_sha256: string;
  identity_status:
    | "caller_supplied_unverified"
    | "frozen_retrieval_snapshot";
}

export interface ValidatedClaim {
  claim_id: string;
  claim_text: string;
  claim_scope: "case_fact" | "retrieved_knowledge";
  source_id: string;
  source_type: SourceType | null;
  source_sha256: string | null;
  exact_quote: string;
  span_start: number | null;
  span_end: number | null;
  evidence_window: string;
  entailment_label:
    | "entailed"
    | "contradicted"
    | "not_enough_information"
    | null;
  evidential_status:
    | "reported"
    | "corroborated"
    | "contradicted"
    | "retrieved_knowledge"
    | "unsupported"
    | "needs_review";
  validation_status: "accepted" | "rejected" | "needs_review";
  validation_reasons: string[];
}

export interface AnalysisError {
  code: string;
  message: string;
}

export interface ValidationSummary {
  total_material_claims: number;
  claims_with_citations: number;
  valid_exact_spans: number;
  deterministic_mismatches: number;
  entailed_claims: number;
  contradicted_claims: number;
  not_enough_information_claims: number;
  unsupported_claims: number;
  needs_review_claims: number;
  citation_coverage: number;
}

export interface CaseAnalysisArtifact {
  case_id: string;
  retrieval_context_id: string;
  context_binding_status: "exact_case_text_match" | "unverified";
  analysis_status: "completed" | "needs_review";
  case_summary: string;
  claims: ValidatedClaim[];
  candidate_indicators: string[];
  timeline_events: string[];
  mitre_context: MitreContextEntry[];
  missing_information: string[];
  suggested_follow_up_questions: string[];
  limitations: string[];
  analysis_errors: AnalysisError[];
  sources: AnalysisSource[];
  validation_summary: ValidationSummary;
}

export interface CyberCaseReport {
  case_summary: string;
  detected_indicators: string[];
  mitre_mapping: string[];
  mapping_justification: string;
  evidence_to_investigate: string[];
  preliminary_recommendations: string[];
  system_limitations: string;
}

export interface ExperimentalAnalysisResponse {
  analysis: CaseAnalysisArtifact;
  report: CyberCaseReport | null;
  reportability_reasons: string[];
}

export interface CaseAnalysisRequest {
  retrieval_context_id: string;
  case_description: string;
  case_description_source_id?: string;
  evidence_sources?: Array<{ source_id: string; text: string }>;
  follow_up_answers?: Array<{
    source_id: string;
    question: string;
    answer: string;
  }>;
}

export const queryRag = async (
  query: string,
  useAgent: boolean = true,
): Promise<QueryResponse> => {
  const baseUrl = getApiBaseUrl();
  const response = await axios.post<QueryResponse>(
    `${baseUrl}/rag/query`,
    {
      query,
      use_agent: useAgent,
    },
  );

  return response.data;
};

export const resumeRag = async (
  sessionId: string,
  answer: string,
): Promise<QueryResponse> => {
  const baseUrl = getApiBaseUrl();
  const response = await axios.post<QueryResponse>(
    `${baseUrl}/rag/resume`,
    {
      session_id: sessionId,
      answer,
    },
  );

  return response.data;
};

export const queryRagFile = async (
  file: File,
  query: string,
): Promise<QueryResponse> => {
  const baseUrl = getApiBaseUrl();
  const formData = new FormData();
  formData.append("file", file);
  formData.append("query", query);

  const response = await axios.post<QueryResponse>(
    `${baseUrl}/rag/query-file`,
    formData,
  );

  return response.data;
};

export const analyzeCase = async (
  caseId: string,
  request: CaseAnalysisRequest,
): Promise<ExperimentalAnalysisResponse> => {
  const baseUrl = getApiBaseUrl();
  const response = await axios.post<ExperimentalAnalysisResponse>(
    `${baseUrl}/rag/cases/${encodeURIComponent(caseId)}/experimental-analysis`,
    request,
  );

  return response.data;
};

export const listChatThreads = async (
  signal?: AbortSignal,
): Promise<ChatThreadRead[]> => {
  const baseUrl = getApiBaseUrl();
  const response = await axios.get<ChatThreadRead[]>(`${baseUrl}/chats`, {
    signal,
  });
  return response.data;
};

export const createChatThread = async (
  title: string = "New chat",
  signal?: AbortSignal,
): Promise<ChatThreadRead> => {
  const baseUrl = getApiBaseUrl();
  const response = await axios.post<ChatThreadRead>(
    `${baseUrl}/chats`,
    { title },
    { signal },
  );
  return response.data;
};

export const getChatThread = async (
  threadId: string,
  signal?: AbortSignal,
): Promise<ChatThreadDetail> => {
  const baseUrl = getApiBaseUrl();
  const response = await axios.get<ChatThreadDetail>(
    `${baseUrl}/chats/${encodeURIComponent(threadId)}`,
    { signal, timeout: CHAT_POLL_REQUEST_TIMEOUT_MS },
  );
  return response.data;
};

export const updateChatThread = async (
  threadId: string,
  title: string,
  signal?: AbortSignal,
): Promise<ChatThreadRead> => {
  const baseUrl = getApiBaseUrl();
  const response = await axios.patch<ChatThreadRead>(
    `${baseUrl}/chats/${encodeURIComponent(threadId)}`,
    { title },
    { signal },
  );
  return response.data;
};

export const deleteChatThread = async (
  threadId: string,
  signal?: AbortSignal,
): Promise<void> => {
  const baseUrl = getApiBaseUrl();
  await axios.delete(`${baseUrl}/chats/${encodeURIComponent(threadId)}`, {
    signal,
  });
};

export const createChatMessage = async (
  threadId: string,
  content: string,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<ChatMessageAccepted> => {
  const baseUrl = getApiBaseUrl();
  const response = await axios.post<ChatMessageAccepted>(
    `${baseUrl}/chats/${encodeURIComponent(threadId)}/messages`,
    { content, idempotency_key: idempotencyKey },
    { signal },
  );
  return response.data;
};

export const getChatRun = async (
  threadId: string,
  runId: string,
  signal?: AbortSignal,
): Promise<ChatRun> => {
  const baseUrl = getApiBaseUrl();
  const response = await axios.get<ChatRun>(
    `${baseUrl}/chats/${encodeURIComponent(threadId)}/runs/${encodeURIComponent(runId)}`,
    { signal, timeout: CHAT_POLL_REQUEST_TIMEOUT_MS },
  );
  return response.data;
};

export function getApiErrorMessage(
  error: unknown,
  fallback: string,
): string {
  if (!axios.isAxiosError(error)) {
    return error instanceof Error ? error.message : fallback;
  }

  if (error.code === "ECONNABORTED") {
    return "The request timed out.";
  }
  if (!error.response) {
    return "The backend is unavailable.";
  }
  const statusMessages: Partial<Record<number, string>> = {
    400: "The backend rejected the request.",
    401: "Authentication is required for this request.",
    403: "This request is not authorized.",
    404: "The requested backend capability is unavailable.",
    409: "The current investigation state cannot be processed.",
    413: "The submitted file or request is too large.",
    422: "The submitted investigation data is invalid.",
    429: "Too many requests were sent. Try again shortly.",
    502: "The analysis service returned an invalid response.",
    503: "The analysis service is temporarily unavailable.",
    504: "The analysis service timed out.",
  };
  const statusMessage = statusMessages[error.response.status];
  if (statusMessage) return statusMessage;
  return fallback;
}
