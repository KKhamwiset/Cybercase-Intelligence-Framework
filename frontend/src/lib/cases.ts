import axios from "axios";

import { getApiBaseUrl } from "./api";
import type {
  ActionItemView,
  AttackMappingView,
  EvidenceItemView,
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

export interface CaseListItem {
  case_id: string;
  title: string;
  status: CaseStatus;
  severity: CaseSeverity;
  updated_at?: string | null;
}

export interface StructuredCase {
  case_id: string;
  title: string;
  case_type: string;
  status: CaseStatus;
  severity: CaseSeverity;
  incident_summary: string;
  affected_users: string[];
  affected_assets: string[];
  timeline_events: TimelineEventView[];
  evidence_items: EvidenceItemView[];
  attack_mappings: AttackMappingView[];
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
  attack_mappings?: AttackMappingView[];
  containment_actions?: ActionItemView[];
  recommendations?: ActionItemView[];
  gaps?: string[];
  limitations?: string[];
  analyst_notes?: string;
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
