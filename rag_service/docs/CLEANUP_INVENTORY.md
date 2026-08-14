# `rag_service/` Cleanup Inventory — Phase 1

Branch: `chore/rag-service-cleanup` (off `main` @ `30059ab`)
Compiled: 2026-08-13. No edits made; this document is the proposal.

Grep scope for every "who references it" line below: the whole repo
(`backend/`, `frontend/`, `rag_service/`, `.github/workflows/`, `docker-compose.yml`,
`Dockerfile`s, `*.md`), excluding `node_modules/` and `evaluation/results/`.

---

## Headline

| | |
|---|---|
| Files proposed for outright deletion | **4** (`chain.py`, `thanoy_client.py`, `_perf_probe.py`, `howtothanoy.md`) |
| Lines in those files | **677** |
| Additional in-file deletions | ~**230** lines across 9 files (Ollama blocks, `use_agent` branch, dead config) |
| Total | ~**900** lines across **17** files |

**Highest-risk single removal: `pipeline/chain.py`.** Not because production
needs it — production genuinely never reaches it — but because
`evaluation/eval_runner.py` (the `--mode generation` path) constructs
`GraphRAGChain` directly, and `evaluation/` is off-limits in this pass and has
unmerged work on `eval/real-cti-dataset`. Deleting `chain.py` breaks the
evaluation harness on this branch and will conflict on merge. **This one needs
your decision before I touch it** — see "Needs a human decision" §H1.

---

## Ground truth re-verified

All four claims in the brief still hold as of today's tree.

1. **Agent path is the only one serving traffic.** ✅
   `rag_service/app/schemas/rag.py:12` → `use_agent: bool = True`.
   `backend/app/services/chat/rag_client.py:31` → `QueryRequest(query=content, use_agent=True)`.
   `rag_service/app/routers/rag.py:30` → `if request.use_agent:` takes the agent branch;
   lines 54–76 (the chain branch) are unreachable for every caller in this repo.

2. **No input translation on the agent path.** ✅
   `pipeline/agent_graph.py:548-571` `_node_prepare` returns `{"english_query": query}`
   verbatim. `DUAL_QUERY_RETRIEVAL` and `CrossLingualLayer.translate_query()` are
   reached only from `chain.py` and `evaluation/`.

3. **Local/Ollama is dropped from the service.** ✅ *with one correction.*
   `USE_LOCAL` defaults false and is not set in `docker-compose.yml` or
   `.github/workflows/deploy.yml`. **But `--local` does not exist in
   `RAG/GraphRAG/main.py` at all** — it is only an `evaluation/eval_runner.py`
   and `evaluation/crosslingual_benchmark.py` flag. And `evaluation/` still uses
   Ollama for real (RAGAS judge, `nomic-embed-text` embeddings, the
   `ollama:<name>` local arm of the generation benchmark). See §H2 — this
   materially limits what can be removed.
   `LOCAL_REASONING_MODEL` does not exist anywhere in the tree; nothing to remove.

4. **Single-call Thai generation is live.** ✅
   `config.py:175` `SINGLE_CALL_GENERATION` defaults true;
   `agent_graph.py:692-704` picks `get_fast_system_prompt()` when it and
   `respond_in_thai` are both set. **But the two-stage path is not dead** — see §H3.

---

## Blocking constraint you should read first

`evaluation/` is excluded from this pass, and it is the *largest consumer* of
the code that looks dead from production's point of view:

| Symbol | Production use | `evaluation/` use |
|---|---|---|
| `GraphRAGChain` | none | `eval_runner.py:197,199` (`--mode generation`) |
| `ChainResponse` | `routers/rag.py:57` (dead branch only) | none |
| `CrossLingualLayer.__init__` / `translate_query` | none | `eval_runner.py:206`, `crosslingual_benchmark.py:94,96`, `crosslingual_generation_benchmark.py:156,175` |
| `build_retrieval_queries` | none | `eval_runner.py:204,207` |
| `DUAL_QUERY_RETRIEVAL` | none | via `build_retrieval_queries` |
| `HybridRetriever.retrieve_multi` | none | `eval_runner.py:208`, `crosslingual_benchmark.py:167` |
| `OLLAMA_BASE_URL` | Ollama blocks only | `eval_runner.py:473`, `generation_metrics.py:103`, `crosslingual_generation_benchmark.py:400` |
| `LOCAL_LLM_MODEL` | Ollama blocks only | `eval_runner.py:473` |
| `LOCAL_EVAL_MODEL` | `evaluator.py` Ollama block only | `eval_runner.py:473`, `generation_metrics.py:103` |
| `get_translation_system_prompt` | `agent_graph.py:741` (reachable, see §H3) | `crosslingual_generation_benchmark.py:321` |
| `get_reasoning_system_prompt` | `agent_graph.py:703` (reachable, see §H3) | `crosslingual_generation_benchmark.py:317,348` |

