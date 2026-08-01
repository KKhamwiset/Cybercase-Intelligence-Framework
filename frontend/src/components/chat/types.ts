export type RunPhase =
  | "idle"
  | "querying"
  | "awaiting_followup"
  | "analyzing"
  | "ready"
  | "error";

export type WorkspaceView = "chat" | "extraction" | "report";

export const workspaceViewLabels: Record<WorkspaceView, string> = {
  chat: "Chat",
  extraction: "Evidence & timeline",
  report: "Report generation",
};
