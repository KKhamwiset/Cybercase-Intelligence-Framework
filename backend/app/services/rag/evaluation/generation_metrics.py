"""
Generation (Answer) Evaluation Metrics
========================================
Evaluates the quality of LLM-generated answers using:

1. RAGAS metrics (if installed):
   - Faithfulness: Is the answer grounded in the retrieved context?
   - Answer Relevancy: Does the answer address the question?

2. Fallback metrics (always available):
   - BERTScore: Semantic similarity to reference answer
   - ROUGE-L: Longest common subsequence overlap
   - Token F1: Token-level precision/recall vs reference

Requires: pip install ragas bert-score rouge-score datasets
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional, Callable

from .ground_truth import EvalSample


# ──────────────────────────────────────────────────────────────────────────────
# Fallback Metrics (no dependencies beyond stdlib)
# ──────────────────────────────────────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    """Simple whitespace + lowercase tokenizer."""
    return text.lower().split()


def token_f1(prediction: str, reference: str) -> dict[str, float]:
    """Token-level Precision, Recall, F1 between prediction and reference."""
    pred_tokens = set(_tokenize(prediction))
    ref_tokens = set(_tokenize(reference))

    if not pred_tokens or not ref_tokens:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    common = pred_tokens & ref_tokens
    precision = len(common) / len(pred_tokens)
    recall = len(common) / len(ref_tokens)

    if precision + recall == 0:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    f1 = 2 * precision * recall / (precision + recall)
    return {"precision": precision, "recall": recall, "f1": f1}


def rouge_l(prediction: str, reference: str) -> float:
    """ROUGE-L score (longest common subsequence)."""
    pred_tokens = _tokenize(prediction)
    ref_tokens = _tokenize(reference)

    if not pred_tokens or not ref_tokens:
        return 0.0

    # LCS via dynamic programming
    m, n = len(pred_tokens), len(ref_tokens)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if pred_tokens[i - 1] == ref_tokens[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

    lcs_len = dp[m][n]
    precision = lcs_len / m
    recall = lcs_len / n

    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


# ──────────────────────────────────────────────────────────────────────────────
# RAGAS Evaluation (optional dependency)
# ──────────────────────────────────────────────────────────────────────────────

def _try_ragas_evaluate(
    questions: list[str],
    answers: list[str],
    contexts: list[list[str]],
    reference_answers: list[str] | None = None,
) -> dict[str, list[float]] | None:
    """Attempt RAGAS evaluation. Returns None if ragas is not installed."""
    try:
        from ragas import evaluate
        from ragas.metrics import faithfulness, answer_relevancy
        from datasets import Dataset
    except ImportError:
        return None

    eval_data = {
        "question": questions,
        "answer": answers,
        "contexts": contexts,
    }

    metrics = [faithfulness, answer_relevancy]

    if reference_answers:
        eval_data["ground_truth"] = reference_answers
        try:
            from ragas.metrics import context_precision, context_recall, answer_correctness
            metrics.extend([context_precision, context_recall, answer_correctness])
        except ImportError:
            pass  # Older RAGAS version

    dataset = Dataset.from_dict(eval_data)

    try:
        result = evaluate(dataset, metrics=metrics)
        return result.to_pandas().to_dict(orient="list")
    except Exception as e:
        print(f"[EVAL] RAGAS evaluation failed: {e}")
        return None


def _try_bertscore(predictions: list[str], references: list[str]) -> list[float] | None:
    """Attempt BERTScore. Returns None if bert-score is not installed."""
    try:
        from bert_score import score
    except ImportError:
        return None

    try:
        P, R, F1 = score(predictions, references, lang="en", verbose=False)
        return F1.tolist()
    except Exception as e:
        print(f"[EVAL] BERTScore failed: {e}")
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Result Container
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class GenerationEvalResult:
    """Aggregated generation evaluation results."""
    num_samples: int = 0

    # RAGAS metrics (None if RAGAS not available)
    faithfulness: Optional[float] = None
    answer_relevancy: Optional[float] = None
    context_precision: Optional[float] = None
    context_recall: Optional[float] = None
    answer_correctness: Optional[float] = None

    # Fallback metrics
    avg_token_f1: float = 0.0
    avg_rouge_l: float = 0.0
    avg_bertscore: Optional[float] = None

    # Timing
    avg_latency_ms: float = 0.0

    # Detailed per-sample scores
    per_sample: list[dict] = field(default_factory=list)

    def to_table(self) -> str:
        """Format results as a printable table."""
        lines = [
            f"\n{'='*60}",
            f"  Generation Evaluation  ({self.num_samples} samples)",
            f"{'='*60}",
            f"  {'Metric':<30}{'Score':>10}",
            "  " + "─" * 40,
        ]

        if self.faithfulness is not None:
            lines.append(f"  {'Faithfulness (RAGAS)':<30}{self.faithfulness:>10.3f}")
        if self.answer_relevancy is not None:
            lines.append(f"  {'Answer Relevancy (RAGAS)':<30}{self.answer_relevancy:>10.3f}")
        if self.context_precision is not None:
            lines.append(f"  {'Context Precision (RAGAS)':<30}{self.context_precision:>10.3f}")
        if self.context_recall is not None:
            lines.append(f"  {'Context Recall (RAGAS)':<30}{self.context_recall:>10.3f}")
        if self.answer_correctness is not None:
            lines.append(f"  {'Answer Correctness (RAGAS)':<30}{self.answer_correctness:>10.3f}")

        lines.append("  " + "─" * 40)
        lines.append(f"  {'Token F1':<30}{self.avg_token_f1:>10.3f}")
        lines.append(f"  {'ROUGE-L':<30}{self.avg_rouge_l:>10.3f}")

        if self.avg_bertscore is not None:
            lines.append(f"  {'BERTScore F1':<30}{self.avg_bertscore:>10.3f}")

        lines.append(f"\n  {'Avg Latency (ms)':<30}{self.avg_latency_ms:>10.1f}")
        lines.append("")

        return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# Evaluation Orchestrator
# ──────────────────────────────────────────────────────────────────────────────

def evaluate_generation(
    query_fn: Callable[[str], tuple[str, list[str]]],
    samples: list[EvalSample],
) -> GenerationEvalResult:
    """Run generation evaluation across all samples.

    Args:
        query_fn: Callable(query: str) -> (answer: str, contexts: list[str])
            A function that takes a query and returns the generated answer
            plus the list of context chunks used for generation.
        samples: List of EvalSample (must have reference_answer for full eval).

    Returns:
        GenerationEvalResult with aggregated metrics.
    """
    result = GenerationEvalResult(num_samples=len(samples))

    questions = []
    answers = []
    contexts_list = []
    reference_answers = []
    latencies = []

    has_references = any(s.has_reference_answer() for s in samples)

    print(f"\n[EVAL] Running generation evaluation on {len(samples)} samples...")

    for i, sample in enumerate(samples):
        t0 = time.perf_counter()
        answer, contexts = query_fn(sample.query)
        latency_ms = (time.perf_counter() - t0) * 1000
        latencies.append(latency_ms)

        questions.append(sample.query)
        answers.append(answer)
        contexts_list.append(contexts)

        if sample.has_reference_answer():
            reference_answers.append(sample.reference_answer)
        else:
            reference_answers.append("")

        # Compute fallback metrics per sample
        sample_result = {"query": sample.query, "latency_ms": latency_ms}

        if sample.has_reference_answer():
            tf1 = token_f1(answer, sample.reference_answer)
            rl = rouge_l(answer, sample.reference_answer)
            sample_result["token_f1"] = tf1["f1"]
            sample_result["rouge_l"] = rl
        else:
            sample_result["token_f1"] = None
            sample_result["rouge_l"] = None

        result.per_sample.append(sample_result)

        print(f"  [{i+1}/{len(samples)}] latency={latency_ms:.0f}ms answer_len={len(answer)}")

    # ── Compute Aggregated Fallback Metrics ────────────────────────────────
    ref_samples = [
        (a, r) for a, r in zip(answers, reference_answers) if r.strip()
    ]

    if ref_samples:
        pred_with_ref = [a for a, _ in ref_samples]
        refs = [r for _, r in ref_samples]

        result.avg_token_f1 = sum(
            token_f1(a, r)["f1"] for a, r in ref_samples
        ) / len(ref_samples)

        result.avg_rouge_l = sum(
            rouge_l(a, r) for a, r in ref_samples
        ) / len(ref_samples)

        # Try BERTScore
        bert_scores = _try_bertscore(pred_with_ref, refs)
        if bert_scores:
            result.avg_bertscore = sum(bert_scores) / len(bert_scores)

    # ── Try RAGAS ──────────────────────────────────────────────────────────
    refs_for_ragas = reference_answers if has_references else None
    ragas_result = _try_ragas_evaluate(
        questions, answers, contexts_list, refs_for_ragas
    )

    if ragas_result:
        def _safe_mean(key):
            vals = ragas_result.get(key, [])
            valid = [v for v in vals if v is not None]
            return sum(valid) / len(valid) if valid else None

        result.faithfulness = _safe_mean("faithfulness")
        result.answer_relevancy = _safe_mean("answer_relevancy")
        result.context_precision = _safe_mean("context_precision")
        result.context_recall = _safe_mean("context_recall")
        result.answer_correctness = _safe_mean("answer_correctness")
    else:
        print("[EVAL] RAGAS not available — using fallback metrics only")
        print("[EVAL] Install with: pip install ragas datasets")

    # Latency
    result.avg_latency_ms = sum(latencies) / len(latencies) if latencies else 0.0

    return result
