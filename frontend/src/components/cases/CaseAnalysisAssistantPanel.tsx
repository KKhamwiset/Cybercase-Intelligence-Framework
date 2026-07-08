import React from "react";
import type { StructuredCase } from "@/lib/cases";
import type { ReportWorkflowResponse, ReportType } from "@/lib/api";

interface CaseAnalysisAssistantPanelProps {
  caseData: StructuredCase;
  workflow: ReportWorkflowResponse | null;
  reportType: ReportType;
  legal: boolean;
  followupAnswer: string;
  isGenerating: boolean;
  onReportTypeChange: (type: ReportType) => void;
  onLegalChange: (legal: boolean) => void;
  onFollowupAnswerChange: (answer: string) => void;
  onStartAnalysis: () => void;
  onSubmitFollowup: () => void;
  onForceGenerate: () => void;
}

export default function CaseAnalysisAssistantPanel({
  caseData,
  workflow,
  reportType,
  legal,
  followupAnswer,
  isGenerating,
  onReportTypeChange,
  onLegalChange,
  onFollowupAnswerChange,
  onStartAnalysis,
  onSubmitFollowup,
  onForceGenerate,
}: CaseAnalysisAssistantPanelProps) {
  const isFollowup = workflow?.status === "followup";

  return (
    <div className="border border-black/10 bg-white p-6 md:p-8 flex flex-col h-full justify-between min-h-[480px]">
      <div>
        <div className="flex items-center justify-between border-b border-black pb-4 mb-6">
          <div>
            <span className="text-[10px] font-black uppercase tracking-widest text-neutral-500">
              Investigation Agent
            </span>
            <h3 className="text-xl font-black text-black mt-1">
              Case Analysis Assistant
            </h3>
          </div>
          <span className="inline-flex border border-black/15 bg-neutral-50 px-2 py-1 text-[8px] font-black uppercase tracking-widest text-neutral-600">
            {isFollowup ? "Active Session" : "Ready"}
          </span>
        </div>

        {/* Timeline Progress */}
        <div className="grid grid-cols-3 gap-2 mb-8 text-[9px] font-black uppercase tracking-wider text-neutral-400">
          <div className="border-t-2 border-black pt-2 text-black">
            1. Intake Complete
          </div>
          <div className={`border-t-2 pt-2 ${isFollowup ? "border-black text-black" : "border-neutral-200"}`}>
            2. Assistant Review
          </div>
          <div className="border-t-2 border-neutral-200 pt-2">
            3. Final Report
          </div>
        </div>

        {!isFollowup ? (
          /* Start State */
          <div className="space-y-6">
            <div className="border border-black/5 bg-neutral-50 p-4">
              <p className="text-xs font-bold text-neutral-700 leading-relaxed">
                The Case Analysis Assistant will inspect the case record for <strong>{caseData.title}</strong>, execute vector and graph retrieval models, mapping threat patterns to MITRE ATT&CK. It will identify missing parameters and guide you if follow-up details are recommended.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
              <div>
                <label htmlFor="assistant-report-type" className="text-[10px] font-black uppercase tracking-wider text-neutral-500 block mb-1">
                  Report Type
                </label>
                <select
                  id="assistant-report-type"
                  value={reportType}
                  onChange={(e) => onReportTypeChange(e.target.value as ReportType)}
                  className="w-full border border-black/15 bg-white px-2.5 py-1.5 text-xs font-semibold text-black focus:outline-none focus:border-black"
                >
                  <option value="overview">Case Overview</option>
                  <option value="subject">Evidence & Indicators</option>
                  <option value="timeline">Incident Timeline</option>
                  <option value="vulnerability">Exposure & Risk</option>
                </select>
              </div>

              <div className="flex flex-col justify-end pb-1.5 pt-2">
                <label htmlFor="assistant-legal" className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    id="assistant-legal"
                    type="checkbox"
                    checked={legal}
                    onChange={(e) => onLegalChange(e.target.checked)}
                    className="accent-black h-4 w-4"
                  />
                  <span className="text-xs font-semibold text-neutral-800">
                    Include Thai Legal Assessment
                  </span>
                </label>
              </div>
            </div>
          </div>
        ) : (
          /* Follow-up State */
          <div className="space-y-6">
            <div className="space-y-4">
              {/* Interaction History / Structured Message */}
              <div className="flex gap-3">
                <div className="w-6 h-6 rounded-full bg-black text-white text-[9px] font-black flex items-center justify-center shrink-0 uppercase">
                  AI
                </div>
                <div className="border border-black/10 bg-neutral-50 p-3 text-xs leading-relaxed text-neutral-800 rounded-sm w-full">
                  <p className="font-bold text-black mb-1">CyberCase AI Assistant</p>
                  The system needs a few more details before producing a stronger preliminary report. Please check the follow-up request below and supply any context you have.
                </div>
              </div>

              <div className="flex gap-3">
                <div className="w-6 h-6 rounded-full bg-black text-white text-[9px] font-black flex items-center justify-center shrink-0 uppercase">
                  AI
                </div>
                <div className="border border-black bg-white p-4 text-xs leading-relaxed text-black rounded-sm w-full">
                  <p className="font-bold text-neutral-500 uppercase tracking-wider text-[9px] mb-1.5">
                    Follow-up Question from Case Assistant
                  </p>
                  <p className="font-bold text-neutral-900 leading-normal">
                    {workflow.followup_question}
                  </p>
                </div>
              </div>
            </div>

            <div className="mt-4">
              <label htmlFor="assistant-followup-answer" className="text-[10px] font-black uppercase tracking-wider text-neutral-500 block mb-1">
                Your Answer
              </label>
              <textarea
                id="assistant-followup-answer"
                rows={5}
                placeholder="Type available log metrics, attachment details, or system identifiers..."
                value={followupAnswer}
                onChange={(e) => onFollowupAnswerChange(e.target.value)}
                className="w-full border border-black/15 px-3 py-2 text-xs bg-[#FAF9F6] text-black focus:outline-none focus:border-black font-sans resize-none"
              />
            </div>
          </div>
        )}
      </div>

      <div className="mt-8 pt-4 border-t border-black/5 flex flex-wrap gap-3 justify-end">
        {!isFollowup ? (
          <button
            onClick={onStartAnalysis}
            disabled={isGenerating}
            className="border border-black bg-black px-5 py-2.5 text-xs font-black text-white hover:bg-neutral-800 disabled:opacity-40 transition uppercase tracking-wider"
          >
            {isGenerating ? "Analyzing..." : "Start Case Analysis"}
          </button>
        ) : (
          <>
            <button
              onClick={onForceGenerate}
              disabled={isGenerating}
              className="border border-black/15 bg-white px-4 py-2.5 text-xs font-black text-black hover:border-black transition uppercase tracking-wider"
            >
              Skip & Force Generate
            </button>
            <button
              disabled={!followupAnswer.trim() || isGenerating}
              onClick={onSubmitFollowup}
              className="border border-black bg-black px-5 py-2.5 text-xs font-black text-white hover:bg-neutral-800 disabled:opacity-40 transition uppercase tracking-wider"
            >
              {isGenerating ? "Submitting..." : "Submit Answer"}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
