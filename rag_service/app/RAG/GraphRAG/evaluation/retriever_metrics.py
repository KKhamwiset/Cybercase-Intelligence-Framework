"""
Retriever Evaluation Metrics
==============================
Pure functions for evaluating retrieval quality.

Metrics:
  - Hit@K          : Did any relevant doc appear in top-K?
  - Recall@K       : Capped recall — hits / min(|relevant|, K)
  - Precision@K    : Fraction of top-K that are relevant
  - MRR            : Mean Reciprocal Rank of first relevant result
  - NDCG@K         : Normalized Discounted Cumulative Gain
  - MAP            : Mean Average Precision

Step-coverage metrics (for chronological incident samples where ground
truth is an ordered list of attack steps, each with its own gold IDs):
  - StepCoverage@K : Fraction of steps with >=1 gold ID in top-K.
                     This is subtopic recall (S-recall@K, Zhai et al.,
                     SIGIR 2003) with attack steps as subtopics.
  - StrictStepCoverage@K : Fraction of steps with ALL gold IDs in top-K.
  - step_best_rank : Rank of the first retrieved ID belonging to a step.

All flat metric functions accept:
  - retrieved_ids : list[str] — ordered list of retrieved STIX IDs
  - relevant_ids  : set[str]  — set of ground-truth relevant STIX IDs

Step metrics accept steps as list[dict] with keys:
  - gold_ids : list[str] | set[str] — IDs that evidence this step
  - cue_type : str (optional)       — "named" | "described"
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Optional

from .ground_truth import EvalSample


# ──────────────────────────────────────────────────────────────────────────────
# Individual Metric Functions
# ──────────────────────────────────────────────────────────────────────────────

def hit_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """1.0 if any relevant doc appears in top-K, else 0.0."""
    top_k = retrieved_ids[:k]
    return 1.0 if any(rid in relevant_ids for rid in top_k) else 0.0


def recall_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """Capped recall: hits / min(|relevant|, K).

    A plain hits/|relevant| denominator makes the score mathematically
    capped at K/|relevant| for enumeration-style samples (e.g. a tactic
    with 180 gold techniques at K=10 can never exceed 0.056 even for a
    perfect retriever). Capping the denominator at K asks the answerable
    question instead: of the K slots available, how many were filled
    with relevant results. Samples with |relevant| <= K are unaffected.
    """
    if not relevant_ids or k <= 0:
        return 0.0
    top_k = set(retrieved_ids[:k])
    return len(top_k & relevant_ids) / min(len(relevant_ids), k)


def precision_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """Fraction of top-K results that are relevant."""
    top_k = retrieved_ids[:k]
    if not top_k:
        return 0.0
    return sum(1 for rid in top_k if rid in relevant_ids) / len(top_k)


def reciprocal_rank(retrieved_ids: list[str], relevant_ids: set[str]) -> float:
    """Reciprocal rank of the first relevant result (1/rank)."""
    for i, rid in enumerate(retrieved_ids, 1):
        if rid in relevant_ids:
            return 1.0 / i
    return 0.0


def ndcg_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """Normalized Discounted Cumulative Gain at K (binary relevance)."""
    top_k = retrieved_ids[:k]

    # DCG
    dcg = 0.0
    for i, rid in enumerate(top_k, 1):
        if rid in relevant_ids:
            dcg += 1.0 / math.log2(i + 1)

    # Ideal DCG — all relevant docs ranked first
    ideal_count = min(len(relevant_ids), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_count + 1))

    if idcg == 0:
        return 0.0
    return dcg / idcg


def average_precision(retrieved_ids: list[str], relevant_ids: set[str]) -> float:
    """Average Precision — average of Precision@k at each relevant position."""
    if not relevant_ids:
        return 0.0

    hits = 0
    sum_precision = 0.0

    for i, rid in enumerate(retrieved_ids, 1):
        if rid in relevant_ids:
            hits += 1
            sum_precision += hits / i

    if hits == 0:
        return 0.0
    return sum_precision / len(relevant_ids)


# ──────────────────────────────────────────────────────────────────────────────
# Step-Coverage Metrics (chronological incident samples)
# ──────────────────────────────────────────────────────────────────────────────
#
# Incident samples model the ground truth as an ordered list of attack
# steps (e.g. SQL injection -> privilege escalation -> data destruction),
# each step carrying the gold IDs that evidence it. Flat recall over the
# union of IDs hides which step the retriever missed; these metrics score
# coverage per step. StepCoverage@K is subtopic recall (S-recall@K,
# Zhai, Cohen & Lafferty, SIGIR 2003) with attack steps as subtopics.

def _step_gold_ids(step: dict) -> set[str]:
    return set(step.get("gold_ids") or [])


def step_coverage_at_k(retrieved_ids: list[str], steps: list[dict], k: int) -> float:
    """Fraction of steps with at least one gold ID in top-K (S-recall@K)."""
    if not steps or k <= 0:
        return 0.0
    top_k = set(retrieved_ids[:k])
    covered = sum(1 for step in steps if top_k & _step_gold_ids(step))
    return covered / len(steps)


def strict_step_coverage_at_k(retrieved_ids: list[str], steps: list[dict], k: int) -> float:
    """Fraction of steps whose gold IDs ALL appear in top-K."""
    if not steps or k <= 0:
        return 0.0
    top_k = set(retrieved_ids[:k])
    covered = sum(
        1 for step in steps
        if _step_gold_ids(step) and _step_gold_ids(step) <= top_k
    )
    return covered / len(steps)


def step_best_rank(retrieved_ids: list[str], step: dict) -> Optional[int]:
    """1-based rank of the first retrieved ID evidencing the step, else None.

    Diagnostic companion to step_coverage_at_k: a step that is covered at
    K=20 but not K=5 is a ranking problem (reranker), not a search problem.
    """
    gold = _step_gold_ids(step)
    for i, rid in enumerate(retrieved_ids, 1):
        if rid in gold:
            return i
    return None


def step_coverage_by_cue_type(
    retrieved_ids: list[str], steps: list[dict], k: int
) -> dict[str, float]:
    """StepCoverage@K broken down by cue_type ("named" vs "described").

    Named cues (technique explicitly written in the case narrative) test
    keyword matching; described cues (behaviour only) test whether the
    pipeline maps behaviour to techniques — the two must be reported
    separately or named-cue scores mask described-cue failures.
    Steps without a cue_type are grouped under "unspecified".
    """
    by_type: dict[str, list[dict]] = {}
    for step in steps:
        by_type.setdefault(step.get("cue_type") or "unspecified", []).append(step)
    return {
        cue_type: step_coverage_at_k(retrieved_ids, type_steps, k)
        for cue_type, type_steps in by_type.items()
    }


# ──────────────────────────────────────────────────────────────────────────────
# Result Container
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class RetrieverEvalResult:
    """Aggregated retriever evaluation results."""
    retriever_name: str
    num_samples: int = 0
    k_values: list[int] = field(default_factory=lambda: [1, 3, 5, 10])

    # Per-K metrics (keyed by K value)
    hit_at_k: dict[int, float] = field(default_factory=dict)
    recall_at_k: dict[int, float] = field(default_factory=dict)
    precision_at_k: dict[int, float] = field(default_factory=dict)
    ndcg_at_k: dict[int, float] = field(default_factory=dict)

    # Scalar metrics
    mrr: float = 0.0
    map_score: float = 0.0

    # Timing
    avg_latency_ms: float = 0.0

    def to_table(self) -> str:
        """Format results as a printable table."""
        lines = [
            f"\n{'='*60}",
            f"  Retriever: {self.retriever_name}  ({self.num_samples} samples)",
            f"{'='*60}",
        ]

        # Per-K metrics table
        header = f"  {'Metric':<20}"
        for k in self.k_values:
            header += f"{'@'+str(k):>8}"
        lines.append(header)
        lines.append("  " + "─" * (20 + 8 * len(self.k_values)))

        for metric_name, metric_dict in [
            ("Hit", self.hit_at_k),
            ("Recall (capped)", self.recall_at_k),
            ("Precision", self.precision_at_k),
            ("NDCG", self.ndcg_at_k),
        ]:
            row = f"  {metric_name:<20}"
            for k in self.k_values:
                val = metric_dict.get(k, 0.0)
                row += f"{val:>8.3f}"
            lines.append(row)

        # Scalar metrics
        lines.append(f"\n  {'MRR':<20}{self.mrr:>8.3f}")
        lines.append(f"  {'MAP':<20}{self.map_score:>8.3f}")
        lines.append(f"  {'Avg Latency (ms)':<20}{self.avg_latency_ms:>8.1f}")
        lines.append("")

        return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# Evaluation Orchestrator
# ──────────────────────────────────────────────────────────────────────────────

def evaluate_retriever(
    retriever_fn,
    samples: list[EvalSample],
    k_values: list[int] | None = None,
    retriever_name: str = "Retriever",
) -> RetrieverEvalResult:
    """Run retriever evaluation across all samples.

    Args:
        retriever_fn: Callable(query: str) -> list[str]
            A function that takes a query string and returns an ordered list
            of retrieved STIX IDs (most relevant first).
        samples: List of EvalSample with ground-truth relevant_stix_ids.
        k_values: List of K values to compute metrics at. Default: [1, 3, 5, 10].
        retriever_name: Display name for the retriever.

    Returns:
        RetrieverEvalResult with aggregated metrics.
    """
    if k_values is None:
        k_values = [1, 3, 5, 10]

    result = RetrieverEvalResult(
        retriever_name=retriever_name,
        num_samples=len(samples),
        k_values=k_values,
    )

    # Accumulators
    all_rr = []
    all_ap = []
    all_latencies = []
    per_k_hits = {k: [] for k in k_values}
    per_k_recall = {k: [] for k in k_values}
    per_k_precision = {k: [] for k in k_values}
    per_k_ndcg = {k: [] for k in k_values}

    for i, sample in enumerate(samples):
        relevant = set(sample.relevant_stix_ids)

        # Time the retrieval
        t0 = time.perf_counter()
        retrieved = retriever_fn(sample.query)
        latency_ms = (time.perf_counter() - t0) * 1000
        all_latencies.append(latency_ms)

        print(
            f"  [{i+1}/{len(samples)}] "
            f"retrieved={len(retrieved)} relevant={len(relevant)} "
            f"latency={latency_ms:.0f}ms"
        )

        # Compute per-K metrics
        for k in k_values:
            per_k_hits[k].append(hit_at_k(retrieved, relevant, k))
            per_k_recall[k].append(recall_at_k(retrieved, relevant, k))
            per_k_precision[k].append(precision_at_k(retrieved, relevant, k))
            per_k_ndcg[k].append(ndcg_at_k(retrieved, relevant, k))

        # Scalar metrics
        all_rr.append(reciprocal_rank(retrieved, relevant))
        all_ap.append(average_precision(retrieved, relevant))

    # Aggregate (mean over all samples)
    def mean(lst):
        return sum(lst) / len(lst) if lst else 0.0

    for k in k_values:
        result.hit_at_k[k] = mean(per_k_hits[k])
        result.recall_at_k[k] = mean(per_k_recall[k])
        result.precision_at_k[k] = mean(per_k_precision[k])
        result.ndcg_at_k[k] = mean(per_k_ndcg[k])

    result.mrr = mean(all_rr)
    result.map_score = mean(all_ap)
    result.avg_latency_ms = mean(all_latencies)

    return result
