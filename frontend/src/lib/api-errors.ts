import axios from "axios";

type ValidationDetail = {
  loc?: Array<string | number>;
  msg?: string;
};

export function apiErrorMessage(error: unknown, fallback: string): string {
  if (!axios.isAxiosError(error)) {
    return error instanceof Error && error.message ? error.message : fallback;
  }

  const detail = error.response?.data?.detail as string | ValidationDetail[] | undefined;
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        const field = item.loc?.filter((part) => part !== "body").join(".");
        if (!item.msg) return "";
        return field ? `${field}: ${item.msg}` : item.msg;
      })
      .filter(Boolean);
    if (messages.length) {
      return messages.join(" ");
    }
  }
  return fallback;
}
