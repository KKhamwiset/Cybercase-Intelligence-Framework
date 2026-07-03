import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useCaseReport } from "./useCaseReport";
import { getCaseReport } from "@/lib/reports";
import type { ReportViewModel } from "@/lib/reports";
import { renderWithQueryClient } from "@/test/renderWithQueryClient";

vi.mock("@/lib/reports", async () => {
  const actual = await vi.importActual<typeof import("@/lib/reports")>("@/lib/reports");
  return {
    ...actual,
    getCaseReport: vi.fn(),
  };
});

function makeReport(caseId: string): ReportViewModel {
  return {
    case_id: caseId,
    report_type: "incident_analysis",
    generated_at: "2026-02-14T00:00:00Z",
    report_status: "ready_for_review",
    sections: [],
    gaps: [],
    limitations: [],
    metadata: {
      confirmed_findings: 1,
      candidate_findings: 0,
      unknown_findings: 0,
      evidence_count: 1,
      gap_count: 0,
    },
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function Harness({ caseId }: { caseId: string }) {
  const { report, isLoading } = useCaseReport(caseId);

  return <div>{isLoading ? "loading" : report?.case_id ?? "empty"}</div>;
}

describe("useCaseReport", () => {
  beforeEach(() => {
    vi.mocked(getCaseReport).mockReset();
  });

  it("fetches by caseId and prevents stale case data after switching cases", async () => {
    const caseA = deferred<ReportViewModel>();
    const caseB = deferred<ReportViewModel>();

    vi.mocked(getCaseReport).mockImplementation((caseId) => {
      return caseId === "CASE-A" ? caseA.promise : caseB.promise;
    });

    const { rerender } = renderWithQueryClient(<Harness caseId="CASE-A" />);

    expect(getCaseReport).toHaveBeenCalledWith("CASE-A", expect.any(AbortSignal));

    rerender(<Harness caseId="CASE-B" />);

    expect(getCaseReport).toHaveBeenCalledWith("CASE-B", expect.any(AbortSignal));

    caseA.resolve(makeReport("CASE-A"));

    await waitFor(() => {
      expect(screen.queryByText("CASE-A")).not.toBeInTheDocument();
    });

    caseB.resolve(makeReport("CASE-B"));

    await waitFor(() => {
      expect(screen.getByText("CASE-B")).toBeInTheDocument();
    });
  });
});
