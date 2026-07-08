import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import CaseRouteState from "@/components/cases/CaseRouteState";

describe("CaseRouteState", () => {
  it("renders an invalid case not-found state", () => {
    render(<CaseRouteState title="Case Report" message="Case CASE-MISSING was not found." />);

    expect(screen.getByText("Case CASE-MISSING was not found.")).toBeInTheDocument();
  });
});
