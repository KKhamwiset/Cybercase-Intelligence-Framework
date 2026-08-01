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
  | "failed";

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
    404: "The requested chat capability is unavailable.",
    409: "The current chat state cannot be processed.",
    413: "The submitted message is too large.",
    422: "The submitted chat message is invalid.",
    429: "Too many requests were sent. Try again shortly.",
    502: "The analysis service returned an invalid response.",
    503: "The analysis service is temporarily unavailable.",
    504: "The analysis service timed out.",
  };
  return statusMessages[error.response.status] ?? fallback;
}
