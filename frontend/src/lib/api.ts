/**
 * API Client for TSR Mitre Backend
 */
import axios from "axios";

/**
 * Returns the API base URL.
 * Fails at runtime if the environment variable is not set.
 */
function getApiBaseUrl(): string {
  const url = process.env.NEXT_PUBLIC_API_URL;
  if (!url) {
    throw new Error(
      "NEXT_PUBLIC_API_URL is not set. The application cannot start.",
    );
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