Consequence: **`langchain-ollama` must stay in `requirements.txt`**, and
`OLLAMA_BASE_URL` / `LOCAL_LLM_MODEL` / `LOCAL_EVAL_MODEL` must stay in
`config.py`, even after every `use_local` block leaves the pipeline. The brief
listed all of these as removable; they are not, unless you also want
`evaluation/` in scope.

---

## A. Safe — dead with zero references outside their own definition

### A1. `pipeline/thanoy_client.py` — 105 lines
**What:** async client for the iApp "Thanoy" Thai legal LLM, for a report
"legal advice" section.
**Referenced by:** nothing. Not in `pipeline/__init__.py`, not imported by any
`.py` in the repo (`grep -rni thanoy` returns only this file, the `config.py`
block that feeds it, and `rag_service/howtothanoy.md`). Not copied into the
prod image beyond the blanket `COPY app/RAG/GraphRAG/pipeline`.
**Verdict: dead.** The report workflow it was written for does not exist —
`CLAUDE.md` states there are no backend report routes and the frontend Report
tab is client-side demo only.
**Also goes:** `config.py:194-204` (`THANOY_API_KEY`, `THANOY_API_URL`,
`THANOY_TIMEOUT`, `THANOY_ENABLED`, and the section banner);
`rag_service/howtothanoy.md` (115 lines, setup notes for the deleted client).
`THANOY_*` appears in no compose file, workflow, or Doppler-referenced env list.

### A2. `app/_perf_probe.py` — 141 lines
**What:** self-described "throwaway perf probe"; monkeypatches timers onto
`GraphRAGAgent` node methods and runs one query.
**Referenced by:** nothing. Not imported anywhere; not in the Dockerfile's
allowlisted `COPY` list, so it never ships. Loads `backend/.env` by relative
path from `rag_service/app`.
**Verdict: dead scratch file.** Also reaches into `retriever.graph_retriever._expand_single`,
a private, so it rots silently.
**Also goes:** nothing else.

### A3. Dead config constants
| Symbol | Location | Referenced by |
|---|---|---|
| `CHROMA_DIR`, `CHROMA_HOST`, `CHROMA_PORT`, `CHROMA_SSL`, `CHROMA_API_KEY`, `CHROMA_COLLECTION_ENTITIES`, `CHROMA_COLLECTION_RELATIONSHIPS` | `config.py:88-97` | nothing — ChromaDB was replaced by Qdrant |
| `GRAPH_EXPANSION_DEPTH` | `config.py:235` | nothing; `graph_retriever.py` takes depth as an argument |
| E5 commented block | `config.py:63-69` | n/a (already comments) |
| mmarco commented block | `config.py:270-273` | n/a (already comments) |

**Verdict: dead.** The two commented "LEGACY … kept for rollback" blocks are
judgment calls — they cost nothing and document a real prior decision. My
recommendation: **keep** the two comment blocks, **delete** the live-but-unused
`CHROMA_*` names and `GRAPH_EXPANSION_DEPTH`. A name that resolves is a name
someone will import.

### A4. `config.py:307` — `print(ATTACK_DOMAINS.items())`
Bare debug print at module scope. Fires on every import, including in the prod
container and in every test run. **Verdict: dead.** Confirmed live at startup:
`python -c "import main"` prints `dict_items([('enterprise', WindowsPath(...)])`.

### A5. `schemas/rag.py:34` — `ReviewStatusRequest`
**Referenced by:** only its own definition and the `schemas/__init__.py`
re-export. No router consumes it; the RAG service has no review endpoint.
**Verdict: dead.** **Also goes:** `schemas/__init__.py` import + `__all__` entry.

---

## B. Safe — the `use_agent` / `rag_chain` branch

### B1. The chain branch in `routers/rag.py` — lines 54–76
Unreachable per ground truth §1. Deleting it also drops the
`ChainResponse` import at `routers/rag.py:5`.

