/**
 * API Client for CyberCase Framework Backend
 */
import axios from "axios";

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

  // Ensure protocol is present
  if (!url.startsWith("http")) {
    url = `https://${url}`;
  }

  // Ensure /api/v1 path is present
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
      headers: {
        "Content-Type": "application/json",
      },
      // Short timeout for health check
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

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

/**
 * Sends a query to the RAG engine.
 */
export const queryRag = async (
  query: string,
  useAgent: boolean = true,
): Promise<QueryResponse> => {
  const baseUrl = getApiBaseUrl();
  try {
    const response = await axios.post<QueryResponse>(
      `${baseUrl}/rag/query`,
      {
        query: query,
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

/**
 * Generates a preliminary cyber case analysis/report draft.
 */
export const generateReport = async (
  query: string,
): Promise<CyberCaseReport> => {
  const baseUrl = getApiBaseUrl();
  try {
    const response = await axios.post<CyberCaseReport>(
      `${baseUrl}/rag/generate-report`,
      {
        query: query,
        use_agent: false,
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

/**
 * Resumes a follow-up session.
 */
export const resumeRag = async (
  sessionId: string,
  answer: string,
): Promise<QueryResponse> => {
  const baseUrl = getApiBaseUrl();
  try {
    const response = await axios.post<QueryResponse>(
      `${baseUrl}/rag/resume`,
      {
        session_id: sessionId,
        answer: answer,
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

/**
 * Sends a query to the RAG engine and returns the answer.
 */
export const chatContinue = async (
  query: string,
  _history: ChatMessage[] = [],
): Promise<QueryResponse> => {
  void _history;
  return queryRag(query);
};

/**
 * Sends a document/image through the OCR-backed RAG endpoint.
 */
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
      `${baseUrl}/rag/query-file`,
      formData,
    );

    return response.data;
  } catch (error) {
    console.error("RAG file query failed:", error);
    throw error;
  }
};
