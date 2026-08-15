export type RunPhase =
  | "idle"
  | "querying"
  | "awaiting_followup"
  | "analyzing"
  | "ready"
  | "error";

export type WorkspaceView =
  | "chat"
  | "extraction"
  | "timeline"
  | "relationships"
  | "report";

export type EvidenceRouteView = "extraction" | "timeline" | "relationships";

export type CaseInformationRouteView = EvidenceRouteView;

export type WorkspaceRouteView = WorkspaceView;

export function workspaceViewForRoute(
  view: WorkspaceRouteView,
): WorkspaceView {
  return view;
}

export const workspaceViewLabels: Record<WorkspaceView, string> = {
  chat: "Chat",
  extraction: "Case details",
  timeline: "Timeline",
  relationships: "Relationships",
  report: "Report generation",
};

export const workspaceViewDescriptions: Record<WorkspaceView, string> = {
  chat: "Interactive incident reasoning",
  extraction: "Extracted facts & observables",
  timeline: "Chronological event sequence",
  relationships: "Entity relationship graph",
  report: "Digital-forensics executive report",
};
