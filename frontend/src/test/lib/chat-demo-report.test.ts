import { describe, expect, it } from "vitest";
import type {
  ChatDemoExtraction,
  PersistedChatMessage,
} from "@/lib/api";
import {
  buildChatDemoReport,
  CHAT_DEMO_REPORT_HEADINGS,
} from "@/lib/chat-demo-report";

function message(
  role: PersistedChatMessage["role"],
  ordinal: number,
  content: string,
  metadata_json: Record<string, unknown> = {},
  thread_id = "thread-1",
): PersistedChatMessage {
  return {
    id: `${thread_id}-message-${ordinal}`,
    thread_id,
    ordinal,
    role,
    content,
    retrieval_context_id: null,
    metadata_json,
    created_at: `2026-08-01T12:00:${String(ordinal).padStart(2, "0")}Z`,
  };
}

const extraction: ChatDemoExtraction = {
  version: 1,
  mode: "deterministic_demo",
  status: "candidate",
  disclaimer: "Verify demo candidates.",
  evidence: [
    {
      evidence_id: "E-001",
      title: "Endpoint event log",
      description: "A suspicious process was recorded.",
      status: "reported",
      confidence: "low",
      source_type: "chat_text",
    },
  ],
  timeline: [
    {
      event_id: "T-001",
      timestamp: "12:30",
      event: "The suspicious process was observed.",
      status: "reported",
      evidence_ids: ["E-001"],
      source_type: "chat_text",
    },
  ],
};

describe("buildChatDemoReport", () => {
  it("returns the exact seven historical sections in deterministic order", () => {
    const messages = [
      message("assistant", 3, "Assistant prose mentions T9999 but is not metadata.", {
        mitre_table: [
          {
            technique_id: "T1566",
            name: "Phishing",
            description: "A valid persisted mapping row.",
          },
        ],
      }),
      message("user", 2, "Second user-authored detail."),
      message("user", 1, "First user-authored narrative."),
    ];

    const report = buildChatDemoReport(messages, extraction, "Selected thread");

    expect(report.sections.map((section) => section.heading)).toEqual(
      CHAT_DEMO_REPORT_HEADINGS,
    );
    expect(report).toEqual(
      buildChatDemoReport(messages, extraction, "Selected thread"),
    );
    expect(report.sections[0].items).toEqual([
      "First user-authored narrative.",
      "Second user-authored detail.",
    ]);
    expect(report.sections[2].items).toEqual([
      "Unverified persisted mapping candidate T1566: Phishing — A valid persisted mapping row.",
    ]);
    expect(report.sections[2].items.join(" ")).not.toContain("T9999");
  });

  it("filters malformed and invalid persisted MITRE rows", () => {
    const messages = [
      message("assistant", 1, "Terminal answer", {
        mitre_table: [
          {
            technique_id: "T1566",
            name: "Phishing",
            description: "Valid row.",
          },
          {
            technique_id: "T1566.001",
            name: "Spearphishing Attachment",
            description: "Valid sub-technique row.",
          },
          { technique_id: "T1566", name: "Duplicate", description: "Ignore duplicate." },
          { technique_id: "T12", name: "Too short", description: "Invalid ID." },
          { technique_id: "T1566.0001", name: "Too long", description: "Invalid ID." },
          { technique_id: "T1110", name: "Missing description" },
          { technique_id: "T1059", name: 42, description: "Invalid name." },
          { technique_id: "not-an-id", name: "Invalid", description: "Invalid ID." },
        ],
      }),
    ];

    const mappingItems = buildChatDemoReport(
      messages,
      extraction,
      "Selected thread",
    ).sections[2].items;

    expect(mappingItems).toHaveLength(2);
    expect(mappingItems.join(" ")).toContain("T1566");
    expect(mappingItems.join(" ")).toContain("T1566.001");
    expect(mappingItems.join(" ")).not.toContain("T12");
    expect(mappingItems.join(" ")).not.toContain("T1059");
  });

  it("labels timeline candidates without rendering their evidence IDs as citations", () => {
    const evidenceSection = buildChatDemoReport(
      [message("user", 1, "Investigate the reported event.")],
      extraction,
      "Selected thread",
    ).sections[4];

    expect(evidenceSection.items.join(" ")).toContain(
      "Unverified timeline candidate (12:30)",
    );
    expect(evidenceSection.items.join(" ")).not.toContain("E-001");
    expect(evidenceSection.items.join(" ")).not.toContain("T-001");
  });

  it("marks reports without extraction incomplete and uses explicit placeholders", () => {
    const report = buildChatDemoReport(
      [
        message("user", 1, "A user-authored narrative."),
        message("assistant", 2, "Assistant prose should not become a mapping."),
      ],
      null,
      "Selected thread",
    );

    expect(report.incomplete).toBe(true);
    expect(report.sections[1].items).toEqual([
      "No persisted extraction evidence candidates are available.",
    ]);
    expect(report.sections[4].items).toEqual([
      "No persisted evidence or timeline candidates are available to check.",
    ]);
    expect(report.sections[2].items).toEqual([
      "No valid persisted MITRE mapping candidates are available.",
    ]);
  });

  it("uses only the messages supplied for the selected thread narrative", () => {
    const selectedThreadMessages = [
      message("user", 1, "Selected thread narrative.", {}, "selected-thread"),
    ];
    const report = buildChatDemoReport(
      selectedThreadMessages,
      null,
      "Selected thread",
    );

    expect(report.sections[0].items).toEqual(["Selected thread narrative."]);
    expect(report.sections[0].items.join(" ")).not.toContain("other-thread");
  });

  it("handles an empty thread and preserves unusual text as plain report data", () => {
    const emptyReport = buildChatDemoReport([], null, "");
    expect(emptyReport.incomplete).toBe(true);
    expect(emptyReport.threadTitle).toBe("Untitled selected thread");
    expect(emptyReport.sections[0].items).toEqual([]);
    expect(emptyReport.sections[0].paragraphs).toContain(
      "No user-authored case narrative is present in the persisted messages.",
    );

    const unusualText = `<script>alert(1)</script> 日本語 ${"long-value ".repeat(200)}`;
    const report = buildChatDemoReport(
      [message("user", 1, unusualText)],
      null,
      "Unicode thread",
    );

    expect(report.sections[0].items).toEqual([unusualText.trim()]);
  });
});