### B2. `use_agent` field — `schemas/rag.py:12`
**Referenced by:** `routers/rag.py:30` (the branch in B1), plus — outside
`rag_service/` — `backend/app/schemas/chat/rag.py:12`,
`backend/app/services/chat/rag_client.py:31`, `backend/tests/test_chat_rag_client.py:30`.
**Verdict: removable from `rag_service/` only.** `rag_service`'s `QueryRequest`
is a plain `BaseModel` (pydantic default `extra="ignore"`), so the backend can
keep sending `use_agent: true` into a schema that no longer declares it — no
error, no coordinated deploy needed. Removing the backend's half is a
cross-service change and out of this branch's scope; I'd leave `backend/`
alone and note it. **Say if you want the backend side too.**

### B3. `rag_chain` in `app/main.py` startup/shutdown
`main.py:11` (import), `:45` (construct), `:53` (None on failure), `:58-59`
(close), and `routers/rag.py:20` (`"rag_chain"` key in `/health`).
**Verdict: dead once B1 lands.** Removing it also halves service boot work —
today startup constructs *both* `GraphRAGChain` and `GraphRAGAgent`, each of
which opens its own `HybridRetriever` (Neo4j driver + Qdrant client) and its
own pair of chat models.
**Watch:** `/health` currently returns `{"status", "rag_chain", "rag_agent"}`.
Dropping the `rag_chain` key changes the response body. Nothing in `backend/`
or `frontend/` parses it (`grep -rn "rag_chain"` outside `rag_service/` → no
hits), and `docker-compose.yml` defines no healthcheck for `rag-service`. Safe,
but it *is* an observable API change — flagging rather than assuming.

---

## C. Medium — Ollama removal from the pipeline

Blocks to delete, each an `if use_local:` branch importing `ChatOllama` plus the
`use_local` parameter:

| File | Lines | Note |
|---|---|---|
| `pipeline/agent_graph.py` | `:151,155,165-197` (ctor), `:324-333` (`_get_ultrafast_llm`) | also `self.use_local` attribute |
| `pipeline/router.py` | `:72-81` | |
| `pipeline/evaluator.py` | `:167-175` | |
| `pipeline/query_decomposer.py` | `:151-164` | sole consumer of `LOCAL_NUM_CTX` |
| `pipeline/cross_lingual.py` | `:179-188` | **blocked** — see §H1/§H2 |
| `pipeline/chain.py` | `:71-110` | dies with the file, see §H1 |
| `app/main.py` | `:20,29,32,36-44,45-46` | `USE_LOCAL` import + the `llm_mode` string |

Config that becomes fully dead and *can* go:
- `LOCAL_NUM_CTX` (`config.py:229`) — only `query_decomposer.py` uses it.
- `USE_LOCAL` (`config.py:224`) — only `app/main.py` uses it.

Config that **must stay** (see the blocking-constraint table):
`OLLAMA_BASE_URL`, `LOCAL_LLM_MODEL`, `LOCAL_EVAL_MODEL`. Their comment block
at `config.py:206-219` needs rewriting to say "used by `evaluation/` only",
not "used when `--local` flag is passed" (there is no such pipeline flag).

Requirements: **`langchain-ollama` stays** (`requirements.txt:13`) —
`evaluation/generation_metrics.py:152`, `evaluation/eval_runner.py`, and
`evaluation/crosslingual_generation_benchmark.py:398` import it at runtime.

**Test that breaks:** `rag_service/tests/test_core_llm_provider.py:109-129`
`test_local_mode_takes_precedence_over_cloud_factory` calls
`router.QueryRouter(use_local=True)` with a faked `langchain_ollama` module.
It must be deleted in the same commit. It is testing exactly the behaviour
being removed, so deletion (not adaptation) is correct.

---

## D. Medium — CLI (`RAG/GraphRAG/main.py`)

Everything here is contingent on the `chain.py` decision (§H1).

- `run_tests()` / `run_interactive()` each carry an `if fast or ultrafast or use_agent: … else: GraphRAGChain()` fork (`:117-125`, `:171-179`). With the chain gone, the `else` goes and `GraphRAGAgent` becomes unconditional.
- `--agent` (`:274-278`) becomes a no-op flag. **This is the one place where dead-code removal changes observable behaviour**: today, bare `python -m RAG.GraphRAG.main` runs the *chain*; afterwards it runs the *agent*. That is forced by the removal, not a separate choice — but you should know it.
- `--confirm-clear` (`:268-272`) is **reachable** (`:305`) — leave it.
- `--retrieve-only` is **reachable** — `GraphRAGAgent.retrieve_only` exists (`agent_graph.py:243`), so the flag keeps working after the chain goes.
- `--fast` / `--ultrafast` are **reachable** (`query_fast` / `query_ultrafast`). See §H4 — I am not proposing to remove them, but they have no non-CLI caller.

