import axios from "axios";

import { getApiBaseUrl } from "./api";

export type CaseChatAction = "analyze" | "refresh_analysis" | "question" | "followup";
export type CaseChatTurnType = "analysis" | "question" | "followup";
export type CaseChatTurnStatus = "pending" | "completed" | "failed" | "expired" | "stale";
export type CaseChatWorkspaceStatus = "idle" | "pending" | "completed" | "failed" | "expired" | "stale";
export type CaseAnalysisStatus = "missing" | "pending" | "completed" | "stale" | "expired" | "failed";
export type ReportReadinessReason =
  | "analysis_required"
  | "analysis_pending"
  | "analysis_stale"
  | "context_expired"
  | "analysis_failed"
  | "ready";

export interface CaseReportReadiness {
  case_id: string;
  current_case_version: number;
  current_case_snapshot_hash: string;
  analysis_status: CaseAnalysisStatus;
  report_eligible: boolean;
  reason: ReportReadinessReason;
  latest_analysis_turn_id?: string | null;
  latest_retrieval_context_id?: string | null;
}

export const caseAnalysisKeys = {
  workspace: (caseId: string) => ["cases", caseId, "chat"] as const,
  readiness: (caseId: string) => ["cases", caseId, "report-readiness"] as const,
};

export interface CaseChatTurn {
  turn_id: string;
  role: "user" | "assistant";
  content: string;
  turn_type: CaseChatTurnType;
  turn_status: CaseChatTurnStatus;
  case_version: number;
  case_snapshot_hash: string;
  created_at?: string | null;
}

export interface CaseChatWorkspace {
  case_id: string;
  context: {
    title: string;
    incident_summary: string;
    case_version: number;
    case_snapshot_hash: string;
    evidence_count: number;
    gap_count: number;
    attack_mapping_count: number;
    gaps: string[];
    attack_candidates: Array<{
      mapping_id: string;
      technique_id: string;
      technique_name: string;
      tactic?: string | null;
      status: string;
    }>;
    updated_at?: string | null;
  };
  turns: CaseChatTurn[];
  status: CaseChatWorkspaceStatus;
  requires_followup: boolean;
  active_session_id?: string | null;
  latest_retrieval_context_id?: string | null;
  analysis_case_version?: number | null;
  analysis_snapshot_hash?: string | null;
  report_eligible: boolean;
}

export interface CaseChatMessageResponse {
  status: CaseChatWorkspaceStatus;
  turn_status: CaseChatTurnStatus;
  turn_type: CaseChatTurnType;
  message: string;
  assistant_message?: string | null;
  followup_question?: string | null;
  session_id?: string | null;
  retrieval_context_id?: string | null;
  case_version: number;
  case_snapshot_hash: string;
  report_eligible: boolean;
  requires_followup: boolean;
  idempotent: boolean;
}

export async function getCaseChat(
  caseId: string,
  signal?: AbortSignal,
): Promise<CaseChatWorkspace> {
  const response = await axios.get<CaseChatWorkspace>(
    `${getApiBaseUrl()}/cases/${encodeURIComponent(caseId)}/chat`,
    { signal },
  );
  return response.data;
}

export async function getCaseReportReadiness(
  caseId: string,
  signal?: AbortSignal,
): Promise<CaseReportReadiness> {
  const response = await axios.get<CaseReportReadiness>(
    `${getApiBaseUrl()}/cases/${encodeURIComponent(caseId)}/report/readiness`,
    { signal },
  );
  return response.data;
}

export async function postCaseChatMessage(
  caseId: string,
  input: { action: CaseChatAction; message?: string },
  idempotencyKey: string,
): Promise<CaseChatMessageResponse> {
  const response = await axios.post<CaseChatMessageResponse>(
    `${getApiBaseUrl()}/cases/${encodeURIComponent(caseId)}/chat/messages`,
    {
      action: input.action,
      message: input.message?.trim() ?? "",
    },
    {
      headers: {
        "Idempotency-Key": idempotencyKey,
      },
    },
  );
  return response.data;
}
