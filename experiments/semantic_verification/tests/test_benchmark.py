"""Offline integrity and tamper tests for the proposition-backed benchmark."""

import ast
import json
from pathlib import Path
import tempfile
import unittest

from experiments.semantic_verification.constants import CORRUPTION_TYPES, DEFAULT_CASE_COUNT, LEAK_MARKERS
from experiments.semantic_verification.generator import generate_cases, write_jsonl
from experiments.semantic_verification.rendering import render_fact
from experiments.semantic_verification.reporting import write_summary_reports
from experiments.semantic_verification.validator import _sentence_count, validate_dataset


PACKAGE_DIR = Path(__file__).resolve().parents[1]


def _validate_rows(rows, strict=False):
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "dataset.jsonl"
        write_jsonl(rows, path)
        return validate_dataset(path, strict=strict)


class SemanticVerificationTests(unittest.TestCase):
    def test_exact_counts_diversity_and_coverage(self):
        cases = generate_cases()
        summary = _validate_rows(cases, strict=True)
        self.assertTrue(summary["valid"], summary["integrity_failures"])
        self.assertEqual(len(cases), DEFAULT_CASE_COUNT)
        self.assertEqual(summary["language_counts"], {"en": 50, "th": 50})
        self.assertEqual(summary["pair_counts"], {"total": 800, "positive": 400, "negative": 400})
        self.assertEqual(summary["corruption_counts"], {error_type: 50 for error_type in CORRUPTION_TYPES})
        self.assertEqual(summary["positive_slot_coverage"], 1.0)
        self.assertEqual(len(summary["scenario_counts"]), 4)
        self.assertEqual(len(summary["template_counts"]), 8)
        self.assertTrue(all(3 <= _sentence_count(case["narrative"]) <= 8 for case in cases))
        self.assertTrue(any(fact["timestamp"] is None for case in cases for fact in case["gold_facts"]["timeline"]))
        self.assertTrue(any(fact["certainty"] == "suspected" for case in cases for fact in case["gold_facts"]["relationships"]))
        self.assertTrue(any(fact["negated"] for case in cases for fact in case["gold_facts"]["relationships"]))
        self.assertTrue(any("it " in case["narrative"] for case in cases if case["language"] == "en"))
        self.assertTrue(any("สิ่งดังกล่าว" in case["narrative"] for case in cases if case["language"] == "th"))

    def test_repeatability_including_reports(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = [root / name for name in ("a.jsonl", "b.jsonl", "a.json", "b.json", "a.md", "b.md")]
            write_jsonl(generate_cases(), paths[0])
            write_jsonl(generate_cases(), paths[1])
            first, second = validate_dataset(paths[0]), validate_dataset(paths[1])
            write_summary_reports(first, paths[2], paths[4])
            write_summary_reports(second, paths[3], paths[5])
            self.assertEqual(paths[0].read_bytes(), paths[1].read_bytes())
            self.assertEqual(paths[2].read_bytes(), paths[3].read_bytes())
            self.assertEqual(paths[4].read_bytes(), paths[5].read_bytes())

    def test_claims_have_no_label_markers(self):
        for case in generate_cases():
            for pair in case["verification_pairs"]:
                lowered = pair["claim"].casefold()
                self.assertFalse(any(marker in lowered for marker in LEAK_MARKERS), pair["claim"])

    def test_narrative_tamper_is_rejected(self):
        rows = generate_cases(case_count=2)
        rows[0]["narrative"] = rows[0]["narrative"].replace("owned", "reviewed", 1)
        summary = _validate_rows(rows)
        self.assertFalse(summary["valid"])
        self.assertTrue(any("narrative does not equal" in failure for failure in summary["integrity_failures"]))

    def test_absent_entity_and_timestamp_are_rejected(self):
        rows = generate_cases(case_count=2)
        case = rows[0]
        entity = case["gold_facts"]["entities"][0]
        entity["name"] += "-changed"
        summary = _validate_rows(rows)
        self.assertFalse(summary["valid"])
        self.assertTrue(any("absent from source proposition" in failure for failure in summary["integrity_failures"]))

        rows = generate_cases(case_count=2)
        fact = next(f for f in rows[0]["gold_facts"]["relationships"] if f["timestamp"])
        proposition = next(p for p in rows[0]["narrative_propositions"] if fact["fact_id"] in p["fact_ids"])
        proposition["text"] = proposition["text"].replace(" at " + fact["timestamp"], "")
        rows[0]["narrative"] = " ".join(p["text"] for p in rows[0]["narrative_propositions"])
        summary = _validate_rows(rows)
        self.assertFalse(summary["valid"])
        self.assertTrue(any("timestamp is absent" in failure for failure in summary["integrity_failures"]))

    def test_positive_and_trivial_negative_tamper_are_rejected(self):
        rows = generate_cases(case_count=2)
        rows[0]["verification_pairs"][0]["claim"] += " altered"
        summary = _validate_rows(rows)
        self.assertFalse(summary["valid"])
        self.assertTrue(any("positive claim is not entailed" in failure for failure in summary["integrity_failures"]))

        rows = generate_cases(case_count=2)
        case = rows[0]
        pair = case["verification_pairs"][4]
        facts = {f["fact_id"]: f for f in case["gold_facts"]["relationships"] + case["gold_facts"]["timeline"]}
        pair["claim"] = render_fact(facts[pair["source_fact_ids"][0]], case["language"], case["gold_facts"])
        summary = _validate_rows(rows)
        self.assertFalse(summary["valid"])
        self.assertTrue(any("identical or trivially equivalent" in failure for failure in summary["integrity_failures"]))

    def test_timeline_edge_without_relationship_is_rejected(self):
        rows = generate_cases(case_count=2)
        rows[0]["gold_facts"]["relationships"] = [f for f in rows[0]["gold_facts"]["relationships"] if f["slot"] != "rel-007"]
        summary = _validate_rows(rows)
        self.assertFalse(summary["valid"])
        self.assertTrue(any("lacks its explicit gold relationship" in failure for failure in summary["integrity_failures"]))

    def test_malformed_blank_and_duplicate_json_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name, text, needle in (
                ("blank.jsonl", "{}\n\n", "blank"),
                ("nan.jsonl", '{"case_id": NaN}\n', "malformed JSON"),
                ("duplicate.jsonl", '{"case_id":"a","case_id":"b"}\n', "duplicate JSON key"),
            ):
                path = root / name
                path.write_text(text, encoding="utf-8")
                summary = validate_dataset(path, strict=False)
                self.assertFalse(summary["valid"])
                self.assertTrue(any(needle in failure for failure in summary["integrity_failures"]))

    def test_import_and_network_isolation(self):
        allowed = {"argparse", "ast", "copy", "datetime", "json", "pathlib", "re", "sys"}
        for source_path in PACKAGE_DIR.glob("*.py"):
            tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertIn(alias.name.split(".")[0], allowed, source_path.name)
                elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                    self.assertIn(node.module.split(".")[0], allowed | {"experiments"}, source_path.name)


if __name__ == "__main__":
    unittest.main()