False help text and docstrings to fix here:
- Module docstring `:4-10` says `python main.py --ingest`. That does not work — the module uses relative imports and must be run as `python -m RAG.GraphRAG.main` from `rag_service/app`. `CLAUDE.md` already says this correctly; the file contradicts it.
- `--agent` help: "with self-reflection and **follow-up**" — the follow-up module was deleted (`docs/FOLLOWUP_REMOVAL.md`).
- `--fast` help: "Skips … **follow-up** …" — same.
- `run_ingest()` docstring `:41`: "load into Neo4j + **ChromaDB**" — it loads Qdrant.

---

## E. Comments and docstrings that are already false

Independent of any deletion.

| Location | Claim | Reality |
|---|---|---|
| `CLAUDE.md:82` | "LangGraph (agentic loop) + LangChain **LCEL**" | LCEL is only `chain.py`. LangChain itself stays (`langchain_core.messages` in 7 files, `langchain_anthropic` via `llm_provider`). LangGraph is a separate library, not part of LangChain. |
| `CLAUDE.md:100-116` | pipeline diagram shows `[CROSS-LINGUAL] Translate query to English` | No such stage on the agent path (`_node_prepare`). Diagram also omits the decomposition step that *does* run. |
| `CLAUDE.md:57,68,94,162` | `--local` CLI flag on `RAG.GraphRAG.main`, "optional local Ollama mode" | No `--local` on that CLI. `--local` exists only on `evaluation/eval_runner.py` and `evaluation/crosslingual_benchmark.py`. |
| `CLAUDE.md:159-160` | Reasoning LLM `claude-sonnet-4-20250514`, Eval `claude-haiku-4-5` | `config.py:127` defaults `CORE_LLM_PROVIDER=openrouter` → `openai/gpt-5.6-luna`. Anthropic default is `claude-haiku-4-5`, not Sonnet 4. |
| `CLAUDE.md:53-56` | `--ingest` "resolves the STIX data dir from `_PROJECT_ROOT`, which currently points at `rag_service/` … Check this path before running ingestion" | **Stale — already fixed.** See §G. |
| `agent_graph.py:4` | "Replaces the linear LCEL chain" | Reference to a file that would no longer exist. |
| `agent_graph.py:143` | "Drop-in companion for `GraphRAGChain`" | Same. |
| `agent_graph.py:87-90` | state section header `── Translation ──` for `english_query` | Nothing is translated; the field mirrors the original query. `_node_prepare`'s own docstring already says so — the header contradicts it. |
| `agent_graph.py:661` | `_node_reasoning` docstring: "**Stage 2**: … synthesize into an **English** answer" | On the live path it writes Thai in one call. The "Stage 2/Stage 3" numbering is inherited from the deleted chain. |
| `config.py:246-247` | "Reranker — must handle Thai↔English pairs when `DUAL_QUERY_RETRIEVAL` is on" | The agent never reads `DUAL_QUERY_RETRIEVAL`. The reranker sees Thai-vs-English pairs for a different reason: no input translation at all. |
| `cross_lingual.py:1-13` | module docstring describes a 3-stage translate→reason→translate pipeline | Stage 1 is gone; stage 3 fires only on one narrow path (§H3). |
| `cross_lingual.py:252-258` | `get_fast_system_prompt` — "Single-pass system prompt for **`--fast` mode**" | It is the *default production* prompt (`agent_graph.py:701`), not a `--fast`-only prompt. This is the most actively misleading comment in the tree. |
| `context_builder.py:95` | `english_query` param: "The translated English query" | On the agent path it is always the original query; the `original_query != english_query` branch at `:109` is dead for production callers. |
| `main.py` (service) `:36-44` | `llm_mode` "LOCAL (Ollama)" | Never taken. |

Historical records I propose to **leave alone** (they describe past decisions,
not current behaviour, and are correctly dated): `docs/DUAL_QUERY_UPGRADE.md`,
`docs/FOLLOWUP_REMOVAL.md`, `docs/HANDOFF_AND_CLEANUP.md`.

Larger stale docs — `rag_service/ARCHITECTURE.md`, `docs/RAG_Module.md`,
`docs/ARCHITECTURE_v2.md`, `docs/PRIMER.md` — carry dozens of `use_local` /
Ollama / `GraphRAGChain` references (see grep hits in §Blocking constraint).
They are Thai-language reference docs with matching generated PDFs. Updating
them properly is a bigger job than this cleanup. **Recommendation:** out of
scope for this branch; add a dated "stale as of 2026-08-13" banner to each, or
tell me to leave them entirely.

