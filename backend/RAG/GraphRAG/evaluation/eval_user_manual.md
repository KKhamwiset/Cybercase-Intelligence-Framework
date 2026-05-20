# RAG Evaluation Framework — User Manual

**For:** MITRE ATT&CK GraphRAG system  
**Location:** `backend/RAG/GraphRAG/evaluation/`

---

## 1. Prerequisites

### Install optional eval dependencies
```bash
pip install ragas datasets          # RAGAS metrics (recommended)
pip install bert-score rouge-score  # BERTScore + ROUGE
```

> [!NOTE]
> The framework still runs without these — it falls back to Token F1 and ROUGE-L which are built-in.

### Make sure your databases are running (for live eval)
```bash
# Neo4j + ChromaDB must be up before running retriever/generation eval
docker-compose up -d
```

---

## 2. File Overview

| File | What it does |
|---|---|
| [eval_dataset.json](file:///backend/RAG/GraphRAG/evaluation/eval_dataset.json) | Your test questions + ground-truth answers |
| [ground_truth.py](file:///backend/RAG/GraphRAG/evaluation/ground_truth.py) | Loads/saves that dataset |
| [retriever_metrics.py](file:///backend/RAG/GraphRAG/evaluation/retriever_metrics.py) | Computes Hit@K, Recall@K, MRR, NDCG@K, MAP |
| [generation_metrics.py](file:///backend/RAG/GraphRAG/evaluation/generation_metrics.py) | Computes Faithfulness, Answer Relevancy, ROUGE-L |
| [eval_runner.py](file:///backend/RAG/GraphRAG/evaluation/eval_runner.py) | CLI that runs everything |
| [test_metrics.py](file:///backend/RAG/GraphRAG/evaluation/test_metrics.py) | Quick sanity-check (no DB needed) |

---

## 3. Quick Start (5 Minutes)

### Step 1 — Verify the metrics work (no DB needed)
```bash
cd backend/RAG/GraphRAG
python evaluation/test_metrics.py
```

**Expected output:**
```
==================================================
  RAG Evaluation -- Unit Tests
==================================================

  [PASS] hit_at_k
  [PASS] recall_at_k
  [PASS] precision_at_k
  [PASS] reciprocal_rank (MRR)
  [PASS] ndcg_at_k
  [PASS] average_precision (MAP)
  [PASS] token_f1
  [PASS] rouge_l
  [PASS] ground_truth save/load

  Results: 9 passed, 0 failed, 9 total
  All tests passed!
```

### Step 2 — Run retriever evaluation (needs Neo4j + ChromaDB)
```bash
python -m evaluation.eval_runner --dataset evaluation/eval_dataset.json --mode retriever
```

### Step 3 — Run generation evaluation (needs LLM API key)
```bash
python -m evaluation.eval_runner --dataset evaluation/eval_dataset.json --mode generation
```

### Step 4 — Run everything
```bash
python -m evaluation.eval_runner --dataset evaluation/eval_dataset.json --mode full
```

---

## 4. Understanding eval_dataset.json

This is your **ground-truth test set**. Each entry looks like this:

```json
{
  "query": "What is Phishing (T1566)?",
  "relevant_stix_ids": [
    "attack-pattern--a62a8db3-f23a-4d8f-afd6-9dbc77e7813b"
  ],
  "reference_answer": "Phishing (T1566) is...",
  "language": "en",
  "category": "technique_lookup"
}
```

| Field | Required | Description |
|---|---|---|
| [query](file:///backend/RAG/GraphRAG/pipeline/chain.py#95-214) | Yes | The test question (English or Thai) |
| `relevant_stix_ids` | Yes | List of STIX IDs the retriever MUST find |
| [reference_answer](file:///backend/RAG/GraphRAG/evaluation/ground_truth.py#29-31) | Optional | Gold-standard answer (enables RAGAS context metrics) |
| `language` | Optional | `"en"` or `"th"` (default: `"en"`) |
| `category` | Optional | Label for grouping results |

> [!TIP]
> Leave `relevant_stix_ids` as `[]` for open-ended queries where retrieval ground truth is unknown.  
> Leave [reference_answer](file:///backend/RAG/GraphRAG/evaluation/ground_truth.py#29-31) as `""` if you only want retriever metrics.

---

## 5. How to Add Your Own Test Cases

### Option A — Edit [eval_dataset.json](file:///backend/RAG/GraphRAG/evaluation/eval_dataset.json) directly

Append a new entry to the JSON array:
```json
{
  "query": "What techniques use PowerShell?",
  "relevant_stix_ids": [
    "attack-pattern--970a3432-3237-47ad-8273-6c9e88f09a32"
  ],
  "reference_answer": "PowerShell (T1059.001) is a sub-technique...",
  "language": "en",
  "category": "technique_lookup"
}
```

### Option B — Find STIX IDs from Neo4j
```cypher
// Find the STIX ID for any technique by name
MATCH (n:Technique)
WHERE n.name CONTAINS "PowerShell"
RETURN n.name, n.stix_id, n.attack_id
```

### Option C — Use Python API

```python
import sys
sys.path.insert(0, "backend/RAG/GraphRAG")

from evaluation.ground_truth import EvalSample, load_ground_truth, save_ground_truth

# Load existing samples
samples = load_ground_truth("evaluation/eval_dataset.json")

# Add a new sample
samples.append(EvalSample(
    query="What is Credential Dumping?",
    relevant_stix_ids=["attack-pattern--0a3ead4e-6d47-4ccb-854c-a6a4f9d96b22"],
    reference_answer="Credential Dumping involves...",
    category="technique_lookup",
))

# Save back
save_ground_truth(samples, "evaluation/eval_dataset.json")
```

---

## 6. Reading the Retriever Results

When you run `--mode retriever`, you get output like this:

```
============================================================
  Retriever: Hybrid (Vector+Graph)  (12 samples)
============================================================
  Metric                    @1      @3      @5     @10
  ────────────────────────────────────────────────────
  Hit                    0.750   0.833   0.917   1.000
  Recall                 0.600   0.750   0.833   0.917
  Precision              0.750   0.444   0.333   0.250
  NDCG                   0.750   0.792   0.846   0.900

  MRR                    0.792
  MAP                    0.771
  Avg Latency (ms)       1240.5
```

### What each metric means

| Metric | Plain English | Good score |
|---|---|---|
| **Hit@K** | "Did we find at least one right answer in top K?" | > 0.8 |
| **Recall@K** | "What % of all correct answers did we find?" | > 0.7 |
| **Precision@K** | "What % of what we returned was actually correct?" | > 0.4 |
| **NDCG@K** | "Are the correct answers ranked near the top?" | > 0.7 |
| **MRR** | "On average, the first correct answer is at position 1/MRR" | > 0.7 |
| **MAP** | "Overall retrieval quality, single number" | > 0.6 |

### Comparison table (side-by-side)

```
======================================================================
  RETRIEVER COMPARISON
======================================================================
  Metric               Vector (ChromaDB)    Graph (Neo4j)    Hybrid
  ────────────────────────────────────────────────────────────────
  Hit@5                        0.750            0.583        0.917
  Recall@5                     0.667            0.500        0.833
  Precision@5                  0.267            0.200        0.333
  NDCG@5                       0.710            0.580        0.846
  MRR                          0.680            0.540        0.792
  MAP                          0.643            0.510        0.771
  Latency (ms)                 450.1           1850.3       1240.5
```

---

## 7. Reading the Generation Results

```
============================================================
  Generation Evaluation  (15 samples)
============================================================
  Metric                                Score
  ────────────────────────────────────────────
  Faithfulness (RAGAS)                  0.912
  Answer Relevancy (RAGAS)              0.876
  Context Precision (RAGAS)             0.800
  Context Recall (RAGAS)                0.743
  Answer Correctness (RAGAS)            0.681
  ────────────────────────────────────────────
  Token F1                              0.534
  ROUGE-L                               0.412
  BERTScore F1                          0.871

  Avg Latency (ms)                     4320.1
```

### What to look for

| Score | Meaning |
|---|---|
| **Faithfulness < 0.7** | LLM is hallucinating — answers not grounded in retrieved context |
| **Answer Relevancy < 0.7** | Answers are off-topic or too generic |
| **Low Token F1 / ROUGE-L** | Answer wording very different from reference (may still be semantically correct — check BERTScore) |
| **BERTScore > 0.85** | Semantically very similar to reference despite different wording |

---

## 8. Use Only Metrics (No Runner)

You can call the metrics directly in your own scripts:

### Retriever metrics
```python
import sys
sys.path.insert(0, "backend/RAG/GraphRAG")

from evaluation.retriever_metrics import hit_at_k, recall_at_k, ndcg_at_k, mrr

retrieved = ["attack-pattern--abc", "attack-pattern--def", "attack-pattern--ghi"]
relevant  = {"attack-pattern--def", "attack-pattern--xyz"}

print(f"Hit@3       : {hit_at_k(retrieved, relevant, k=3):.3f}")   # 1.000
print(f"Recall@3    : {recall_at_k(retrieved, relevant, k=3):.3f}") # 0.500
print(f"NDCG@3      : {ndcg_at_k(retrieved, relevant, k=3):.3f}")  # varies
```

### Generation metrics
```python
from evaluation.generation_metrics import token_f1, rouge_l

prediction = "Phishing is a technique where adversaries send emails with malicious links."
reference  = "Phishing (T1566) involves sending deceptive messages to gain access."

scores = token_f1(prediction, reference)
print(f"Token F1: {scores['f1']:.3f}")
print(f"ROUGE-L : {rouge_l(prediction, reference):.3f}")
```

---

## 9. Evaluation Modes Summary

| Mode | What runs | Requires |
|---|---|---|
| `--mode retriever` | Vector, Graph, Hybrid benchmarks (all metrics) | Neo4j + ChromaDB |
| `--mode generation` | RAGAS + fallback answer quality metrics | LLM API key |
| `--mode full` | Both retriever + generation | All of the above |

---

## 10. Common Issues

| Problem | Fix |
|---|---|
| `FileNotFoundError: eval_dataset.json` | Run from `backend/RAG/GraphRAG` directory |
| `RAGAS not available` | `pip install ragas datasets` |
| `Neo4j connection refused` | Start Docker: `docker-compose up -d` |
| `No ANTHROPIC_API_KEY` | Set in [.env](file:///.env) file: `ANTHROPIC_API_KEY=sk-ant-...` |
| Scores all 0.0 for retriever | Check that `relevant_stix_ids` in dataset match actual ChromaDB IDs |
