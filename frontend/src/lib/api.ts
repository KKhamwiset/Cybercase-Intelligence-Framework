/**
 * API Client for CyberCase Framework Backend
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

interface HealthStatus {
  status: string;
  database: "loading" | "connected" | "error" | "disconnected";
  version: string;
}

export async function getHealthStatus(): Promise<HealthStatus> {
  const baseUrl = getApiBaseUrl();
  try {
    const response = await axios.get<HealthStatus>(baseUrl + "/health", {
      headers: {
        "Content-Type": "application/json",
      },
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
  role: "user" | "assistant";
  content: string;
}

export interface PersistedChatMessage extends ChatMessage {
  id: string;
  thread_id: string;
  ordinal: number;
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

export type AnalysisSourceType =
  | "case_description"
  | "evidence_text"
  | "follow_up_answer"
  | "retrieved_context";

export interface AnalysisSource {
  source_id: string;
  source_type: AnalysisSourceType;
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
  source_type: AnalysisSourceType | null;
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

export interface ExperimentalCyberCaseReport {
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
  report: ExperimentalCyberCaseReport | null;
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

export type EvidenceStatus = "confirmed" | "reported" | "inferred" | "unknown";
export type ReviewStatus = "draft" | "ai_generated" | "reviewed" | "approved";
export type ReportType = "overview" | "subject" | "timeline" | "vulnerability";
export type SourceType =
  | "user_input"
  | "uploaded_file"
  | "log"
  | "rag_source"
  | "mitre_source"
  | "legal_source";
export type Confidence = "low" | "medium" | "high";
export type IndicatorType = "ip" | "domain" | "url" | "email" | "hash" | "cve" | "file" | "other";

export interface EvidenceReference {
  evidence_id: string;
  source_type: SourceType;
  source_name: string;
  excerpt?: string | null;
  page_number?: number | null;
  line_reference?: string | null;
  file_hash_sha256?: string | null;
  content_type?: string | null;
  uploaded_at?: string | null;
  extraction_method?: string | null;
}

export interface CaseFact {
  fact_id: string;
  statement: string;
  category: string;
  status: EvidenceStatus;
  confidence: Confidence;
  evidence_ids: string[];
  notes?: string | null;
}

export interface TimelineEvent {
  event_id: string;
  timestamp?: string | null;
  event: string;
  status: EvidenceStatus;
  evidence_ids: string[];
}

export interface Indicator {
  indicator_id: string;
  indicator_type: IndicatorType;
  value: string;
  status: EvidenceStatus;
  evidence_ids: string[];
  notes?: string | null;
}

export interface MitreAssessment {
  technique_id: string;
  technique_name: string;
  mapping_status: EvidenceStatus;
  justification: string;
  evidence_ids: string[];
}

export interface LegalRelevanceAssessment {
  enabled: boolean;
  provision_reference: string;
  preliminary_relevance: string;
  status: EvidenceStatus;
  evidence_ids: string[];
  disclaimer: string;
}

export interface CompletenessField {
  field_id: string;
  label: string;
  present: boolean;
  evidence_ids: string[];
}

export interface CaseInformationCompleteness {
  percentage: number;
  status: "Sufficient for preliminary report" | "Incomplete - follow-up required";
  missing_fields: string[];
  fields: CompletenessField[];
}

export interface CaseFactPack {
  facts: CaseFact[];
  evidence_registry: EvidenceReference[];
  indicators: Indicator[];
  timeline: TimelineEvent[];
  mitre_assessments: MitreAssessment[];
  legal_assessments: LegalRelevanceAssessment[];
  missing_information: string[];
  limitations: string[];
  completeness_percentage: number;
  completeness: CaseInformationCompleteness;
  review_status: ReviewStatus;
}

export interface CyberCaseReport {
  report_id: string;
  title: string;
  report_type: ReportType;
  executive_case_summary: string;
  case_information_completeness: CaseInformationCompleteness;
  evidence_and_indicators_table: Indicator[];
  incident_timeline: TimelineEvent[];
  mitre_attack_assessment: MitreAssessment[];
  evidence_still_required: string[];
  investigation_next_steps: string[];
  legal_assessments: LegalRelevanceAssessment[];
  limitations_and_disclaimers: string[];
  review_status: ReviewStatus;
  case_fact_pack: CaseFactPack;
  created_at: string;
}

export interface ReportEditMetadata {
  origin: "generated" | "manual_edit";
  edited_fields: string[];
  edited_at?: string | null;
}

export interface ReportUpdateInput {
  title?: string;
  executive_case_summary?: string;
  evidence_still_required?: string[];
  investigation_next_steps?: string[];
  limitations_and_disclaimers?: string[];
}

export interface ReportCompletedResponse {
  status: "completed";
  report_id: string;
  report: CyberCaseReport;
  answer: string;
  retrieval_context_id?: string;
  edit_metadata: ReportEditMetadata;
}

export interface ReportFollowUpResponse {
  status: "followup";
  session_id: string;
  followup_question: string;
  retrieval_context_id?: string;
  completeness: CaseInformationCompleteness;
  missing_information: string[];
}

export interface ReportErrorResponse {
  status: "error" | "context_expired" | "analysis_required" | "analysis_stale";
  error_code: string;
  message: string;
}

export type ReportWorkflowResponse =
  | ReportCompletedResponse
  | ReportFollowUpResponse
  | ReportErrorResponse;

export const queryRag = async (
  query: string,
  useAgent: boolean = true,
): Promise<QueryResponse> => {
  const baseUrl = getApiBaseUrl();
  try {
    const response = await axios.post<QueryResponse>(
      baseUrl + "/rag/query",
      {
        query,
        use_agent: useAgent,
      },
      {
        headers: {
          "Content-Type": "application/json",
        },
      },
    );

    return response.data;
  } catch (error) {
    console.error("RAG query failed:", error);
    throw error;
  }
};

export const getReport = async (reportId: string): Promise<ReportWorkflowResponse> => {
  const baseUrl = getApiBaseUrl();
  const response = await axios.get<ReportWorkflowResponse>(
    baseUrl + "/reports/" + reportId,
  );
  return response.data;
};

export const updateReport = async (
  reportId: string,
  input: ReportUpdateInput,
): Promise<ReportWorkflowResponse> => {
  const response = await axios.patch<ReportWorkflowResponse>(
    `${getApiBaseUrl()}/reports/${encodeURIComponent(reportId)}`,
    input,
  );
  return response.data;
};

export const deleteReport = async (reportId: string): Promise<void> => {
  await axios.delete(`${getApiBaseUrl()}/reports/${encodeURIComponent(reportId)}`);
};

export const updateReportReviewStatus = async (
  reportId: string,
  reviewStatus: ReviewStatus,
): Promise<ReportWorkflowResponse> => {
  const baseUrl = getApiBaseUrl();
  const response = await axios.patch<ReportWorkflowResponse>(
    baseUrl + "/reports/" + reportId + "/review-status",
    {
      review_status: reviewStatus,
    },
  );
  return response.data;
};

export const resumeRag = async (
  sessionId: string,
  answer: string,
): Promise<QueryResponse> => {
  const baseUrl = getApiBaseUrl();
  try {
    const response = await axios.post<QueryResponse>(
      baseUrl + "/rag/resume",
      {
        session_id: sessionId,
        answer,
      },
      {
        headers: {
          "Content-Type": "application/json",
        },
      },
    );

    return response.data;
  } catch (error) {
    console.error("RAG resume failed:", error);
    throw error;
  }
};

export const chatContinue = async (
  query: string,
  _history: ChatMessage[] = [],
): Promise<QueryResponse> => {
  void _history;
  return queryRag(query);
};

export const queryRagFile = async (
  file: File,
  query: string,
): Promise<QueryResponse> => {
  const baseUrl = getApiBaseUrl();
  const formData = new FormData();
  formData.append("file", file);
  formData.append("query", query);

  try {
    const response = await axios.post<QueryResponse>(
      baseUrl + "/rag/query-file",
      formData,
    );

    return response.data;
  } catch (error) {
    console.error("RAG file query failed:", error);
    throw error;
  }
};

export interface ReportRegistryItem {
  report_id: string;
  case_id: string;
  case_title: string;
  case_status: string;
  severity: string;
  report_type: string;
  workflow_status: string;
  review_status: string;
  created_at: string;
  updated_at: string;
  executive_summary_preview: string;
  edit_metadata: ReportEditMetadata;
}

export const listReports = async (caseId?: string): Promise<ReportRegistryItem[]> => {
  const baseUrl = getApiBaseUrl();
  const response = await axios.get<ReportRegistryItem[]>(
    baseUrl + "/reports",
    { params: caseId ? { case_id: caseId } : undefined },
  );
  return response.data;
};

export const generateCaseReport = async (
  caseId: string,
  reportType: ReportType = "overview",
  legal: boolean = false,
  forceGenerate: boolean = false,
): Promise<ReportWorkflowResponse> => {
  const baseUrl = getApiBaseUrl();
  try {
    const response = await axios.post<ReportWorkflowResponse>(
      baseUrl + "/cases/" + caseId + "/report",
      {
        report_type: reportType,
        legal,
        force_generate: forceGenerate,
      },
      {
        headers: {
          "Content-Type": "application/json",
        },
      },
    );

    return response.data;
  } catch (error) {
    console.error("Case report generation failed:", error);
    throw error;
  }
};

export const resumeCaseReport = async (
  caseId: string,
  sessionId: string,
  answer: string,
): Promise<ReportWorkflowResponse> => {
  const baseUrl = getApiBaseUrl();
  try {
    const response = await axios.post<ReportWorkflowResponse>(
      baseUrl + "/cases/" + caseId + "/report/resume",
      {
        session_id: sessionId,
        answer,
      },
      {
        headers: {
          "Content-Type": "application/json",
        },
      },
    );

    return response.data;
  } catch (error) {
    console.error("Case report resume failed:", error);
    throw error;
  }
};

export const getLatestCaseReport = async (
  caseId: string,
): Promise<ReportWorkflowResponse> => {
  const baseUrl = getApiBaseUrl();
  const response = await axios.get<ReportWorkflowResponse>(
    baseUrl + "/cases/" + caseId + "/report",
  );
  return response.data;
};

export const downloadReportExport = async (
  reportId: string,
  format: "md" | "pdf" | "docx",
): Promise<Blob> => {
  const baseUrl = getApiBaseUrl();
  const response = await axios.get(
    `${baseUrl}/reports/${reportId}/export`,
    {
      params: { format },
      responseType: "blob",
    },
  );
  return response.data;
};

export interface CaseAnalysisResponse {
  case_id: string;
  session_id: string | null;
  workflow_status:
  | "case_saved"
  | "analyzing"
  | "needs_followup"
  | "ready_for_report"
  | "report_generated"
  | "context_expired"
  | "error";
  retrieval_context_id: string | null;
  completeness: CaseInformationCompleteness | null;
  missing_information: string[];
  followup_question: string | null;
  mitre_preview: MitreAssessment[];
  created_at: string | null;
  updated_at: string | null;
}

export const startCaseAnalysis = async (
  caseId: string,
  reportType: ReportType = "overview",
  legal: boolean = false,
): Promise<CaseAnalysisResponse> => {
  const baseUrl = getApiBaseUrl();
  try {
    const response = await axios.post<CaseAnalysisResponse>(
      baseUrl + "/cases/" + caseId + "/analysis/start",
      {
        report_type: reportType,
        legal,
      },
      {
        headers: {
          "Content-Type": "application/json",
        },
      },
    );
    return response.data;
  } catch (error) {
    console.error("Start case analysis failed:", error);
    throw error;
  }
};

export const getCaseAnalysis = async (
  caseId: string,
): Promise<CaseAnalysisResponse> => {
  const baseUrl = getApiBaseUrl();
  try {
    const response = await axios.get<CaseAnalysisResponse>(
      baseUrl + "/cases/" + caseId + "/analysis",
    );
    return response.data;
  } catch (error) {
    console.error("Get case analysis failed:", error);
    throw error;
  }
};

export const submitCaseAnalysisFollowUp = async (
  caseId: string,
  sessionId: string,
  answer: string,
): Promise<CaseAnalysisResponse> => {
  const baseUrl = getApiBaseUrl();
  try {
    const response = await axios.post<CaseAnalysisResponse>(
      baseUrl + "/cases/" + caseId + "/analysis/followup",
      {
        session_id: sessionId,
        answer,
      },
      {
        headers: {
          "Content-Type": "application/json",
        },
      },
    );
    return response.data;
  } catch (error) {
    console.error("Submit case analysis followup failed:", error);
    throw error;
  }
};

export const analyzeCase = async (
  caseId: string,
  request: CaseAnalysisRequest,
): Promise<ExperimentalAnalysisResponse> => {
  const response = await axios.post<ExperimentalAnalysisResponse>(
    `${getApiBaseUrl()}/rag/cases/${encodeURIComponent(caseId)}/experimental-analysis`,
    request,
  );
  return response.data;
};

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
): Promise<ChatMessageAccepted> => {
  const response = await axios.post<ChatMessageAccepted>(
    `${getApiBaseUrl()}/chats/${encodeURIComponent(threadId)}/messages`,
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
  const response = await axios.get<ChatRun>(
    `${getApiBaseUrl()}/chats/${encodeURIComponent(threadId)}/runs/${encodeURIComponent(runId)}`,
    { signal, timeout: CHAT_POLL_REQUEST_TIMEOUT_MS },
  );
  return response.data;
};

export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (!axios.isAxiosError(error)) {
    return error instanceof Error ? error.message : fallback;
  }
  if (error.code === "ECONNABORTED") return "The request timed out.";
  if (!error.response) return "The backend is unavailable.";

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
  return statusMessages[error.response.status] ?? fallback;
}
