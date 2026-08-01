import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import HomePage from "@/components/home/HomePage";

describe("HomePage", () => {
  it("sends the case entry point directly to the persistent chat workspace", () => {
    render(<HomePage />);

    expect(screen.getByRole("link", { name: "Start case" })).toHaveAttribute(
      "href",
      "/chat",
    );
    const openChatLinks = screen.getAllByRole("link", { name: "Open chat" });
    expect(openChatLinks).toHaveLength(2);
    for (const link of openChatLinks) {
      expect(link).toHaveAttribute("href", "/chat");
    }
  });
});
