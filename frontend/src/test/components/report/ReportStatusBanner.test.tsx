import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import ReportStatusBanner from "@/components/report/ReportStatusBanner";
import type { ReportViewModel } from "@/lib/reports";

function report(status: ReportViewModel["report_status"]): ReportViewModel {
  return {
    case_id: "CASE-001",
    report_type: "incident_analysis",
    generated_at: "2026-02-14T00:00:00Z",
    report_status: status,
    sections: [],
    gaps: [],
    limitations: [],
    metadata: {
      confirmed_findings: 0,
      candidate_findings: 0,
      unknown_findings: 0,
      evidence_count: 0,
      gap_count: 0,
    },
  };
}

describe("ReportStatusBanner", () => {
  it("shows the incomplete gap banner", () => {
    render(<ReportStatusBanner report={report("incomplete")} />);

    expect(screen.getByText("Incomplete: evidence gaps detected")).toBeInTheDocument();
  });
});
