# MITRE ATT&CK GraphRAG Architecture

This document describes the complete architecture of the GraphRAG pipeline located in `backend/RAG/GraphRAG`. The pipeline is designed to ingest MITRE ATT&CK STIX data, provide a dual vector-graph retrieval mechanism, and support a LangGraph-based agentic pipeline with cross-lingual support (Thai/English), self-reflection, and follow-up capabilities.

## High-Level Flow

1. **Ingestion:** STIX data is parsed and loaded into **Neo4j** (Graph DB) and **Qdrant** (Vector DB).
2. **Querying:** User queries (in Thai or English) are routed, translated to English, and sent to the Hybrid Retriever.
3. **Hybrid Retrieval:** Performs Vector Search to find initial nodes/relationships, followed by Graph Expansion to extract structural context.
4. **Agentic Pipeline (LangGraph):** Evaluates retrieved context. It can loop back to rewrite the query (Self-Reflection) or pause to ask the user for clarification (Follow-Up).
5. **Generation & Translation:** An LLM synthesizes the final answer and translates it back to the original language if needed.

---

## 1. Data Ingestion (`ingestion/`)

- **`stix_parser.py`**: Parses MITRE ATT&CK STIX 2.1 JSON bundles.
- **`graph_loader.py`**: Loads the parsed entities (nodes) and relationships (edges) into a **Neo4j** database to capture structural threat intelligence.
- **`vector_loader.py`**: Computes embeddings using `BAAI/bge-m3` and loads the entities and relationships into **Qdrant** (which replaced ChromaDB).

## 2. Retrieval System (`retrieval/`)

The retrieval system employs a Hybrid RAG approach, combining the semantic power of dense vectors with the structural accuracy of graph databases.

- **`vector_retriever.py`**: Performs semantic search in Qdrant. The embedding model `BAAI/bge-m3` supports both dense and sparse representations.
- **`graph_retriever.py`**: Takes STIX IDs (from the vector results) and queries Neo4j to pull subgraphs (a center node, its neighbors, and connecting edges) within a specified hop depth.
- **`hybrid_retriever.py`**: Orchestrates the retrieval process:
  1. Retrieves top-K items via Vector Search.
  2. Extracts their STIX IDs and performs Graph Expansion.
  3. Merges the semantic results and subgraph results into a single context block (`GraphRAGResult`) for the LLM.

## 3. Agentic Pipeline (`pipeline/`)

The core execution logic uses **LangGraph** (`agent_graph.py`) to move beyond simple linear LCEL chains (`chain.py`), introducing intelligent loops.

### Agent Workflow (Nodes)
- **Routing (`router.py`)**: Classifies the user's intent into either a general explanation (no retrieval needed) or an incident analysis (requires retrieval).
- **Cross-Lingual Layer (`cross_lingual.py`)**: Translates Thai queries to English before retrieval, as English queries yield better results against MITRE data.
- **Retrieval**: Invokes the `HybridRetriever`.
- **Evaluation / Self-Reflection (`evaluator.py`)**: The retrieved context is evaluated against the query:
  - **Sufficient**: Proceeds to reasoning.
  - **Insufficient**: Rewrites the query and triggers a re-retrieval loop (up to a configured max retry limit).
  - **Needs Clarification**: Pauses the pipeline and issues a follow-up question to the user.
- **Reasoning**: The LLM (Claude) generates a plain-English narrative based on the combined Graph+Vector context.
- **Translation**: Translates the final English response back to Thai if the original query was in Thai.

## 4. Configuration & Infrastructure (`config.py`)

- **Embedding Model**: `BAAI/bge-m3` (dim: 1024, running in fp16).
- **Reranker Model**: `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`.
- **Vector Database**: **Qdrant** (Collections: `mitre_entities`, `mitre_relationships`).
- **Graph Database**: **Neo4j**.
- **LLMs**:
  - **Primary (Reasoning/Translation)**: Anthropic `claude-sonnet-4-20250514`.
  - **Evaluation (Ragas)**: `meta-llama/llama-3.3-70b-instruct:free` (via OpenRouter).

## 5. Evaluation & Metrics (`evaluation/`)

A dedicated evaluation suite to benchmark the RAG pipeline's performance.
- Uses **Ragas** framework to compute metrics.
- **`generate_eval_dataset.py`**: Generates synthetic Q&A datasets based on the STIX knowledge base.
- **`generation_metrics.py` & `retriever_metrics.py`**: Measures context precision, recall, faithfulness, and answer relevancy.

Viewed Architecture.md:1-31
Viewed chain.py:1-237

The system actually uses **both**, but for different components of the pipeline:

1. **LangGraph (`agent_graph.py`)**: It uses LangGraph for the new, advanced `GraphRAGAgent`. LangGraph is used to build a stateful, non-linear graph that allows the pipeline to loop back on itself. This is what enables the **Self-Reflection** (re-retrieving if context is bad) and **Follow-Up** capabilities (pausing the graph to ask you a question and resuming later).
2. **LangChain (`chain.py`)**: It uses LangChain for the foundational pieces like LLM integrations (`langchain_anthropic` for Claude), message formatting (`SystemMessage`, `HumanMessage`), and the legacy `GraphRAGChain`, which is a traditional, linear LCEL (LangChain Expression Language) pipeline without the smart looping capabilities.

You can switch between them when running the pipeline; for example, passing the `--agent` flag in `main.py` tells the system to use the LangGraph version instead of the standard LangChain version!
