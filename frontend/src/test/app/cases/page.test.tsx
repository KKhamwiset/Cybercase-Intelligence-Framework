import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CasesPage from "@/app/cases/page";
import { createCase, listCases } from "@/lib/cases";
import { renderWithQueryClient } from "@/test/renderWithQueryClient";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

vi.mock("@/lib/cases", async () => {
  const actual = await vi.importActual<typeof import("@/lib/cases")>("@/lib/cases");
  return {
    ...actual,
    listCases: vi.fn(),
    createCase: vi.fn(),
  };
});

const createdCase = {
  case_id: "CASE-REDIRECT",
  case_version: 1,
  title: "Redirect case",
  case_type: "incident",
  status: "new" as const,
  severity: "unknown" as const,
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
};

describe("CasesPage", () => {
  beforeEach(() => {
    push.mockReset();
    vi.mocked(listCases).mockReset();
    vi.mocked(createCase).mockReset();
    vi.mocked(listCases).mockResolvedValue([]);
    vi.mocked(createCase).mockResolvedValue(createdCase);
  });

  it("redirects to an intake URL containing the created caseId", async () => {
    renderWithQueryClient(<CasesPage />);

    fireEvent.change(screen.getByLabelText("Case title"), {
      target: { value: "  Redirect case  " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create Case" }));

    await waitFor(() => {
      expect(createCase).toHaveBeenCalledWith({ title: "Redirect case" });
      expect(push).toHaveBeenCalledWith("/cases/CASE-REDIRECT/intake");
    });
  });

  it("renders labeled case fields, semantic states, and updated-time fallbacks", async () => {
    vi.mocked(listCases).mockResolvedValue([
      {
        case_id: "CASE-HIGH",
        case_version: 3,
        title: "Mailbox compromise with a deliberately descriptive investigation title",
        status: "investigating",
        severity: "high",
        updated_at: "2026-07-10T12:00:00Z",
      },
      {
        case_id: "CASE-UNKNOWN",
        case_version: 1,
        title: "Unclassified alert",
        status: "unknown",
        severity: "unknown",
        updated_at: null,
      },
    ]);

    renderWithQueryClient(<CasesPage />);

    expect(await screen.findByRole("link", { name: /Mailbox compromise/i })).toHaveAttribute(
      "href",
      "/cases/CASE-HIGH/intake",
    );
    expect(screen.getByRole("columnheader", { name: "Case" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Status" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Severity" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Updated" })).toBeInTheDocument();
    expect(screen.getByText("investigating")).toBeInTheDocument();
    expect(screen.getByText("high")).toBeInTheDocument();
    expect(screen.getByText("10 Jul 2026")).toBeInTheDocument();
    expect(screen.getByText("Not recorded")).toBeInTheDocument();
  });

  it("shows a purposeful empty state", async () => {
    renderWithQueryClient(<CasesPage />);

    expect(await screen.findByRole("heading", { name: "No investigations yet" })).toBeInTheDocument();
    expect(screen.getByText(/Create the first case/i)).toBeInTheDocument();
  });

  it("shows loading skeletons while the registry request is pending", () => {
    vi.mocked(listCases).mockImplementation(() => new Promise(() => undefined));
    renderWithQueryClient(<CasesPage />);

    expect(screen.getByRole("status", { name: "Loading saved investigations" })).toBeInTheDocument();
  });

  it("offers a retry after the registry request fails", async () => {
    vi.mocked(listCases)
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce([
        {
          case_id: "CASE-RETRY",
          case_version: 1,
          title: "Recovered registry case",
          status: "new",
          severity: "low",
          updated_at: null,
        },
      ]);

    renderWithQueryClient(<CasesPage />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Could not load saved investigations");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByRole("link", { name: "Recovered registry case" })).toBeInTheDocument();
    expect(listCases).toHaveBeenCalledTimes(2);
  });

  it("defaults a blank title and blocks titles longer than 255 characters", async () => {
    renderWithQueryClient(<CasesPage />);

    fireEvent.click(screen.getByRole("button", { name: "Create Case" }));
    await waitFor(() => expect(createCase).toHaveBeenCalledWith({ title: "Untitled case" }));

    vi.mocked(createCase).mockClear();
    fireEvent.change(screen.getByLabelText("Case title"), {
      target: { value: "x".repeat(256) },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create Case" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("255 characters or fewer");
    expect(createCase).not.toHaveBeenCalled();
  });
});
