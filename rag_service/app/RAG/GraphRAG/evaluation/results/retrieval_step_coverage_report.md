# Retrieval Step-Coverage (production agent path, frozen contexts)

Samples: 45

| k | coverage | strict | named | described |
|---|----------|--------|-------|-----------|
| 5 | 0.441 | 0.441 | 0.704 | 0.283 |
| 10 | 0.550 | 0.550 | 0.835 | 0.367 |
| 15 | 0.601 | 0.601 | 0.885 | 0.419 |
| 20 | 0.601 | 0.601 | 0.885 | 0.419 |

_coverage: fraction of chronological attack steps with >=1 gold ID in top-k retrieved (S-recall@k). Low described vs named = the retriever finds keyword-named techniques but misses behaviour-described ones._
