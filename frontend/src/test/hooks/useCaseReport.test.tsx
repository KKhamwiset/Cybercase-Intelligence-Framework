import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useCaseReport } from "@/hooks/useCaseReport";
import { getLatestCaseReport, type ReportCompletedResponse } from "@/lib/api";
import { renderWithQueryClient } from "@/test/renderWithQueryClient";
import { makeCompletedReport } from "@/test/reportWorkflow";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, getLatestCaseReport: vi.fn() };
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

function Harness({ caseId }: { caseId: string }) {
  const { report, isLoading } = useCaseReport(caseId);
  return <div>{isLoading ? "loading" : report?.report_id ?? "empty"}</div>;
}

describe("useCaseReport", () => {
  beforeEach(() => {
    vi.mocked(getLatestCaseReport).mockReset();
  });

  it("fetches the canonical workflow by caseId and prevents stale case data", async () => {
    const caseA = deferred<ReportCompletedResponse>();
    const caseB = deferred<ReportCompletedResponse>();
    vi.mocked(getLatestCaseReport).mockImplementation((caseId) =>
      caseId === "CASE-A" ? caseA.promise : caseB.promise,
    );

    const { rerender } = renderWithQueryClient(<Harness caseId="CASE-A" />);
    expect(getLatestCaseReport).toHaveBeenCalledWith("CASE-A");
    rerender(<Harness caseId="CASE-B" />);
    expect(getLatestCaseReport).toHaveBeenCalledWith("CASE-B");

    caseA.resolve(makeCompletedReport({ report: { report_id: "REPORT-A" } }));
    await waitFor(() => expect(screen.queryByText("REPORT-A")).not.toBeInTheDocument());

    caseB.resolve(makeCompletedReport({ report: { report_id: "REPORT-B" } }));
    await waitFor(() => expect(screen.getByText("REPORT-B")).toBeInTheDocument());
  });
});
