# Cross-Lingual Generation Benchmark — Deterministic Metrics

Samples per variant: A=8, B=8, C=8, E=8

| Metric | A | B | C | E |
|--------|-------|-------|-------|-------|
| id_f1 | 0.442 | 0.417 | 0.445 | 0.325 |
| id_precision | 0.353 | 0.330 | 0.347 | 0.222 |
| id_recall | 0.617 | 0.592 | 0.648 | 0.640 |
| id_survival | 1.000 | 1.000 | — | — |
| ids_gained_in_translation | 0.000 | 0.000 | — | — |
| latency_ms | 28894.807 | 28931.919 | 13710.276 | 8499.631 |
| llm_calls | 2.000 | 3.000 | 1.000 | 1.000 |
| output_tokens | 3376.875 | 3436.750 | 2000.500 | 824.250 |
| step_cov_described | 0.500 | 0.500 | 0.500 | 0.500 |
| step_cov_named | 0.708 | 0.625 | 0.792 | 0.708 |
| structure | 1.000 | 1.000 | 1.000 | 1.000 |
| tactic_f1 | 0.842 | 0.841 | 0.855 | 0.757 |
| thai_ratio | 0.884 | 0.891 | 0.835 | 0.000 |

## Paired deltas vs baseline A (id_f1)

| Variant | mean Δ | 95% CI | Wilcoxon p | n pairs |
|---------|--------|--------|------------|---------|
| B | -0.026 | [-0.064, -0.002] | n/a | 8 |
| C | +0.003 | [-0.029, +0.040] | 1.0000 | 8 |
| E | -0.117 | [-0.217, -0.028] | 0.0391 | 8 |
