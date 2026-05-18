/**
 * API Client for TSR Mitre Backend
 */
import axios from "axios";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1";

interface HealthStatus {
  status: string;
  database: "loading" | "connected" | "error" | "disconnected";
  version: string;
}

export async function getHealthStatus(): Promise<HealthStatus> {
  try {
    const response = await axios.get<HealthStatus>(`${API_BASE_URL}/health`, {
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

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export async function queryRag(query: string): Promise<string> {
  try {
    const response = await axios.post<QueryResponse>(
      `${API_BASE_URL}/rag/query`,
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
}

export async function chatContinue(
  query: string,
  history: ChatMessage[],
): Promise<string> {
  try {
    const response = await axios.post<QueryResponse>(
      `${API_BASE_URL}/rag/chatcontinue`,
      {
        query: query,
        history: history,
      },
      {
        headers: {
          "Content-Type": "application/json",
        },
      },
    );

    return response.data.answer;
  } catch (error) {
    console.error("Chat continue failed:", error);
    throw error;
  }
}
