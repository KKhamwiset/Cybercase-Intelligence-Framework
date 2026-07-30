import type {
  AnalysisSource,
  MitreContextEntry,
  ValidatedClaim,
} from "@/lib/api";

export type RunPhase =
  | "idle"
  | "querying"
  | "awaiting_followup"
  | "analyzing"
  | "ready"
  | "error";

export type AnalysisAvailability =
  | { status: "idle"; message: null }
  | { status: "loading"; message: null }
  | { status: "available"; message: null }
  | { status: "unavailable"; message: string }
  | { status: "error"; message: string };

export type InspectorSelection =
  | { kind: "claim"; item: ValidatedClaim }
  | { kind: "source"; item: AnalysisSource }
  | { kind: "mitre"; item: MitreContextEntry }
  | { kind: "timeline"; item: string; index: number }
  | null;
