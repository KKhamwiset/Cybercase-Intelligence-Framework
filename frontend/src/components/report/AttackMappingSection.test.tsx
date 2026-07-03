import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import AttackMappingSection from "./AttackMappingSection";
import type { ReportSection } from "@/lib/reports";

const section: ReportSection = {
  id: "mitre_attack_mapping",
  title: "MITRE ATT&CK Mapping",
  required: true,
  status: "partial",
  source_fact_ids: ["M-001"],
  content: {
    tactics: [
      {
        tactic: "Initial Access",
        mappings: [
          {
            mapping_id: "M-001",
            technique_id: "T1566",
            technique_name: "Phishing",
            rationale: "",
            status: "candidate",
            confidence: "medium",
            evidence_ids: [],
            analyst_verified: false,
            source_type: "rag",
          },
        ],
      },
    ],
  },
};

describe("AttackMappingSection", () => {
  it("labels candidate mappings as requiring analyst validation", () => {
    render(<AttackMappingSection section={section} />);

    expect(screen.getByText("Candidate")).toBeInTheDocument();
    expect(screen.getByText("Analyst validation required")).toBeInTheDocument();
  });
});
