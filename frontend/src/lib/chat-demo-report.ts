import type {
  ChatDemoExtraction,
  PersistedChatMessage,
} from "@/lib/api";

export const CHAT_DEMO_REPORT_HEADINGS = [
  "1. Case Summary",
  "2. Found Indicators",
  "3. MITRE ATT&CK Mapping",
  "4. Mapping Rationale",
  "5. Evidence That Should Be Checked",
  "6. Preliminary Recommendations",
  "7. System Limitations",
] as const;

export type ChatDemoReportHeading = (typeof CHAT_DEMO_REPORT_HEADINGS)[number];

export interface ChatDemoReportSection {
  heading: ChatDemoReportHeading;
  paragraphs: string[];
  items: string[];
}

export interface ChatDemoReport {
  threadTitle: string;
  incomplete: boolean;
  sections: ChatDemoReportSection[];
}

const MITRE_TECHNIQUE_ID = /^T\d{4}(?:\.\d{3})?$/;

export function buildChatDemoReport(
  messages: PersistedChatMessage[],
  extraction: ChatDemoExtraction | null,
  threadTitle: string,
): ChatDemoReport {
  const orderedMessages = [...messages].sort(
    (left, right) =>
      left.ordinal - right.ordinal || left.id.localeCompare(right.id),
  );
  const selectedThreadTitle = threadTitle.trim() || "Untitled selected thread";
  const narrative = orderedMessages
    .filter((message) => message.role === "user")
    .map((message) => message.content.trim())
    .filter(Boolean);
  const mitreRows = persistedMitreRows(orderedMessages);
  const hasExtraction = extraction !== null;

  const evidenceItems = extraction
    ? extraction.evidence.map(
        (item) =>
          `Unverified evidence candidate ${item.evidence_id}: ${item.title} — ${item.description}`,
      )
    : [];
  const evidenceVerificationItems = extraction
    ? extraction.evidence.map(
        (item) =>
          `Original logs/files to verify: ${item.title} — ${item.description}`,
      )
    : [];
  const timelineItems = extraction
    ? extraction.timeline.map((item) => {
        const timestamp = item.timestamp ? ` (${item.timestamp})` : "";
        return `Unverified timeline candidate${timestamp}: ${item.event}`;
      })
    : [];

  return {
    threadTitle: selectedThreadTitle,
    incomplete: !hasExtraction,
    sections: [
      {
        heading: "1. Case Summary",
        paragraphs: [
          `Selected thread: ${selectedThreadTitle}`,
          "Case narrative source: user-authored messages from this selected thread only.",
          ...(narrative.length === 0
            ? ["No user-authored case narrative is present in the persisted messages."]
            : []),
        ],
        items: narrative,
      },
      {
        heading: "2. Found Indicators",
        paragraphs: [
          hasExtraction
            ? "Scope: the latest relevant persisted extraction for this selected thread. These are chat-text candidates and remain unverified."
            : "No latest relevant persisted extraction is available for this selected thread.",
        ],
        items:
          evidenceItems.length > 0
            ? evidenceItems
            : ["No persisted extraction evidence candidates are available."],
      },
      {
        heading: "3. MITRE ATT&CK Mapping",
        paragraphs: [
          mitreRows.length > 0
            ? "The candidates below come only from valid persisted metadata_json.mitre_table rows. No mapping is inferred from assistant prose."
            : "No valid persisted metadata_json.mitre_table rows are available. Assistant prose is not used to create mappings.",
        ],
        items:
          mitreRows.length > 0
            ? mitreRows.map(
                (row) =>
                  `Unverified persisted mapping candidate ${row.techniqueId}: ${row.name} — ${row.description}`,
              )
            : ["No valid persisted MITRE mapping candidates are available."],
      },
      {
        heading: "4. Mapping Rationale",
        paragraphs: [
          "Generic chat has no deterministic mapping rationale. Any MITRE mapping candidate requires analyst verification against the original narrative and source material.",
        ],
        items: [],
      },
      {
        heading: "5. Evidence That Should Be Checked",
        paragraphs: [
          hasExtraction
            ? "Check the original logs/files corresponding to the latest relevant persisted extraction. Timeline items are unverified candidate references; no evidence IDs are presented as verified citations."
            : "No latest relevant persisted extraction is available. Original logs/files and timeline facts must be supplied and verified by an analyst.",
        ],
        items:
          evidenceVerificationItems.length > 0 || timelineItems.length > 0
            ? [...evidenceVerificationItems, ...timelineItems]
            : ["No persisted evidence or timeline candidates are available to check."],
      },
      {
        heading: "6. Preliminary Recommendations",
        paragraphs: [
          "These are conservative analyst-review actions, not confirmed findings or automated response instructions.",
        ],
        items: [
          "Preserve the original logs and files, including source timestamps, timezone, and available integrity metadata.",
          "Validate each indicator against trusted endpoint, identity, network, and email telemetry before drawing conclusions.",
          "Review any MITRE candidate against the verified activity and record the supporting source span before accepting it.",
          "Document missing context and avoid attribution or containment decisions based on this chat-only demo report.",
        ],
      },
      {
        heading: "7. System Limitations",
        paragraphs: [
          "This is a Demo only / Unverified report generated from chat text, with low confidence.",
        ],
        items: [
          "The report is chat-text-only and uses the selected thread's persisted messages plus the latest relevant persisted extraction.",
          "The demo output is non-persistent and is not saved as a case report.",
          "Generic chat has no case ID or report session; this demo does not derive either and does not use case-report endpoints.",
          "Chat content and candidate references are not verified links to original logs or files; timeline references remain unverified candidates.",
        ],
      },
    ],
  };
}

interface PersistedMitreRow {
  techniqueId: string;
  name: string;
  description: string;
}

function persistedMitreRows(
  messages: PersistedChatMessage[],
): PersistedMitreRow[] {
  const rows: PersistedMitreRow[] = [];
  const seenIds = new Set<string>();

  for (const message of messages) {
    if (message.role !== "assistant") continue;
    const rawRows = message.metadata_json.mitre_table;
    if (!Array.isArray(rawRows)) continue;

    for (const rawRow of rawRows) {
      if (!isRecord(rawRow)) continue;
      const techniqueId = readTrimmedString(rawRow.technique_id);
      const name = readTrimmedString(rawRow.name);
      const description = readTrimmedString(rawRow.description);
      if (
        techniqueId === null ||
        name === null ||
        description === null ||
        !MITRE_TECHNIQUE_ID.test(techniqueId) ||
        seenIds.has(techniqueId)
      ) {
        continue;
      }

      seenIds.add(techniqueId);
      rows.push({ techniqueId, name, description });
    }
  }

  return rows;
}

function readTrimmedString(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
