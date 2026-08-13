# RAG and Backend Contract

## RAG HTTP response

`rag_service/app/schemas/rag.py` and
`backend/app/schemas/chat/rag.py` define the response boundary:

```json
{
  "status": "completed",
  "retrieval_context_id": "...",
  "context": "bounded retrieved MITRE context",
  "mitre_table": []
}
```

Both schemas use `extra="forbid"`. `answer` and `rag_answer` are not accepted
or forwarded across this boundary. `context` is required and may be empty at
the schema level; the backend's initial-analysis validation requires a usable
context ID and non-empty context before durable completion.

## Full agent pipeline

The `/query` route currently calls `rag_agent.query(query, verbose=False)`.
This intentionally preserves the full LangGraph retrieval-quality path rather
than using the old retrieve-only shortcut. Depending on evaluator results, the
agent can decompose, retrieve, rerank, evaluate, broaden, retrieve again, and
then reason/translate. The final RAG answer is discarded at the HTTP boundary;
Main Case Analysis is the backend's user-facing analysis stage.

The retrieval stack includes Qdrant dense/sparse search, a cross-encoder
reranker (`BAAI/bge-reranker-v2-m3` by current configuration), and Neo4j graph
expansion. The actual pipeline code is authoritative if configuration changes.

Relevant paths:

- `rag_service/app/routers/rag.py`
- `rag_service/app/schemas/rag.py`
- `rag_service/app/RAG/GraphRAG/pipeline/agent_graph.py`
- `rag_service/app/RAG/GraphRAG/retrieval/hybrid_retriever.py`
- `rag_service/app/RAG/GraphRAG/retrieval/reranker.py`

## MITRE table

The RAG route builds the table inside `rag_service` from the GraphRAG result.
The generated answer may still be used internally by the current table builder
as a relevance signal, but it is not serialized into the response or context
snapshot. Backend/Main Analysis receives only the table rows and retrieved
context. Treat any future change to `relevance` or answer-derived mapping as a
wire-contract change requiring focused tests.

## Context lifetime

`rag_service/app/routers/context_store.py` stores retrieval snapshots in
process-local `app.state` with a one-hour TTL. That cache is not durable and is
not sufficient as the backend's only grounding store. The backend persists the
actual context and MITRE table in `rag_contexts`, linked to the Case State
version, so ASK can reuse the exact grounding snapshot after the RAG cache is
gone.

## Do not regress

- Do not reintroduce `answer` or `rag_answer` into either `QueryResponse`.
- Do not replace the full agent call with retrieve-only unless retrieval quality
  is intentionally redesigned and benchmarked.
- Do not feed Main Case Analysis output back into RAG for citation labeling.
- Do not treat an opaque `retrieval_context_id` as the retrieval content.
