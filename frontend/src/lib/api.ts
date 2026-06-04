/**
 * API Client for CyberCase Framework Backend
 */
import axios from "axios";

/**
 * Returns the API base URL.
 * Fails at runtime if the environment variable is not set.
 */
function getApiBaseUrl(): string {
  let url = process.env.NEXT_PUBLIC_API_URL;

  // During build time (server-side in CI), we allow it to be empty
  // to prevent build crashes. It will fail at runtime in the browser.
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

interface QueryResponse {
  answer: string;
}

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

/**
 * Sends a query to the RAG engine and returns the answer.
 * Currently uses queryRag as a backend.
 */
export const chatContinue = async (
  query: string,
  _history: ChatMessage[] = [],
): Promise<string> => {
  void _history;
  return queryRag(query);
};

/**
 * Direct call to the RAG query endpoint.
 */
export const queryRag = async (query: string): Promise<string> => {
  const baseUrl = getApiBaseUrl();
  try {
    const response = await axios.post<QueryResponse>(
      `${baseUrl}/rag/query`,
      {
        query: query,
      },
      {
        headers: {
          "Content-Type": "application/json",
        },
      },
    );

    return response.data.answer;
  } catch (error) {
    console.error("RAG query failed:", error);
    throw error;
  }
};

/**
 * Sends a document/image through the OCR-backed RAG endpoint.
 */
export const queryRagFile = async (
  file: File,
  query: string,
  pageNum: number,
): Promise<string> => {
  const baseUrl = getApiBaseUrl();
  const formData = new FormData();
  formData.append("file", file);
  formData.append("query", query);
  formData.append("page_num", String(pageNum));

  try {
    const response = await axios.post<QueryResponse>(
      `${baseUrl}/rag/query-file`,
      formData,
    );

    return response.data.answer;
  } catch (error) {
    console.error("RAG file query failed:", error);
    throw error;
  }
};
