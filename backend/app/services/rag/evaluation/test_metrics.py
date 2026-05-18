"""
Unit Tests for Evaluation Metrics
====================================
Tests metric functions with known inputs/outputs.
Runs without any database or model dependencies.

Usage:
    cd d:\\Doc\\TSR_Mitre\\RAG\\GraphRAG
    python evaluation/test_metrics.py
"""

import sys
from pathlib import Path

# Add parent directory for imports
_SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from app.services.rag.evaluation.retriever_metrics import (
    hit_at_k,
    recall_at_k,
    precision_at_k,
    reciprocal_rank,
    ndcg_at_k,
    average_precision,
)
from app.services.rag.evaluation.generation_metrics import token_f1, rouge_l
from app.services.rag.evaluation.ground_truth import EvalSample, save_ground_truth, load_ground_truth

import json
import tempfile
import os


def test_hit_at_k():
    retrieved = ["a", "b", "c", "d", "e"]
    relevant = {"c", "f"}

    assert hit_at_k(retrieved, relevant, k=1) == 0.0, "c is not in top-1"
    assert hit_at_k(retrieved, relevant, k=2) == 0.0, "c is not in top-2"
    assert hit_at_k(retrieved, relevant, k=3) == 1.0, "c IS in top-3"
    assert hit_at_k(retrieved, relevant, k=5) == 1.0, "c IS in top-5"
    assert hit_at_k(retrieved, set(), k=5) == 0.0
    print("  [PASS] hit_at_k")


def test_recall_at_k():
    retrieved = ["a", "b", "c", "d", "e"]
    relevant = {"a", "c", "f"}

    assert recall_at_k(retrieved, relevant, k=1) == 1/3
    assert recall_at_k(retrieved, relevant, k=3) == 2/3
    assert recall_at_k(retrieved, relevant, k=5) == 2/3
    assert recall_at_k(retrieved, set(), k=5) == 0.0
    print("  [PASS] recall_at_k")


def test_precision_at_k():
    retrieved = ["a", "b", "c", "d", "e"]
    relevant = {"a", "c"}

    assert precision_at_k(retrieved, relevant, k=1) == 1.0
    assert precision_at_k(retrieved, relevant, k=2) == 0.5
    assert precision_at_k(retrieved, relevant, k=5) == 0.4
    print("  [PASS] precision_at_k")


def test_reciprocal_rank():
    relevant = {"c", "f"}

    assert reciprocal_rank(["c", "b", "a"], relevant) == 1.0
    assert reciprocal_rank(["a", "c", "b"], relevant) == 0.5
    assert reciprocal_rank(["a", "b", "c"], relevant) == 1/3
    assert reciprocal_rank(["a", "b", "d"], relevant) == 0.0
    print("  [PASS] reciprocal_rank (MRR)")


def test_ndcg_at_k():
    retrieved = ["a", "b", "c", "d", "e"]
    relevant = {"a", "c"}

    perfect = ["a", "c", "b", "d", "e"]
    assert ndcg_at_k(perfect, relevant, k=5) == 1.0
    assert ndcg_at_k(["x", "y", "z"], relevant, k=3) == 0.0

    score = ndcg_at_k(retrieved, relevant, k=5)
    assert 0.0 < score < 1.0, f"partial ranking should be 0<x<1, got {score}"
    print("  [PASS] ndcg_at_k")


def test_average_precision():
    relevant = {"a", "c", "e"}

    perfect = ["a", "c", "e", "b", "d"]
    ap = average_precision(perfect, relevant)
    assert abs(ap - 1.0) < 1e-6, f"perfect AP should be 1.0, got {ap}"

    mixed = ["a", "b", "c", "d", "e"]
    ap = average_precision(mixed, relevant)
    expected = (1.0 + 2/3 + 3/5) / 3
    assert abs(ap - expected) < 1e-6, f"expected {expected}, got {ap}"
    assert average_precision(mixed, set()) == 0.0
    print("  [PASS] average_precision (MAP)")


def test_token_f1():
    assert token_f1("hello world", "hello world")["f1"] == 1.0
    assert token_f1("foo bar", "baz qux")["f1"] == 0.0
    assert 0.0 < token_f1("the cat sat", "the dog sat on mat")["f1"] < 1.0
    assert token_f1("", "hello")["f1"] == 0.0
    print("  [PASS] token_f1")


def test_rouge_l():
    assert rouge_l("hello world foo", "hello world foo") == 1.0
    assert rouge_l("aaa bbb", "ccc ddd") == 0.0
    assert 0.0 < rouge_l("the cat sat on the mat", "the cat on the mat sat") < 1.0
    assert rouge_l("", "hello") == 0.0
    print("  [PASS] rouge_l")


def test_ground_truth_io():
    samples = [
        EvalSample(
            query="What is Phishing?",
            relevant_stix_ids=["attack-pattern--a62a8db3"],
            reference_answer="Phishing is...",
            language="en",
            category="technique_lookup",
        ),
        EvalSample(
            query="What is T1059?",
            relevant_stix_ids=["attack-pattern--a62a8db3"],
            language="en",
        ),
    ]

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        tmp_path = f.name

    try:
        save_ground_truth(samples, tmp_path)
        loaded = load_ground_truth(tmp_path)

        assert len(loaded) == 2
        assert loaded[0].query == "What is Phishing?"
        assert loaded[0].relevant_stix_ids == ["attack-pattern--a62a8db3"]
        assert loaded[0].has_reference_answer() is True
        assert loaded[1].has_reference_answer() is False
    finally:
        os.unlink(tmp_path)

    print("  [PASS] ground_truth save/load")


def run_all_tests():
    print("\n" + "=" * 50)
    print("  RAG Evaluation -- Unit Tests")
    print("=" * 50 + "\n")

    tests = [
        test_hit_at_k,
        test_recall_at_k,
        test_precision_at_k,
        test_reciprocal_rank,
        test_ndcg_at_k,
        test_average_precision,
        test_token_f1,
        test_rouge_l,
        test_ground_truth_io,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  [FAIL] {test.__name__}: unexpected error: {e}")
            failed += 1

    print(f"\n  Results: {passed} passed, {failed} failed, {passed + failed} total")

    if failed > 0:
        sys.exit(1)
    else:
        print("  All tests passed!\n")


if __name__ == "__main__":
    run_all_tests()
