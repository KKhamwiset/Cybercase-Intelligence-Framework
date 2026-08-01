export type RunPhase =
  | "idle"
  | "querying"
  | "awaiting_followup"
  | "analyzing"
  | "ready"
  | "error";
