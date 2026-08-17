"""CLI entrypoint for the isolated offline benchmark."""

import argparse
import json
from pathlib import Path
import sys

from .constants import DEFAULT_CASE_COUNT, DEFAULT_SEED
from .generator import generate_cases, write_jsonl
from .reporting import write_summary_reports
from .validator import validate_dataset


PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_DATASET = PACKAGE_DIR / "data" / "semantic_verification.jsonl"
DEFAULT_SUMMARY_JSON = PACKAGE_DIR / "reports" / "summary.json"
DEFAULT_SUMMARY_MD = PACKAGE_DIR / "reports" / "summary.md"


def _parser():
    parser = argparse.ArgumentParser(description="Build or validate the offline synthetic benchmark.")
    commands = parser.add_subparsers(dest="command", required=True)

    generate = commands.add_parser("generate", help="generate JSONL and deterministic summary reports")
    generate.add_argument("--seed", type=int, default=DEFAULT_SEED)
    generate.add_argument("--cases", type=int, default=DEFAULT_CASE_COUNT)
    generate.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    generate.add_argument("--summary-json", type=Path, default=DEFAULT_SUMMARY_JSON)
    generate.add_argument("--summary-md", type=Path, default=DEFAULT_SUMMARY_MD)

    validate = commands.add_parser("validate", help="independently validate an existing JSONL dataset")
    validate.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    validate.add_argument("--non-strict", action="store_true", help="skip the 100-case/50-50 size requirement")
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    if args.command == "generate":
        cases = generate_cases(case_count=args.cases, seed=args.seed)
        write_jsonl(cases, args.dataset)
        summary = validate_dataset(args.dataset, strict=args.cases == DEFAULT_CASE_COUNT)
        write_summary_reports(summary, args.summary_json, args.summary_md)
    else:
        summary = validate_dataset(args.dataset, strict=not args.non_strict)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if summary["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