---

## F. Reachable — leaving alone despite appearances

- `_node_translate_output` + `get_translation_system_prompt` — reachable, see §H3.
- `REASONING_SYSTEM_PROMPT` — feeds `get_fast_system_prompt`, which is the live prompt.
- `should_respond_in_thai`, `_is_thai` — live.
- `query_sanitizer.sanitize_retrieval_query` — live (`agent_graph.py:643,791`).
- `mitre_table.py` — live, consumed by `backend/app/services/reports/report_service.py:496`.
- `context_store.py`, `RetrievalContextSnapshot`, `/retrieval-contexts/{id}` — live.
- `INGEST_HISTORICAL`, `RRF_K`, `DENSE_WEIGHT`, `SPARSE_WEIGHT`, `ATTACK_DOMAIN_FILTER` — live.
- `app/download_model.py` — used by `Dockerfile:24`.
- `docs/_build_pdf.py` — a doc tool, not service code; harmless.
- Per your instruction, untouched: `MITRE_TABLE_SCORE_THRESHOLD`, `_TYPE_WEIGHTS`
  and node-type handling in `hybrid_retriever.py`, `retrieve_multi_quota()`.

---

## G. STIX ingestion path — already fixed, `CLAUDE.md` is stale

`CLAUDE.md:53-56` warns that `--ingest` resolves the data dir to `rag_service/`
while the bundles live at the repo root. **That is no longer true.**

`config.py:19-25` already has the fallback:
```python
_STIX_DATA_DIR = _PROJECT_ROOT / "Mitre_ATT&CK Doc"
if not _STIX_DATA_DIR.exists():
    _STIX_DATA_DIR = _PROJECT_ROOT.parent / "Mitre_ATT&CK Doc"
```
`_PROJECT_ROOT` is indeed `rag_service/`, `rag_service/Mitre_ATT&CK Doc` does
not exist, so the fallback fires. Verified by import — `ATTACK_DOMAINS` resolves to
`…/CyberCase-Intelligence-Framework/Mitre_ATT&CK Doc/enterprise-attack`, which
exists and holds the bundles.

**No code fix needed.** The fix is to delete the stale warning from `CLAUDE.md`
and add one line at `config.py:19` explaining *why* the fallback exists (repo
checkout vs. Docker image, where `rag_service/` is the build context root).

---

## H. Needs a human decision

### H1. Does `evaluation/` get to keep the chain? — **blocks the largest removal**
`evaluation/eval_runner.py:197-217` builds `GraphRAGChain`, calls
`chain.translator.translate_query()`, `build_retrieval_queries()`, and
`chain.retriever.retrieve_multi()`. That is the entire `--mode generation`
adapter. `evaluation/` is excluded from this pass and has unmerged work on
`eval/real-cti-dataset`.

Three options:

- **(a) Delete `chain.py` and everything chain-only.** Biggest win
  (~430 lines: the file, `ChainResponse`, `translate_query`,
  `CrossLingualLayer.__init__`, `build_retrieval_queries`,
  `TRANSLATE_TO_ENGLISH_PROMPT`, `DUAL_QUERY_RETRIEVAL`, `_is_mostly_english`,
  `retrieve_multi`, and 8 `__init__.py` re-export lines). **Breaks
  `evaluation/eval_runner.py --mode generation` and
  `evaluation/crosslingual_benchmark.py` on this branch, and will conflict with
  `eval/real-cti-dataset` on merge.**
- **(b) Delete only what production touches** — the `use_agent` branch,
  `rag_chain` in startup, the `ChainResponse` import in `routers/rag.py` — and
  leave `chain.py` + `cross_lingual` translation in place as an
  evaluation-only module, with a header comment saying exactly that.
  Safe, merges cleanly, leaves ~430 lines standing.
- **(c) (a), plus port `eval_runner`'s generation adapter onto
  `GraphRAGAgent`.** Correct end state, but it is a behaviour change inside
  `evaluation/` — explicitly out of scope, and it would change eval numbers.

**My recommendation: (b) now, (c) as a follow-up once
`eval/real-cti-dataset` merges.** The whole point of the exclusion is to avoid
that conflict, and (a) walks straight into it.

