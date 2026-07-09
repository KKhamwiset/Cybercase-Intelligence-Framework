# Mapping Module Evaluation — build_mitre_table vs gold

Config threshold: 0.62  |  Samples: 8

| Source | precision | recall | F1 | avg IDs/sample |
|--------|-----------|--------|----|----------------|
| raw retrieval (no filter) | 0.068 | 0.825 | 0.120 | 65.9 |
| mapped table (answer A) | 0.427 | 0.633 | 0.488 | 6.9 |
| mapped table (answer B) | 0.426 | 0.633 | 0.488 | 7.2 |
| mapped table (answer C) | 0.417 | 0.633 | 0.482 | 7.1 |
| mapped table (answer E) | 0.379 | 0.675 | 0.469 | 7.6 |

## Threshold sweep (variant A answers)

| threshold | precision | recall | F1 | avg IDs |
|-----------|-----------|--------|----|---------|
| 0.00 | 0.227 | 0.675 | 0.335 | 11.9 |
| 0.30 | 0.227 | 0.675 | 0.335 | 11.9 |
| 0.40 | 0.227 | 0.675 | 0.335 | 11.9 |
| 0.50 | 0.227 | 0.675 | 0.335 | 11.9 |
| 0.55 | 0.227 | 0.675 | 0.335 | 11.9 |
| 0.60 | 0.227 | 0.675 | 0.335 | 11.9 |
| 0.70 | 0.443 | 0.633 | 0.498 | 6.6 |
