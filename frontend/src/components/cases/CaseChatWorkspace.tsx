"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import CaseRouteState from "@/components/cases/CaseRouteState";
import CaseStageShell from "@/components/cases/CaseStageShell";
import { isNotFound, useCase } from "@/hooks/useCase";
import {
  CaseChatAction,
  getCaseChat,
  postCaseChatMessage,
} from "@/lib/case-chat";
import { generateCaseReport } from "@/lib/api";

const chatKey = (caseId: string) => ["cases", caseId, "chat"] as const;

function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `case-chat-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export default function CaseChatWorkspace({ caseId }: { caseId: string | null }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const caseQuery = useCase(caseId);
  const [message, setMessage] = useState("");
  const [requestError, setRequestError] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isGeneratingReport, setIsGeneratingReport] = useState(false);

  const chatQuery = useQuery({
    queryKey: caseId ? chatKey(caseId) : ["cases", "missing", "chat"],
    queryFn: ({ signal }) => {
      if (!caseId) throw new Error("caseId is required");
      return getCaseChat(caseId, signal);
    },
    enabled: Boolean(caseId),
    retry: 1,
  });

  if (!caseId) {
    return <CaseRouteState title="Case Chat" message="No case ID was provided." />;
  }
  if (caseQuery.isLoading || chatQuery.isLoading) {
    return <CaseRouteState title="Case Chat" message={`Loading case ${caseId}.`} />;
  }
  if (isNotFound(caseQuery.error) || isNotFound(chatQuery.error)) {
    return <CaseRouteState title="Case Chat" message={`Case ${caseId} was not found.`} />;
  }
  if (caseQuery.error || chatQuery.error || !caseQuery.data || !chatQuery.data) {
    return <CaseRouteState title="Case Chat" message="Could not load this case chat." />;
  }

  const workspace = chatQuery.data;
  const activeCaseId = caseId;
  const hasSavedIntake = Boolean(workspace.context.incident_summary.trim());
  const isPending = isSending || workspace.status === "pending";

  async function send(action: CaseChatAction, visibleMessage = "") {
    if (isPending) return;
    setIsSending(true);
    setRequestError("");
    try {
      await postCaseChatMessage(
        activeCaseId,
        { action, message: visibleMessage },
        newIdempotencyKey(),
      );
      setMessage("");
      await queryClient.invalidateQueries({ queryKey: chatKey(activeCaseId) });
    } catch {
      setRequestError("Could not submit the case-chat action. Refresh analysis and try again.");
    } finally {
      setIsSending(false);
    }
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = message.trim();
    if (!value) return;
    await send(workspace.requires_followup ? "followup" : "question", value);
  }

  async function generateReport() {
    const contextId = workspace.latest_retrieval_context_id;
    if (!workspace.report_eligible || !contextId) return;
    setIsGeneratingReport(true);
    setRequestError("");
    try {
      await generateCaseReport(activeCaseId, "overview", false, false, contextId);
      router.push(`/cases/${activeCaseId}/report`);
    } catch {
      setRequestError("The report could not start. Refresh analysis if the retrieval context has expired.");
      await queryClient.invalidateQueries({ queryKey: chatKey(activeCaseId) });
    } finally {
      setIsGeneratingReport(false);
    }
  }

  return (
    <CaseStageShell activeStage="chat" caseData={caseQuery.data}>
      <div className="mx-auto max-w-7xl space-y-5 p-5">
        {requestError ? (
          <div role="alert" className="border border-red-500/20 bg-red-50 p-4 text-sm font-semibold text-red-700">
            {requestError}
          </div>
        ) : null}

        {workspace.status === "stale" ? (
          <div className="border border-amber-500/30 bg-amber-50 p-4 text-sm font-semibold text-amber-900">
            This analysis completed against an older case version. Refresh analysis before generating a report.
          </div>
        ) : null}
        {workspace.status === "expired" ? (
          <div className="border border-amber-500/30 bg-amber-50 p-4 text-sm font-semibold text-amber-900">
            The RAG session or retrieval context expired. Refresh analysis explicitly to continue.
          </div>
        ) : null}

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
          <main className="min-w-0 border border-black/10 bg-white">
            <div className="border-b border-black/10 p-5">
              <p className="mono-label">Case investigation chat</p>
              <h1 className="mt-2 text-2xl font-black">{workspace.context.title}</h1>
              <p className="mt-2 text-sm font-semibold text-neutral">
                Start analysis deliberately or ask a focused investigation question. Opening this page never runs retrieval.
              </p>
            </div>

            <div className="min-h-80 space-y-4 p-5" aria-live="polite">
              {workspace.turns.length ? workspace.turns.map((turn) => (
                <article
                  key={turn.turn_id}
                  className={turn.role === "user"
                    ? "ml-auto max-w-2xl border border-black bg-black p-4 text-white"
                    : "mr-auto max-w-2xl border border-black/10 bg-neutral-50 p-4"}
                >
                  <div className="flex flex-wrap items-center gap-2 text-[10px] font-black uppercase tracking-widest opacity-70">
                    <span>{turn.role === "user" ? "Analyst" : "Investigation agent"}</span>
                    <span>•</span>
                    <span>{turn.turn_type}</span>
                    {turn.case_version !== workspace.context.case_version ? (
                      <span>• Based on case v{turn.case_version}</span>
                    ) : null}
                    {turn.turn_status !== "completed" ? <span>• {turn.turn_status}</span> : null}
                  </div>
                  <p className="mt-2 whitespace-pre-wrap text-sm font-semibold leading-6">{turn.content}</p>
                </article>
              )) : (
                <div className="border border-dashed border-black/15 bg-neutral-50 p-5 text-sm font-semibold text-neutral">
                  {hasSavedIntake
                    ? "No investigation messages yet. Analyze the saved case or ask a question."
                    : "Save Intake first. The saved case context is required before analysis."}
                </div>
              )}
            </div>

            <div className="border-t border-black/10 p-5">
              <div className="flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={() => void send("analyze")}
                  disabled={!hasSavedIntake || isPending}
                  className="btn-primary"
                >
                  {workspace.status === "stale" || workspace.status === "expired" ? "Refresh analysis" : "Analyze saved case"}
                </button>
                <button
                  type="button"
                  onClick={() => void generateReport()}
                  disabled={!workspace.report_eligible || isGeneratingReport || isPending}
                  className="border border-black px-4 py-2 text-xs font-black uppercase tracking-wider disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {isGeneratingReport ? "Starting report…" : "Generate preliminary report"}
                </button>
              </div>

              <form onSubmit={onSubmit} className="mt-4 flex gap-3">
                <label className="sr-only" htmlFor="case-chat-message">
                  {workspace.requires_followup ? "Follow-up answer" : "Investigation question"}
                </label>
                <textarea
                  id="case-chat-message"
                  value={message}
                  onChange={(event) => setMessage(event.target.value)}
                  disabled={isPending || !hasSavedIntake}
                  placeholder={workspace.requires_followup ? "Provide the requested follow-up information" : "Ask an investigation question"}
                  className="min-h-24 flex-1 resize-y border border-black/15 p-3 text-sm font-semibold outline-none focus:border-black disabled:bg-neutral-100"
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
                      event.preventDefault();
                      event.currentTarget.form?.requestSubmit();
                    }
                  }}
                />
                <button
                  type="submit"
                  disabled={!message.trim() || isPending || !hasSavedIntake}
                  className="self-end border border-black bg-black px-4 py-3 text-xs font-black uppercase tracking-wider text-white disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Send
                </button>
              </form>
              <p className="mt-2 text-xs font-semibold text-neutral">Press Ctrl/Cmd + Enter to send. Only your visible message is sent from this browser.</p>
            </div>
          </main>

          <aside className="order-first xl:order-none">
            <details open className="border border-black/10 bg-white">
              <summary className="cursor-pointer list-none border-b border-black/10 p-5">
                <p className="mono-label">Pinned saved case context</p>
                <p className="mt-2 text-sm font-black">Case version {workspace.context.case_version}</p>
              </summary>
              <div className="space-y-4 p-5">
                <p className="whitespace-pre-wrap text-sm font-semibold leading-6 text-neutral-900">
                  {workspace.context.incident_summary || "No saved intake narrative."}
                </p>
                <dl className="grid grid-cols-3 gap-2 border-t border-black/10 pt-4 text-center">
                  <div><dt className="mono-label">Evidence</dt><dd className="mt-1 text-xl font-black">{workspace.context.evidence_count}</dd></div>
                  <div><dt className="mono-label">Gaps</dt><dd className="mt-1 text-xl font-black">{workspace.context.gap_count}</dd></div>
                  <div><dt className="mono-label">ATT&CK</dt><dd className="mt-1 text-xl font-black">{workspace.context.attack_mapping_count}</dd></div>
                </dl>
                <div className="space-y-2 border-t border-black/10 pt-4">
                  <p className="mono-label">Known gaps</p>
                  {workspace.context.gaps.length ? (
                    <ul className="space-y-1 text-xs font-semibold leading-5 text-neutral-900">
                      {workspace.context.gaps.slice(0, 4).map((gap) => <li key={gap}>• {gap}</li>)}
                    </ul>
                  ) : <p className="text-xs font-semibold text-neutral">No deterministic gaps recorded.</p>}
                </div>
                <div className="space-y-2 border-t border-black/10 pt-4">
                  <p className="mono-label">ATT&CK candidates</p>
                  {workspace.context.attack_candidates.length ? (
                    <ul className="space-y-1 text-xs font-semibold leading-5 text-neutral-900">
                      {workspace.context.attack_candidates.slice(0, 4).map((candidate) => (
                        <li key={candidate.mapping_id || `${candidate.technique_id}-${candidate.technique_name}`}>
                          {candidate.technique_id} {candidate.technique_name}
                        </li>
                      ))}
                    </ul>
                  ) : <p className="text-xs font-semibold text-neutral">No ATT&CK candidates recorded.</p>}
                </div>
                <p className="border-t border-black/10 pt-4 text-xs font-semibold text-neutral">
                  Last case update: {workspace.context.updated_at ? new Date(workspace.context.updated_at).toLocaleString() : "not recorded"}
                </p>
                {workspace.requires_followup ? (
                  <p className="border border-amber-500/30 bg-amber-50 p-3 text-xs font-bold text-amber-900">
                    The investigation agent needs your follow-up answer before a report can be generated.
                  </p>
                ) : null}
              </div>
            </details>
          </aside>
        </div>
      </div>
    </CaseStageShell>
  );
}
