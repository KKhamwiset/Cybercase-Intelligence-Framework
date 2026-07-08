import React from "react";
import type { StructuredCase } from "@/lib/cases";
import type { ReportWorkflowResponse, CaseInformationCompleteness, ReportType } from "@/lib/api";

interface CaseContextPanelProps {
  caseData: StructuredCase;
  workflow: ReportWorkflowResponse | null;
  reportType: ReportType;
  legal: boolean;
  completeness: CaseInformationCompleteness | null;
}

export default function CaseContextPanel({
  caseData,
  workflow,
  reportType,
  legal,
  completeness,
}: CaseContextPanelProps) {
  const isFollowup = workflow?.status === "followup";
  const percentage = completeness?.percentage ?? 0;
  const missingFields = completeness?.missing_fields ?? [];

  return (
    <div className="border border-black/10 bg-white p-6 md:p-8 space-y-8">
      {/* Case Overview Section */}
      <div>
        <span className="text-[10px] font-black uppercase tracking-widest text-neutral-500">
          Selected Case Context
        </span>
        <h4 className="text-base font-black text-black mt-1 leading-snug">
          {caseData.title}
        </h4>
        <div className="mt-3 flex flex-wrap gap-2 text-[8px] font-black uppercase tracking-widest">
          <span className="border border-black/15 px-2 py-0.5 bg-neutral-50 text-neutral-700">
            ID: {caseData.case_id}
          </span>
          <span className={`border px-2 py-0.5 ${
            caseData.severity === "critical" || caseData.severity === "high"
              ? "border-red-500/20 bg-red-50 text-red-700"
              : caseData.severity === "medium"
              ? "border-amber-500/20 bg-amber-50 text-amber-700"
              : "border-black/15 bg-neutral-50 text-neutral-700"
          }`}>
            {caseData.severity} Severity
          </span>
          <span className="border border-black/15 px-2 py-0.5 bg-neutral-50 text-neutral-700">
            {caseData.status}
          </span>
        </div>

        {/* Workflow Settings Section */}
        <div className="mt-4 border border-black/5 bg-neutral-50 p-3 rounded-sm space-y-2">
          <span className="text-[9px] font-black uppercase tracking-wider text-neutral-400 block border-b border-black/5 pb-1">
            Analysis Configuration
          </span>
          <div className="grid grid-cols-2 gap-2 text-[10px]">
            <div>
              <p className="text-neutral-400 text-[8px] uppercase font-bold">Report Type</p>
              <p className="font-bold text-neutral-800 capitalize">{reportType}</p>
            </div>
            <div>
              <p className="text-neutral-400 text-[8px] uppercase font-bold">Legal Assessment</p>
              <p className="font-bold text-neutral-800">{legal ? "Enabled" : "Disabled"}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Case Readiness Section */}
      <div className="border-t border-neutral-100 pt-6">
        <div className="flex justify-between items-center mb-2">
          <span className="text-[10px] font-black uppercase tracking-wider text-neutral-500">
            Case Fact Readiness
          </span>
          <span className="text-xs font-black text-black">
            {completeness ? `${percentage}%` : "Pending initial review"}
          </span>
        </div>
        
        {completeness ? (
          <>
            <div className="w-full h-2 bg-neutral-100 border border-black/5 rounded-full overflow-hidden">
              <div
                className="h-full bg-black transition-all duration-500"
                style={{ width: `${percentage}%` }}
              />
            </div>
            <p className="text-[10px] font-semibold text-neutral-500 mt-2">
              {completeness.status}
            </p>
          </>
        ) : (
          <div className="w-full h-2 bg-neutral-100 border border-black/5 rounded-full overflow-hidden">
            <div className="h-full bg-neutral-300 w-1/4 animate-pulse" />
          </div>
        )}
      </div>

      {/* Missing Information Fields */}
      {isFollowup && missingFields.length > 0 && (
        <div className="border-t border-neutral-100 pt-6">
          <span className="text-[10px] font-black uppercase tracking-wider text-neutral-500 block mb-3">
            Recommended Missing Information
          </span>
          <div className="flex flex-wrap gap-1.5">
            {missingFields.map((field, idx) => (
              <span
                key={idx}
                className="inline-flex border border-neutral-200 bg-neutral-50 px-2 py-1 text-[9px] font-semibold text-neutral-700 rounded-sm"
              >
                {field}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* MITRE Candidate Preview */}
      <div className="border-t border-neutral-100 pt-6">
        <span className="text-[10px] font-black uppercase tracking-wider text-neutral-500 block mb-3">
          MITRE ATT&CK Preview
        </span>
        {caseData.attack_mappings && caseData.attack_mappings.length > 0 ? (
          <div className="space-y-2 max-h-[180px] overflow-y-auto pr-1">
            {caseData.attack_mappings.map((mapping) => (
              <div
                key={mapping.mapping_id}
                className="border border-black/5 bg-neutral-50 p-2.5 rounded-sm flex items-start gap-2.5"
              >
                <div className="bg-black text-white text-[8px] font-black px-1.5 py-0.5 rounded-sm shrink-0">
                  {mapping.technique_id}
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-bold text-black truncate leading-tight">
                    {mapping.technique_name}
                  </p>
                  {mapping.tactic && (
                    <p className="text-[9px] font-medium text-neutral-400 mt-0.5">
                      {mapping.tactic}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs italic text-neutral-400">
            No MITRE mappings cataloged on intake. Generator will execute deep threat model analysis.
          </p>
        )}
      </div>

      {/* Footer Info Disclaimer */}
      <div className="border-t border-neutral-100 pt-6">
        <div className="bg-neutral-50 border border-black/5 p-3.5 rounded-sm">
          <p className="text-[9px] leading-relaxed text-neutral-500 font-medium">
            Note: All intelligence analysis, RAG matching, and final MITRE ATT&CK technique mappings remain preliminary and must be reviewed by a certified security analyst before external case submission.
          </p>
        </div>
      </div>
    </div>
  );
}
