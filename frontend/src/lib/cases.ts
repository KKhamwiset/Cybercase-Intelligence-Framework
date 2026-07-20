import axios from "axios";

import { getApiBaseUrl } from "./api";
import type {
  ActionItemView,
  EvidenceItemView,
  FindingMetadataView,
  FindingStatus,
  ReportConfidence,
  ReportSourceType,
  TimelineEventView,
} from "./reports";

export type CaseStatus =
  | "new"
  | "triage"
  | "investigating"
  | "contained"
  | "resolved"
  | "unknown";
export type CaseSeverity = "critical" | "high" | "medium" | "low" | "unknown";
export type CaseAnalysisOutputStatus =
  | "not_started"
  | "pending"
  | "completed"
  | "stale"
  | "failed"
  | "expired";
export type CaseOutputSourceType =
  | "analyst_input"
  | "user_input"
  | "log"
  | "document"
  | "system_rule"
  | "rag"
  | "manual_edit"
  | "legacy_unverified";
export type CaseOutputReviewStatus = "unreviewed" | "accepted" | "rejected" | "edited";

export interface CaseListItem {
  case_id: string;
  case_version: number;
  title: string;
  status: CaseStatus;
  severity: CaseSeverity;
  updated_at?: string | null;
}

export interface CaseAttackMapping {
  mapping_id: string;
  technique_id: string;
  technique_name: string;
  tactic?: string | null;
  rationale: string;
  metadata: FindingMetadataView;
}

export interface StructuredCase {
  case_id: string;
  case_version: number;
  title: string;
  case_type: string;
  status: CaseStatus;
  severity: CaseSeverity;
  incident_summary: string;
  affected_users: string[];
  affected_assets: string[];
  timeline_events: TimelineEventView[];
  evidence_items: EvidenceItemView[];
  attack_mappings: CaseAttackMapping[];
  containment_actions: ActionItemView[];
  recommendations: ActionItemView[];
  gaps: string[];
  limitations: string[];
  analyst_notes: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface CaseCreateInput {
  title?: string;
  case_type?: string;
  status?: CaseStatus;
  severity?: CaseSeverity;
  incident_summary?: string;
}

export interface CaseUpdateInput {
  title?: string;
  case_type?: string;
  status?: CaseStatus;
  severity?: CaseSeverity;
  incident_summary?: string;
  affected_users?: string[];
  affected_assets?: string[];
  timeline_events?: TimelineEventView[];
  evidence_items?: EvidenceItemView[];
  containment_actions?: ActionItemView[];
  limitations?: string[];
  analyst_notes?: string;
}

export interface CaseOutputItem {
  item_id: string;
  title: string;
  description: string;
  source_type: CaseOutputSourceType;
  analysis_run_id?: string | null;
  case_version: number;
  generated_at?: string | null;
  source_references: string[];
  review_status: CaseOutputReviewStatus;
  status: string;
  details: Record<string, unknown>;
}

export interface CaseOutputBucket {
  current_count: number;
  items: CaseOutputItem[];
  source_types: CaseOutputSourceType[];
}

export interface CaseHistoricalOutputBucket {
  historical_count: number;
  items: CaseOutputItem[];
}

export interface CaseOutputsResponse {
  case_id: string;
  case_version: number;
  analysis: {
    status: CaseAnalysisOutputStatus;
    analysis_run_id?: string | null;
    analyzed_case_version?: number | null;
    analyzed_snapshot_hash?: string | null;
  };
  outputs: {
    evidence: CaseOutputBucket;
    gaps: CaseOutputBucket;
    attack_mappings: CaseOutputBucket;
    recommendations: CaseOutputBucket;
  };
  historical_outputs: {
    evidence: CaseHistoricalOutputBucket;
    gaps: CaseHistoricalOutputBucket;
    attack_mappings: CaseHistoricalOutputBucket;
    recommendations: CaseHistoricalOutputBucket;
  };
}

export interface CaseMetadataInput {
  status: FindingStatus;
  confidence: ReportConfidence;
  evidence_ids: string[];
  source_type: ReportSourceType;
  analyst_verified: boolean;
}

export async function listCases(signal?: AbortSignal): Promise<CaseListItem[]> {
  const response = await axios.get<CaseListItem[]>(`${getApiBaseUrl()}/cases`, {
    signal,
  });
  return response.data;
}

export async function createCase(input: CaseCreateInput): Promise<StructuredCase> {
  const response = await axios.post<StructuredCase>(`${getApiBaseUrl()}/cases`, input);
  return response.data;
}

export async function getCase(
  caseId: string,
  signal?: AbortSignal,
): Promise<StructuredCase> {
  const response = await axios.get<StructuredCase>(
    `${getApiBaseUrl()}/cases/${encodeURIComponent(caseId)}`,
    { signal },
  );
  return response.data;
}

export async function getCaseOutputs(
  caseId: string,
  signal?: AbortSignal,
): Promise<CaseOutputsResponse> {
  const response = await axios.get<CaseOutputsResponse>(
    `${getApiBaseUrl()}/cases/${encodeURIComponent(caseId)}/outputs`,
    { signal },
  );
  return response.data;
}

export async function updateCase(
  caseId: string,
  input: CaseUpdateInput,
): Promise<StructuredCase> {
  const response = await axios.patch<StructuredCase>(
    `${getApiBaseUrl()}/cases/${encodeURIComponent(caseId)}`,
    input,
  );
  return response.data;
}

export async function deleteCase(caseId: string): Promise<void> {
  await axios.delete(`${getApiBaseUrl()}/cases/${encodeURIComponent(caseId)}`);
}
