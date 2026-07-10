import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import CyberCaseShell from "@/components/CyberCaseShell";

describe("CyberCaseShell", () => {
  it("exposes matching desktop and mobile navigation without client-side menu state", () => {
    render(
      <CyberCaseShell activeNav="Investigate" title="Investigations">
        <p>Workspace content</p>
      </CyberCaseShell>,
    );

    const desktopNav = screen.getByRole("navigation", { name: "Primary navigation" });
    const mobileNav = screen.getByRole("navigation", { name: "Mobile navigation" });

    expect(within(desktopNav).getByRole("link", { name: "Investigate" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(within(mobileNav).getByRole("link", { name: "Investigate" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(within(mobileNav).getByRole("link", { name: "Home" })).toHaveAttribute("href", "/");
    expect(within(mobileNav).getByRole("link", { name: "Reports" })).toHaveAttribute(
      "href",
      "/reports",
    );
  });
});
