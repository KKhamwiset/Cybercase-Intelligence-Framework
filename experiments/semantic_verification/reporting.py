"""Deterministic report writing for benchmark construction results."""

import json
from pathlib import Path


def summary_markdown(summary):
    pair_counts = summary["pair_counts"]
    lines = [
        "# Offline Semantic Verification Benchmark Summary",
        "",
        "- Schema version: %s" % summary["schema_version"],
        "- Seed: %s" % summary["seed"],
        "- Cases: %d" % summary["case_count"],
        "- English cases: %d" % summary["language_counts"]["en"],
        "- Thai cases: %d" % summary["language_counts"]["th"],
        "- Verification pairs: %d" % pair_counts["total"],
        "- Supported pairs: %d" % pair_counts["positive"],
        "- Unsupported pairs: %d" % pair_counts["negative"],
        "- Positive gold-fact slot coverage: %.1f%%" % (summary["positive_slot_coverage"] * 100),
        "",
        "## Corruption counts",
        "",
    ]
    for error_type, count in summary["corruption_counts"].items():
        lines.append("- %s: %d" % (error_type, count))
    lines.extend(["", "## Scenario counts", ""])
    for scenario_id, count in summary["scenario_counts"].items():
        lines.append("- %s: %d" % (scenario_id, count))
    lines.extend(["", "## Narrative template counts", ""])
    for template_id, count in summary["template_counts"].items():
        lines.append("- %s: %d" % (template_id, count))
    lines.extend(["", "## Positive gold-fact slots covered", ""])
    lines.extend("- %s" % slot for slot in summary["positive_fact_slots_covered"])
    lines.extend(["", "## Integrity failures", ""])
    failures = summary["integrity_failures"]
    if failures:
        lines.extend("- %s" % failure for failure in failures)
    else:
        lines.append("- None")
    lines.extend(["", "## Limitations", ""])
    lines.extend("- %s" % limitation for limitation in summary["limitations"])
    lines.extend(
        [
            "",
            "This is a fixture-construction validator, not a semantic verifier and not a model-quality result.",
        ]
    )
    return "\n".join(lines)


def write_summary_reports(summary, json_path, markdown_path):
    json_destination = Path(json_path)
    markdown_destination = Path(markdown_path)
    json_destination.parent.mkdir(parents=True, exist_ok=True)
    markdown_destination.parent.mkdir(parents=True, exist_ok=True)
    json_destination.write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    markdown_destination.write_text(summary_markdown(summary) + "\n", encoding="utf-8", newline="\n")
