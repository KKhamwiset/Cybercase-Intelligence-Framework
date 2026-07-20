export type FindingStatus = "confirmed" | "candidate" | "unknown";
export type ReportStatus = "draft" | "incomplete" | "ready_for_review";
export type ReportSectionStatus = "complete" | "partial" | "missing";
export type ReportConfidence = "high" | "medium" | "low";
export type ReportSourceType =
  | "user_input"
  | "analyst_input"
  | "log"
  | "document"
  | "rag"
  | "system_rule";

export interface ReportGap {
  gap_id: string;
  section_id: string;
  title: string;
  description: string;
  priority: "high" | "medium" | "low";
  evidence_ids: string[];
}

export interface ReportSection {
  id: string;
  title: string;
  required: boolean;
  status: ReportSectionStatus;
  content: Record<string, unknown>;
  source_fact_ids: string[];
}

export interface ReportMetadata {
  confirmed_findings: number;
  candidate_findings: number;
  unknown_findings: number;
  evidence_count: number;
  gap_count: number;
}

export interface ReportViewModel {
  case_id: string;
  report_type: "incident_analysis";
  generated_at: string;
  report_status: ReportStatus;
  sections: ReportSection[];
  gaps: ReportGap[];
  limitations: string[];
  metadata: ReportMetadata;
}

export interface TimelineEventView {
  event_id: string;
  timestamp?: string | null;
  title: string;
  description?: string;
  metadata: FindingMetadataView;
}

export interface FindingMetadataView {
  status: FindingStatus;
  confidence: ReportConfidence;
  evidence_ids: string[];
  source_type: ReportSourceType;
  analyst_verified: boolean;
}

export interface EvidenceItemView {
  evidence_id: string;
  title: string;
  description?: string;
  source_type: ReportSourceType;
  status: FindingStatus;
  confidence: ReportConfidence;
  collected_at?: string | null;
  analyst_verified: boolean;
}

export interface AttackMappingView {
  mapping_id: string;
  technique_id: string;
  technique_name: string;
  rationale: string;
  status: FindingStatus;
  confidence: ReportConfidence;
  evidence_ids: string[];
  analyst_verified: boolean;
  source_type: ReportSourceType;
}

export interface AttackTacticGroupView {
  tactic: string;
  mappings: AttackMappingView[];
}

export interface ActionItemView {
  action_id: string;
  title: string;
  description?: string;
  status: FindingStatus;
  metadata: FindingMetadataView;
}
