import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CasesPage from "./page";
import { renderWithQueryClient } from "@/test/renderWithQueryClient";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

vi.mock("@/lib/cases", async () => {
  const actual = await vi.importActual<typeof import("@/lib/cases")>("@/lib/cases");
  return {
    ...actual,
    listCases: vi.fn().mockResolvedValue([]),
    createCase: vi.fn().mockResolvedValue({
      case_id: "CASE-REDIRECT",
      title: "Redirect case",
      case_type: "incident",
      status: "new",
      severity: "unknown",
      incident_summary: "",
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
    }),
  };
});

describe("CasesPage", () => {
  beforeEach(() => {
    push.mockReset();
  });

  it("redirects to an intake URL containing the created caseId", async () => {
    renderWithQueryClient(<CasesPage />);

    fireEvent.change(screen.getByLabelText("Case title"), {
      target: { value: "Redirect case" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create Case" }));

    await waitFor(() => {
      expect(push).toHaveBeenCalledWith("/cases/CASE-REDIRECT/intake");
    });
  });
});
