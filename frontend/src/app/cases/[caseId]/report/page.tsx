"use client";

import { useParams } from "next/navigation";

import CaseRouteState from "@/components/cases/CaseRouteState";
import CaseStageShell from "@/components/cases/CaseStageShell";
import AttackMappingSection from "@/components/report/AttackMappingSection";
import EvidenceRegisterSection from "@/components/report/EvidenceRegisterSection";
import ExecutiveSummarySection from "@/components/report/ExecutiveSummarySection";
import GapsAndLimitationsSection from "@/components/report/GapsAndLimitationsSection";
import ReportHeader from "@/components/report/ReportHeader";
import ReportSection from "@/components/report/ReportSection";
import ReportStatusBanner from "@/components/report/ReportStatusBanner";
import TimelineSection from "@/components/report/TimelineSection";
import { isNotFound, useCase } from "@/hooks/useCase";
import { useCaseReport } from "@/hooks/useCaseReport";
import { getRouteParam } from "@/lib/routeParams";
import type { ActionItemView, ReportSection as ReportSectionView } from "@/lib/reports";
import { FindingStatusBadge } from "@/components/report/status";

function isAction(value: unknown): value is ActionItemView {
  return typeof value === "object" && value !== null && "action_id" in value && "title" in value;
}

function TextListSection({
  section,
  field,
  empty,
}: {
  section: ReportSectionView;
  field: string;
  empty: string;
}) {
  const values = Array.isArray(section.content[field])
    ? section.content[field].filter((item): item is string => typeof item === "string")
    : [];

  return (
    <ReportSection section={section}>
      {values.length ? (
        <ul className="grid gap-2 text-sm font-semibold text-neutral-800 md:grid-cols-2">
          {values.map((item) => (
            <li key={item} className="border border-black/10 px-3 py-2">
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm font-semibold text-neutral">{empty}</p>
      )}
    </ReportSection>
  );
}

function ActionSection({
  section,
  field,
  empty,
}: {
  section: ReportSectionView;
  field: string;
  empty: string;
}) {
  const actions = Array.isArray(section.content[field])
    ? section.content[field].filter(isAction)
    : [];

  return (
    <ReportSection section={section}>
      {actions.length ? (
        <div className="grid gap-3 md:grid-cols-2">
          {actions.map((action) => (
            <div key={action.action_id} className="border border-black/10 p-3">
              <div className="flex items-start justify-between gap-3">
                <p className="font-black">{action.title}</p>
                <FindingStatusBadge status={action.status} />
              </div>
              {action.description ? (
                <p className="mt-2 text-sm text-neutral-800">{action.description}</p>
              ) : null}
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm font-semibold text-neutral">{empty}</p>
      )}
    </ReportSection>
  );
}

function OverviewSection({ section }: { section: ReportSectionView }) {
  const rawFields: Array<[string, unknown]> = [
    ["Title", section.content.title],
    ["Case type", section.content.case_type],
    ["Status", section.content.status],
    ["Severity", section.content.severity],
    ["Analyst notes", section.content.analyst_notes],
  ];
  const fields: Array<[string, string]> = rawFields.flatMap(([label, value]) =>
    typeof value === "string" && value.length > 0 ? [[label, value]] : [],
  );

  return (
    <ReportSection section={section}>
      <dl className="grid gap-3 text-sm md:grid-cols-2">
        {fields.map(([label, value]) => (
          <div key={label} className="border border-black/10 p-3">
            <dt className="text-[10px] font-black uppercase text-neutral">{label}</dt>
            <dd className="mt-1 font-semibold text-neutral-900">{value}</dd>
          </div>
        ))}
      </dl>
    </ReportSection>
  );
}

function ScopeSection({ section }: { section: ReportSectionView }) {
  const affectedUsers = Array.isArray(section.content.affected_users)
    ? section.content.affected_users.filter((item): item is string => typeof item === "string")
    : [];
  const affectedAssets = Array.isArray(section.content.affected_assets)
    ? section.content.affected_assets.filter((item): item is string => typeof item === "string")
    : [];

  return (
    <ReportSection section={section}>
      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <p className="mono-label">Affected Users</p>
          <ul className="mt-2 space-y-2 text-sm font-semibold text-neutral-800">
            {affectedUsers.length ? affectedUsers.map((item) => <li key={item}>{item}</li>) : <li>Unknown</li>}
          </ul>
        </div>
        <div>
          <p className="mono-label">Affected Assets</p>
          <ul className="mt-2 space-y-2 text-sm font-semibold text-neutral-800">
            {affectedAssets.length ? affectedAssets.map((item) => <li key={item}>{item}</li>) : <li>Unknown</li>}
          </ul>
        </div>
      </div>
    </ReportSection>
  );
}

function renderSection(section: ReportSectionView) {
  switch (section.id) {
    case "executive_summary":
      return <ExecutiveSummarySection key={section.id} section={section} />;
    case "incident_overview":
      return <OverviewSection key={section.id} section={section} />;
    case "scope_and_affected_assets":
      return <ScopeSection key={section.id} section={section} />;
    case "attack_timeline":
      return <TimelineSection key={section.id} section={section} />;
    case "mitre_attack_mapping":
      return <AttackMappingSection key={section.id} section={section} />;
    case "evidence_register":
      return <EvidenceRegisterSection key={section.id} section={section} />;
    case "containment_and_response_actions":
      return (
        <ActionSection
          key={section.id}
          section={section}
          field="actions"
          empty="No containment actions available."
        />
      );
    case "recommendations":
      return (
        <ActionSection
          key={section.id}
          section={section}
          field="recommendations"
          empty="No recommendations available."
        />
      );
    case "evidence_gaps_and_limitations":
      return <GapsAndLimitationsSection key={section.id} section={section} />;
    default:
      return (
        <TextListSection
          key={section.id}
          section={section}
          field="items"
          empty="No section content available."
        />
      );
  }
}

export default function CaseReportPage() {
  const params = useParams();
  const caseId = getRouteParam(params.caseId);
  const caseQuery = useCase(caseId);
  const { report, isLoading, error, notFound } = useCaseReport(caseId);

  if (!caseId) {
    return <CaseRouteState title="Case Report" message="No case ID provided." />;
  }

  if (caseQuery.isLoading) {
    return <CaseRouteState title="Case Report" message={`Loading case ${caseId}.`} />;
  }

  if (isNotFound(caseQuery.error) || notFound) {
    return <CaseRouteState title="Case Report" message={`Case ${caseId} was not found.`} />;
  }

  if (caseQuery.error || !caseQuery.data) {
    return <CaseRouteState title="Case Report" message="Could not load this case." />;
  }

  return (
    <CaseStageShell activeStage="report" caseData={caseQuery.data}>
      <div className="bg-neutral-100">
        {isLoading ? (
          <div className="m-5 border border-black/10 bg-white p-5 text-sm font-semibold">
            Loading report for case {caseId}.
          </div>
        ) : null}
        {error ? (
          <div className="m-5 border border-black/10 bg-white p-5 text-sm font-semibold">
            {error}
          </div>
        ) : null}
        {report ? (
          <div className="mx-auto max-w-6xl border-x border-black/10 bg-white">
            <ReportHeader report={report} />
            <ReportStatusBanner report={report} />
            {report.sections.map(renderSection)}
          </div>
        ) : null}
      </div>
    </CaseStageShell>
  );
}
