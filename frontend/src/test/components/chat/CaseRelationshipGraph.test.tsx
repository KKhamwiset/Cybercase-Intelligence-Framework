import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CaseRelationshipGraph } from "@/components/relationships/CaseRelationshipGraph";
import type {
  ChatBaselineEntity,
  ChatBaselineRelationship,
} from "@/lib/api";

class MockResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

if (typeof window !== "undefined") {
  if (!window.ResizeObserver) {
    window.ResizeObserver = MockResizeObserver as unknown as typeof ResizeObserver;
  }

  Object.defineProperty(HTMLElement.prototype, "clientWidth", {
    configurable: true,
    get() {
      return 1000;
    },
  });
  Object.defineProperty(HTMLElement.prototype, "clientHeight", {
    configurable: true,
    get() {
      return 600;
    },
  });
  Object.defineProperty(HTMLElement.prototype, "offsetWidth", {
    configurable: true,
    get() {
      return 1000;
    },
  });
  Object.defineProperty(HTMLElement.prototype, "offsetHeight", {
    configurable: true,
    get() {
      return 600;
    },
  });

  if (
    typeof SVGElement !== "undefined" &&
    !(SVGElement.prototype as unknown as { getBBox?: () => DOMRect }).getBBox
  ) {
    (
      SVGElement.prototype as unknown as { getBBox: () => DOMRect }
    ).getBBox = () =>
      ({
        x: 0,
        y: 0,
        width: 100,
        height: 100,
      }) as DOMRect;
  }
}

const entities: ChatBaselineEntity[] = [
  {
    entity_id: "ENT-001",
    name: "Employee account with a deliberately long descriptive label",
    entity_type: "account",
    reported_role: null,
    confidence: "high",
    source_message_ids: ["message-1"],
  },
  {
    entity_id: "ENT-002",
    name: "host-7",
    entity_type: "host",
    reported_role: null,
    confidence: "high",
    source_message_ids: ["message-1"],
  },
  {
    entity_id: "ENT-003",
    name: "Administrator group",
    entity_type: "group",
    reported_role: null,
    confidence: "medium",
    source_message_ids: ["message-2"],
  },
];

const relationships: ChatBaselineRelationship[] = [
  {
    relationship_id: "REL-001",
    subject_entity_id: "ENT-001",
    predicate: "signed_in_from",
    object_entity_id: "ENT-002",
    statement: "The employee account signed in from host-7.",
    status: "reported",
    confidence: "high",
    source_message_ids: ["message-1"],
  },
  {
    relationship_id: "REL-002",
    subject_entity_id: "ENT-001",
    predicate: "was_not_confirmed_as_member_of",
    object_entity_id: "ENT-003",
    statement:
      "Membership of the employee account in the administrator group was not established.",
    status: "not_established",
    confidence: "medium",
    source_message_ids: ["message-1", "message-2"],
  },
];

describe("CaseRelationshipGraph", () => {
  it("selects the first relationship and exposes accessible relationship controls", () => {
    const { container } = render(
      <CaseRelationshipGraph
        entities={entities}
        relationships={relationships}
      />,
    );

    const first = screen.getByRole("button", {
      name: /employee account.*host-7.*reported/i,
    });
    expect(first).toHaveAttribute("aria-pressed", "true");
    expect(first).toHaveAttribute("aria-controls");
    expect(container.querySelector("[aria-live='polite']")).toHaveTextContent(
      "The employee account signed in from host-7.",
    );
    expect(screen.getByText("Relationship canvas")).toBeInTheDocument();
    expect(container.querySelector("svg[aria-hidden='true']")).toBeInTheDocument();
    expect(
      container.querySelector("[data-relationship-graph-scroller='true']"),
    ).toHaveClass("min-w-0", "max-w-full", "overflow-x-auto");
    expect(container.querySelectorAll("[data-graph-node-id]")).toHaveLength(3);
    expect(container.querySelectorAll("[data-graph-edge-id]")).toHaveLength(2);
    expect(
      container.querySelector("[data-graph-edge-id='REL-001']"),
    ).toHaveAttribute("data-selected", "true");
    expect(
      container.querySelector("[data-graph-edge-id='REL-002']"),
    ).toHaveAttribute("data-selected", "false");
    expect(
      container.querySelector("[data-graph-node-id='ENT-001']"),
    ).toHaveAttribute("data-selected", "true");
    expect(
      container.querySelector("[data-graph-node-id='ENT-002']"),
    ).toHaveAttribute("data-selected", "true");
    expect(
      container.querySelector("[data-graph-node-id='ENT-003']"),
    ).toHaveAttribute("data-selected", "false");
  });

  it("updates the live detail and preserves text labels for uncertainty", () => {
    const { container } = render(
      <CaseRelationshipGraph
        entities={entities}
        relationships={relationships}
      />,
    );
    const second = screen.getByRole("button", {
      name: /employee account.*administrator group.*not established/i,
    });

    fireEvent.click(second);

    expect(second).toHaveAttribute("aria-pressed", "true");
    const liveDetail = container.querySelector("[aria-live='polite']");
    expect(liveDetail).not.toBeNull();
    expect(within(liveDetail as HTMLElement).getByText(/Membership of the employee/)).toBeInTheDocument();
    expect(within(liveDetail as HTMLElement).getByText("Not established")).toBeInTheDocument();
    expect(within(liveDetail as HTMLElement).getByText("message-2")).toBeInTheDocument();
    expect(
      container.querySelector("[data-graph-edge-id='REL-001']"),
    ).toHaveAttribute("data-selected", "false");
    expect(
      container.querySelector("[data-graph-edge-id='REL-002']"),
    ).toHaveAttribute("data-selected", "true");
    expect(
      container.querySelector("[data-graph-node-id='ENT-001']"),
    ).toHaveAttribute("data-selected", "true");
    expect(
      container.querySelector("[data-graph-node-id='ENT-002']"),
    ).toHaveAttribute("data-selected", "false");
    expect(
      container.querySelector("[data-graph-node-id='ENT-003']"),
    ).toHaveAttribute("data-selected", "true");
  });

  it("renders one dashed empty state without blank detail or graph panels", () => {
    render(<CaseRelationshipGraph entities={entities} relationships={[]} />);

    expect(
      screen.getByText("No explicit entity-to-entity relationship was extracted."),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Selected relationship detail"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Relationship canvas")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Relationship labels")).toBeInTheDocument();
    expect(
      screen.getByText(/The graph is a visual inspection aid/),
    ).toBeInTheDocument();
  });

  it("renders a self-relationship without non-finite SVG coordinates", () => {
    const selfRelationship: ChatBaselineRelationship = {
      relationship_id: "REL-SELF",
      subject_entity_id: "ENT-002",
      predicate: "communicated_with_itself",
      object_entity_id: "ENT-002",
      statement: "The host was reported as communicating with itself.",
      status: "suspected",
      confidence: "low",
      source_message_ids: ["message-1"],
    };

    const { container } = render(
      <CaseRelationshipGraph
        entities={entities}
        relationships={[selfRelationship]}
      />,
    );

    const edge = container.querySelector("[data-graph-edge-id='REL-SELF']");
    expect(edge).not.toBeNull();
    expect(edge?.outerHTML).not.toMatch(/NaN|Infinity/);
  });
});
