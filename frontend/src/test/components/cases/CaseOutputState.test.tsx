import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import CaseOutputSummaryCards, {
  OutputProvenance,
} from "@/components/cases/CaseOutputState";
import { makeCaseOutputs, makeOutputItem } from "@/test/caseOutputs";

describe("CaseOutputSummaryCards lifecycle", () => {
  it("labels backend evidence origins distinctly", () => {
    render(
      <>
        <OutputProvenance
          item={makeOutputItem({ source_type: "user_input" })}
        />
        <OutputProvenance item={makeOutputItem({ source_type: "log" })} />
        <OutputProvenance
          item={makeOutputItem({ source_type: "document" })}
        />
      </>,
    );

    expect(screen.getByText("User-provided input")).toBeInTheDocument();
    expect(screen.getByText("Log evidence")).toBeInTheDocument();
    expect(screen.getByText("Document evidence")).toBeInTheDocument();
  });

  it("summarizes every current evidence origin", () => {
    render(
      <CaseOutputSummaryCards
        data={makeCaseOutputs("CASE-OUTPUTS", {
          evidence: [
            makeOutputItem({ item_id: "USER-1", source_type: "user_input" }),
            makeOutputItem({ item_id: "LOG-1", source_type: "log" }),
            makeOutputItem({ item_id: "DOC-1", source_type: "document" }),
          ],
        })}
      />,
    );

    expect(
      screen.getByText("User-provided input / Log evidence / Document evidence"),
    ).toBeInTheDocument();
  });

  it("shows zero generated gaps and recommendations before analysis", () => {
    render(<CaseOutputSummaryCards data={makeCaseOutputs("CASE-OUTPUTS")} />);
    expect(screen.getByText("Run analysis to identify evidence gaps.")).toBeInTheDocument();
    expect(screen.getByText("Run analysis to generate recommendations.")).toBeInTheDocument();
    expect(screen.getAllByText("Analysis not started").length).toBeGreaterThan(0);
  });

  it("shows pending state without promoting historical outputs", () => {
    const data = makeCaseOutputs("CASE-OUTPUTS", { status: "pending" });
    data.historical_outputs.gaps = {
      historical_count: 1,
      items: [makeOutputItem({ item_id: "OLD-GAP", title: "Old gap", case_version: 1 })],
    };
    render(<CaseOutputSummaryCards data={data} />);
    expect(screen.getAllByText("Analysis pending").length).toBeGreaterThan(0);
    expect(screen.getByText(/Previous gaps are not counted as current/)).toBeInTheDocument();
    expect(screen.queryByText("Old gap")).not.toBeInTheDocument();
  });

  it("shows only current completed-run items and provenance", () => {
    render(
      <CaseOutputSummaryCards
        data={makeCaseOutputs("CASE-OUTPUTS", {
          status: "completed",
          gaps: [makeOutputItem({ item_id: "GAP-1", title: "Collect headers" })],
          recommendations: [makeOutputItem({ item_id: "REC-1", title: "Reset sessions" })],
        })}
      />,
    );
    expect(screen.getByText("Collect headers")).toBeInTheDocument();
    expect(screen.getByText("Reset sessions")).toBeInTheDocument();
    expect(screen.getAllByText("Current analysis completed").length).toBeGreaterThan(0);
  });

  it.each([
    ["stale", "Analysis stale"],
    ["failed", "Analysis failed"],
    ["expired", "Analysis context expired"],
  ] as const)("renders the %s lifecycle without inferred current outputs", (status, label) => {
    render(<CaseOutputSummaryCards data={makeCaseOutputs("CASE-OUTPUTS", { status })} />);
    expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    expect(screen.getByText("Run analysis to generate recommendations.")).toBeInTheDocument();
  });
});
