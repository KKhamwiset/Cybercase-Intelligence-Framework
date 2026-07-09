# Mapping Module Evaluation — build_mitre_table vs gold

Config threshold: 0.62  |  Samples: 45

| Source | precision | recall | F1 | avg IDs/sample |
|--------|-----------|--------|----|----------------|
| raw retrieval (no filter) | 0.079 | 0.788 | 0.138 | 64.4 |
| mapped table (answer A) | 0.395 | 0.696 | 0.490 | 8.1 |
| mapped table (answer B) | 0.399 | 0.696 | 0.493 | 8.1 |
| mapped table (answer C) | 0.404 | 0.696 | 0.497 | 7.9 |
| mapped table (answer E) | 0.385 | 0.699 | 0.484 | 8.3 |

## Threshold sweep (variant A answers)

| threshold | precision | recall | F1 | avg IDs |
|-----------|-----------|--------|----|---------|
| 0.00 | 0.238 | 0.707 | 0.351 | 12.9 |
| 0.30 | 0.238 | 0.707 | 0.351 | 12.9 |
| 0.40 | 0.238 | 0.707 | 0.351 | 12.9 |
| 0.50 | 0.238 | 0.707 | 0.351 | 12.9 |
| 0.55 | 0.238 | 0.707 | 0.351 | 12.9 |
| 0.60 | 0.238 | 0.707 | 0.351 | 12.9 |
| 0.70 | 0.445 | 0.696 | 0.530 | 7.2 |