### H2. Ollama: is `evaluation/` allowed to keep using it?
If yes (the default reading of your exclusion), then `OLLAMA_BASE_URL`,
`LOCAL_LLM_MODEL`, `LOCAL_EVAL_MODEL`, and `langchain-ollama` all stay, and
"drop Ollama" means only "drop the `use_local` plumbing from the pipeline and
the service". If you actually want Ollama gone repo-wide, `evaluation/` must
come into scope — including the RAGAS `nomic-embed-text` embeddings at
`generation_metrics.py:152`, which have no cloud fallback wired up, and the
`ollama:` local arm of the generation benchmark that the fine-tune A/B depends on.

### H3. The two-stage translate path is **not** dead — remove or keep?
`_node_translate_output` is still reachable on two live routes:
1. `respond_in_thai=False` (an English query) → `single_call` is false → the
   reasoning node emits English and `_edge_after_reasoning` returns `"done"`.
   So `get_reasoning_system_prompt` runs, translate does not.
2. **`ACKNOWLEDGE_LIMIT`** — `_node_reasoning:681-685` returns the evaluator's
   message *without* setting `answer_is_final`. For a Thai query that message
   then goes through `_node_translate_output` (`_edge_after_reasoning:806-810`,
   the docstring calls this out deliberately).

Plus `SINGLE_CALL_GENERATION` is an env override documented as a rollback
switch. So `TRANSLATE_TO_THAI_SYSTEM_PROMPT` and the translate node are
**reachable — I am leaving them.** Confirm you agree; the brief implied they
might be removable.

### H4. `query_fast` / `query_ultrafast` — keep?
~140 lines in `agent_graph.py` plus `ULTRAFAST_MAX_TOKENS` / `ULTRAFAST_TOP_K`
in config. Reachable *only* from `RAG/GraphRAG/main.py`'s `--fast` /
`--ultrafast` CLI flags — no HTTP route, no `backend/` caller, and
`RAG/GraphRAG/main.py` is not even copied into the prod image (`Dockerfile:34-46`
is an allowlist that omits it). They are a latency-experiment surface.
**Not proposing removal** — they work and are a deliberate tool — but if you
consider the experiment finished, this is the second-largest win available and
it is completely self-contained. Your call.

### H5. The router makes a paid LLM call whose answer is discarded
`_edge_after_route` (`agent_graph.py:758-764`) is hard-wired to `return "incident"`,
with the real branch commented out and marked `TEMPORARILY DISABLED ROUTER`.
But `_node_route_query` still runs on every request and still calls
`self.router.route_query()` — one LLM round-trip per query, result thrown away.
Consequently `_node_general_explanation` and the `"general"` graph edge are
unreachable, and `QueryRouter` + `ROUTER_SYSTEM_PROMPT` exist only to feed the
discarded call.

This is dead code by any reading, but removing it is a **latency and cost
change**, and "TEMPORARILY" suggests someone intends to switch it back on.
Options: (a) leave entirely, (b) leave the router but skip the call while the
edge is hard-wired (saves one LLM call per query — smallest change, real win),
(c) remove router + general-explanation node wholesale. I did not act on any of
these. **(b) is what I would do, but it is a behaviour change and therefore
yours to approve.**

---

## Proposed commit sequence (Phase 2), assuming H1=(b)

Each commit is followed by the two import checks.

1. `chore(rag): drop dead thanoy client and perf probe` — A1, A2
2. `chore(rag): drop the unreachable chain branch from /query` — B1, B2, B3
3. `chore(rag): drop ollama/use_local plumbing from the pipeline` — §C + the `test_core_llm_provider` local-mode test
4. `chore(rag): drop dead config constants and debug print` — A3, A4, A5
5. `docs(rag): correct comments the deletions and earlier refactors invalidated` — §D help text, §E, §G

If you pick H1=(a), commits 2 and 3 grow and a new commit lands between them
for `chain.py` + the `cross_lingual` translation half + the `__init__.py`
re-exports + `test_llm_content.py:207-229` + `PIPELINE_FILES` in
`test_core_llm_provider.py:13-20`.

---

## Note on the working tree

This branch carries three uncommitted files inherited from `main`:
`config.py` and `retrieval/reranker.py` (the double-sigmoid fix and the
`MITRE_TABLE_SCORE_THRESHOLD` recalibration note) and
`docs/HANDOFF_AND_CLEANUP.md`. Per your instruction they are untouched and
uncommitted. My `config.py` edits in Phase 2 will sit alongside them; the
threshold constant and its comment block stay exactly as they are.
