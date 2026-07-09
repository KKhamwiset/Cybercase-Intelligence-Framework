# Cross-Lingual Generation Benchmark — Deterministic Metrics

Samples per variant: A=45, B=45, C=45, E=45

| Metric | A | B | C | E |
|--------|-------|-------|-------|-------|
| id_f1 | 0.479 | 0.473 | 0.468 | 0.391 |
| id_precision | 0.371 | 0.369 | 0.366 | 0.274 |
| id_recall | 0.718 | 0.699 | 0.688 | 0.721 |
| id_survival | 1.000 | 1.000 | — | — |
| ids_gained_in_translation | 0.000 | 0.000 | — | — |
| latency_ms | 29521.004 | 28272.300 | 12566.475 | 8198.798 |
| llm_calls | 2.000 | 3.000 | 1.000 | 1.000 |
| output_tokens | 3459.889 | 3383.356 | 1945.200 | 778.111 |
| step_cov_described | 0.504 | 0.507 | 0.476 | 0.517 |
| step_cov_named | 0.935 | 0.923 | 0.935 | 0.935 |
| structure | 1.000 | 1.000 | 1.000 | 1.000 |
| tactic_f1 | 0.811 | 0.812 | 0.810 | 0.759 |
| thai_ratio | 0.886 | 0.891 | 0.835 | 0.000 |

## Paired deltas vs baseline A (id_f1)

| Variant | mean Δ | 95% CI | Wilcoxon p | n pairs |
|---------|--------|--------|------------|---------|
| B | -0.006 | [-0.023, +0.010] | 0.8376 | 45 |
| C | -0.011 | [-0.029, +0.007] | 0.2415 | 45 |
| E | -0.087 | [-0.118, -0.058] | 0.0000 | 45 |
