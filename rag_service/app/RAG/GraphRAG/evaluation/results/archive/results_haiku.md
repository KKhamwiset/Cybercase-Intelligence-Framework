[EVAL] Loaded 3324 evaluation samples from Thai_dataset_08.json
[EVAL] Filtered out 21 samples with > 50 relevant STIX IDs
[EVAL] Capped to 1 samples (--max-samples)
[EVAL] Samples for evaluation: 1

════════════════════════════════════════════════════════════
  Evaluating: Answer Generation (GraphRAGChain)
════════════════════════════════════════════════════════════
[EVAL] Loading embedding model BAAI/bge-m3...

───────────────────── Initializing GraphRAG Chain ─────────────────────
[TRANSLATE] Local model: qwen2.5:7b
[VECTOR] Using Qdrant Cloud at https://840f3e20-49f1-4f47-bd34-c20996e34b9c.us-east-2-0.aws.cloud.qdrant.io
[VECTOR] Entity collection: 2733 docs
[VECTOR] Relationship collection: 25467 docs
[GRAPH] Connected to neo4j+s://71750b02.databases.neo4j.io
[RERANKER] Loading cross-encoder/mmarco-mMiniLMv2-L12-H384-v1...
[RERANKER] Ready
[HYBRID] GraphRAG retriever initialized
[ROUTER] Local model: qwen2.5:7b
[CHAIN] Reasoning LLM  : qwen2.5:7b (local)
[CHAIN] Translation LLM: qwen2.5:7b (local)
[CHAIN] GraphRAG chain ready

[EVAL] Running generation evaluation on 1 samples...
[TRANSLATE] Query is English, skipping translation
[RETRIEVE] Query: What mitigations exist for Ingress Tool Transfer?...
[RETRIEVE] Vector search: 10 results (pre-rerank)
[RERANKER] Top-10 after reranking: Network Intrusion Prevention (1.000), Ingress Tool Transfer (0.954), cmd (0.875), Ingress Tool Transfer (0.827), Lateral Tool Transfer (0.636), Scheduled Transfer Mitigation (0.252), Data Transfer Size Limits Mitigation (0.044), Process Injection Mitigation (0.007), Access Token Manipulation Mitigation (0.003), Upload Tool (0.003)
[RETRIEVE] Graph expansion: 5 subgraphs
           → Network Intrusion Prevention (70 neighbors, 70 edges)
           → Ingress Tool Transfer (540 neighbors, 540 edges)
           → cmd (14 neighbors, 14 edges)
           → Ingress Tool Transfer (22 neighbors, 22 edges)
           → Lateral Tool Transfer (69 neighbors, 69 edges)
  [1/1] latency=56844ms answer_len=2104
[EVAL] Using Claude claude-haiku-4-5 as RAGAS judge

============================================================
  Generation Evaluation  (1 samples)
============================================================
  Metric                             Score
  ────────────────────────────────────────
  Faithfulness (RAGAS)               0.036
  Answer Correctness (RAGAS)           nan
  ────────────────────────────────────────
  Token F1                           0.263
  ROUGE-L                            0.172
  BERTScore F1                       0.834

  Avg Latency (ms)                 56843.7


════════════════════════════════════════════════════════════
  EVALUATION COMPLETE
════════════════════════════════════════════════════════════
