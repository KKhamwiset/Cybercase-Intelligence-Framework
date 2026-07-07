/**
 * API Client for CyberCase Framework Backend
 */
import axios from "axios";

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

export interface QueryResponse {
  status: "completed" | "followup";
  answer: string;
  followup_question?: string;
  session_id?: string;
  retrieval_context_id?: string;
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

export interface ReportCompletedResponse {
  status: "completed";
  report_id: string;
  report: CyberCaseReport;
  answer: string;
}

export interface ReportFollowUpResponse {
  status: "followup";
  session_id: string;
  followup_question: string;
  retrieval_context_id?: string;
  completeness: CaseInformationCompleteness;
  missing_information: string[];
}

export type ReportWorkflowResponse =
  | ReportCompletedResponse
  | ReportFollowUpResponse;

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

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

export const generateReport = async (
  query: string,
  reportType: ReportType = "overview",
  legal: boolean = false,
  forceGenerate: boolean = false,
  retrievalContextId: string = "",
): Promise<ReportWorkflowResponse> => {
  const baseUrl = getApiBaseUrl();
  try {
    const response = await axios.post<ReportWorkflowResponse>(
      baseUrl + "/reports/generate",
      {
        query,
        report_type: reportType,
        legal,
        force_generate: forceGenerate,
        retrieval_context_id: retrievalContextId,
      },
      {
        headers: {
          "Content-Type": "application/json",
        },
      },
    );

    return response.data;
  } catch (error) {
    console.error("Report generation failed:", error);
    throw error;
  }
};

export const generateReportFile = async (
  file: File,
  query: string,
  reportType: ReportType = "overview",
  legal: boolean = false,
  forceGenerate: boolean = false,
): Promise<ReportWorkflowResponse> => {
  const baseUrl = getApiBaseUrl();
  const formData = new FormData();
  formData.append("file", file);
  formData.append("query", query);
  formData.append("report_type", reportType);
  formData.append("legal", String(legal));
  formData.append("force_generate", String(forceGenerate));

  try {
    const response = await axios.post<ReportWorkflowResponse>(
      baseUrl + "/reports/generate-file",
      formData,
    );

    return response.data;
  } catch (error) {
    console.error("Report file generation failed:", error);
    throw error;
  }
};

export const resumeReport = async (
  sessionId: string,
  answer: string,
): Promise<ReportWorkflowResponse> => {
  const baseUrl = getApiBaseUrl();
  try {
    const response = await axios.post<ReportWorkflowResponse>(
      baseUrl + "/reports/resume",
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
    console.error("Report resume failed:", error);
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
}

export const listReports = async (): Promise<ReportRegistryItem[]> => {
  const baseUrl = getApiBaseUrl();
  const response = await axios.get<ReportRegistryItem[]>(
    baseUrl + "/reports",
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
