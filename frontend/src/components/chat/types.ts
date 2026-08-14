export type RunPhase =
  | "idle"
  | "querying"
  | "awaiting_followup"
  | "analyzing"
  | "ready"
  | "error";

export type WorkspaceView = "chat" | "extraction" | "report";

export type EvidenceRouteView = "extraction" | "timeline" | "relationships";

export type CaseInformationRouteView = EvidenceRouteView;

export type WorkspaceRouteView = WorkspaceView | EvidenceRouteView;

export function workspaceViewForRoute(
  view: WorkspaceRouteView,
): WorkspaceView {
  return view === "timeline" || view === "relationships" ? "extraction" : view;
}

export const workspaceViewLabels: Record<WorkspaceView, string> = {
  chat: "Chat",
  extraction: "Case details & timeline",
  report: "Report generation",
};
