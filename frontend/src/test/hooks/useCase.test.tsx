import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useCase } from "@/hooks/useCase";
import { getCase } from "@/lib/cases";
import type { StructuredCase } from "@/lib/cases";
import { renderWithQueryClient } from "@/test/renderWithQueryClient";

vi.mock("@/lib/cases", async () => {
  const actual = await vi.importActual<typeof import("@/lib/cases")>("@/lib/cases");
  return {
    ...actual,
    getCase: vi.fn(),
  };
});

function makeCase(caseId: string, incidentSummary = ""): StructuredCase {
  return {
    case_id: caseId,
    case_version: 1,
    title: `Case ${caseId}`,
    case_type: "incident",
    status: "new",
    severity: "unknown",
    incident_summary: incidentSummary,
    affected_users: [],
    affected_assets: [],
    timeline_events: [],
    evidence_items: [],
    attack_mappings: [],
    containment_actions: [],
    recommendations: [],
    gaps: [],
    limitations: [],
    analyst_notes: "",
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
  const query = useCase(caseId);

  if (query.isLoading) {
    return <div>loading</div>;
  }
  if (query.error) {
    return <div>not-found</div>;
  }
  return <div>{query.data?.incident_summary || query.data?.case_id}</div>;
}

describe("useCase", () => {
  beforeEach(() => {
    vi.mocked(getCase).mockReset();
  });

  it("reloads case data from the URL caseId", async () => {
    vi.mocked(getCase).mockResolvedValue(makeCase("CASE-REFRESH", "Reloaded from backend"));

    renderWithQueryClient(<Harness caseId="CASE-REFRESH" />);

    await waitFor(() => {
      expect(screen.getByText("Reloaded from backend")).toBeInTheDocument();
    });
    expect(getCase).toHaveBeenCalledWith("CASE-REFRESH", expect.any(AbortSignal));
  });

  it("does not show stale Case A data after switching to Case B", async () => {
    const caseA = deferred<StructuredCase>();
    const caseB = deferred<StructuredCase>();

    vi.mocked(getCase).mockImplementation((caseId) => {
      return caseId === "CASE-A" ? caseA.promise : caseB.promise;
    });

    const { rerender } = renderWithQueryClient(<Harness caseId="CASE-A" />);
    rerender(<Harness caseId="CASE-B" />);
    caseA.resolve(makeCase("CASE-A"));

    await waitFor(() => {
      expect(screen.queryByText("CASE-A")).not.toBeInTheDocument();
    });

    caseB.resolve(makeCase("CASE-B"));

    await waitFor(() => {
      expect(screen.getByText("CASE-B")).toBeInTheDocument();
    });
  });
});
