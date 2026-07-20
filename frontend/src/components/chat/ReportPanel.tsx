import type { ReactNode } from "react";
import type { CyberCaseReport } from "@/lib/api";
import type { AnalysisAvailability } from "./types";

interface ReportPanelProps {
  report: CyberCaseReport | null;
  reportabilityReasons: string[];
  availability: AnalysisAvailability;
  inlineInspector: ReactNode;
}

function ReportList({ items }: { items: string[] }) {
  if (items.length === 0) {
    return <p className="text-sm text-gray-500">None returned.</p>;
  }
  return (
    <ul className="list-disc space-y-2 pl-5 text-sm leading-6 text-gray-700">
      {items.map((item, index) => (
        <li key={`${item}-${index}`}>{item}</li>
      ))}
    </ul>
  );
}

export function ReportPanel({
  report,
  reportabilityReasons,
  availability,
  inlineInspector,
}: ReportPanelProps) {
  return (
    <section
      id="report-panel"
      role="tabpanel"
      aria-labelledby="vertical-report-tab horizontal-report-tab"
      className="h-full overflow-y-auto bg-white px-4 py-6 sm:px-6 lg:px-8"
    >
      <div className="mx-auto max-w-4xl">
        <header className="border-b border-gray-200 pb-5">
          <p className="text-xs font-extrabold uppercase tracking-[0.16em] text-gray-500">
            Backend-owned output
          </p>
          <h2 className="mt-2 text-2xl font-extrabold tracking-tight">Report</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-gray-600">
            The report appears only when the integrated analysis endpoint returns
            a reportable artifact.
          </p>
        </header>

        {report ? (
          <article className="space-y-8 py-7">
            <section>
              <h3 className="text-lg font-extrabold">Case summary</h3>
              <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-gray-700">
                {report.case_summary}
              </p>
            </section>
            <section>
              <h3 className="text-lg font-extrabold">Detected indicators</h3>
              <div className="mt-3">
                <ReportList items={report.detected_indicators} />
              </div>
            </section>
            <section>
              <h3 className="text-lg font-extrabold">MITRE mapping</h3>
              <div className="mt-3">
                <ReportList items={report.mitre_mapping} />
              </div>
            </section>
            <section>
              <h3 className="text-lg font-extrabold">Mapping justification</h3>
              <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-gray-700">
                {report.mapping_justification}
              </p>
            </section>
            <section>
              <h3 className="text-lg font-extrabold">Evidence to investigate</h3>
              <div className="mt-3">
                <ReportList items={report.evidence_to_investigate} />
              </div>
            </section>
            <section>
              <h3 className="text-lg font-extrabold">
                Preliminary recommendations
              </h3>
              <div className="mt-3">
                <ReportList items={report.preliminary_recommendations} />
              </div>
            </section>
            <section>
              <h3 className="text-lg font-extrabold">System limitations</h3>
              <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-gray-700">
                {report.system_limitations}
              </p>
            </section>
          </article>
        ) : reportabilityReasons.length > 0 ? (
          <div className="py-8">
            <h3 className="text-base font-extrabold">Report not generated</h3>
            <p className="mt-2 text-sm leading-6 text-gray-600">
              The backend returned these reportability reasons:
            </p>
            <ul className="mt-4 space-y-2">
              {reportabilityReasons.map((reason, index) => (
                <li
                  key={`${reason}-${index}`}
                  className="rounded-xl border border-gray-200 bg-gray-50 px-3 py-2 font-mono text-xs text-gray-800"
                >
                  {reason}
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <div className="py-12 text-sm leading-6 text-gray-600">
            {availability.status === "loading" ? (
              <p role="status">Waiting for validated analysis…</p>
            ) : availability.status === "unavailable" ||
              availability.status === "error" ? (
              <p>{availability.message}</p>
            ) : availability.status === "available" ? (
              <p>The backend did not return a report or reportability reason.</p>
            ) : (
              <p>No integrated report is available yet.</p>
            )}
          </div>
        )}

        <div className="mt-8 min-[1100px]:hidden">{inlineInspector}</div>
      </div>
    </section>
  );
}
