"""
A/B Comparison — base qwen2.5:7b  vs  fine-tuned mitre-qwen:7b
=============================================================
Runs the EXISTING generation evaluation (evaluation/eval_runner.py) once per
model, switching models purely via the LOCAL_LLM_MODEL env var — no pipeline or
eval code is modified. Then it parses both reports into one side-by-side table.

Prerequisites (same as any generation eval):
  • Neo4j + Qdrant up (docker-compose up -d) and ingested
  • Ollama serving BOTH models:
        ollama list   # must show qwen2.5:7b AND mitre-qwen:7b

Usage (from the finetune/ directory):
    python compare/run_comparison.py
    python compare/run_comparison.py --max-samples 20
    python compare/run_comparison.py --dataset GraphRAG/evaluation/Thai_dataset.json
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

# UTF-8 stdout (report contains Δ / emoji) — matches eval_runner.py's Windows fix.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # finetune/
import ft_config as C  # noqa: E402

# Metrics we surface, in display order. Higher is better except latency.
METRIC_ORDER = [
    "Faithfulness (RAGAS)",
    "Answer Relevancy (RAGAS)",
    "Answer Correctness (RAGAS)",
    "Token F1",
    "ROUGE-L",
    "BERTScore F1",
    "Avg Latency (ms)",
]

_METRIC_RE = re.compile(r"^\s+(\S.*?\S)\s{2,}([\d]+\.[\d]+)\s*$")


def run_eval(model: str, dataset: str, max_samples: int, out_md: Path) -> None:
    env = os.environ.copy()
    env["LOCAL_LLM_MODEL"] = model
    cmd = [
        sys.executable, "-m", "GraphRAG.evaluation.eval_runner",
        "--dataset", dataset, "--mode", "generation", "--local",
        "--output", str(out_md),
    ]
    if max_samples:
        cmd += ["--max-samples", str(max_samples)]

    print(f"\n{'=' * 70}\n  EVAL  LOCAL_LLM_MODEL={model}\n{'=' * 70}")
    print("  cwd:", C.RAG_PKG_ROOT)
    print("  cmd:", " ".join(cmd))
    subprocess.run(cmd, cwd=str(C.RAG_PKG_ROOT), env=env, check=True)


def parse_metrics(md_path: Path) -> dict[str, float]:
    """Extract 'Metric -> value' pairs from the generation eval report."""
    metrics: dict[str, float] = {}
    if not md_path.exists():
        return metrics
    in_gen = False
    for line in md_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "Generation Evaluation" in line:
            in_gen = True
        if not in_gen:
            continue
        m = _METRIC_RE.match(line)
        if m:
            label, val = m.group(1).strip(), float(m.group(2))
            metrics[label] = val
    return metrics


def render(base_model, ft_model, base_m, ft_m) -> str:
    lines = [
        f"# Model Comparison — `{base_model}` vs `{ft_model}`",
        "",
        f"| Metric | {base_model} | {ft_model} | Δ (ft − base) |",
        "|---|---:|---:|---:|",
    ]
    for metric in METRIC_ORDER:
        if metric not in base_m and metric not in ft_m:
            continue
        b = base_m.get(metric)
        f = ft_m.get(metric)
        delta = ""
        if b is not None and f is not None:
            d = f - b
            arrow = "🔻" if (metric.startswith("Avg Latency") and d > 0) or \
                            (not metric.startswith("Avg Latency") and d < 0) else "🟢"
            delta = f"{d:+.3f} {arrow}"
        lines.append(
            f"| {metric} | {b if b is not None else '—'} "
            f"| {f if f is not None else '—'} | {delta} |"
        )
    lines += [
        "",
        "> 🟢 = fine-tuned is better, 🔻 = worse. For metrics other than latency, "
        "higher is better; for latency, lower is better.",
        "",
        "_Note: with the default dataset build (`--holdout none`), training and "
        "this eval may share entities, so treat this as an in-domain knowledge-"
        "absorption measure. For a leak-reduced test, rebuild with `--holdout ids`._",
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="A/B compare base vs fine-tuned model")
    ap.add_argument("--dataset", default="GraphRAG/evaluation/eval_dataset.json",
                    help="dataset path relative to rag_service/app/RAG")
    ap.add_argument("--base-model", default=C.BASE_MODEL_OLLAMA)
    ap.add_argument("--ft-model", default=C.FT_MODEL_OLLAMA)
    ap.add_argument("--max-samples", type=int, default=0)
    ap.add_argument("--skip-eval", action="store_true",
                    help="only re-parse existing reports (don't re-run the models)")
    args = ap.parse_args()

    out_dir = Path(__file__).resolve().parent
    base_md = out_dir / f"results_{args.base_model.replace(':', '_').replace('/', '_')}.md"
    ft_md = out_dir / f"results_{args.ft_model.replace(':', '_').replace('/', '_')}.md"

    if not args.skip_eval:
        run_eval(args.base_model, args.dataset, args.max_samples, base_md)
        run_eval(args.ft_model, args.dataset, args.max_samples, ft_md)

    base_m = parse_metrics(base_md)
    ft_m = parse_metrics(ft_md)

    report = render(args.base_model, args.ft_model, base_m, ft_m)
    comp_md = out_dir / f"comparison_{Path(args.dataset).stem}.md"
    comp_md.write_text(report, encoding="utf-8")

    print("\n" + report)
    print(f"\n[OK] comparison written -> {comp_md}")


if __name__ == "__main__":
    main()
