# สรุปงาน Cleanup — `rag_service/`

> **branch:** `chore/rag-service-cleanup` → merge เข้า `main` แล้ว (`d226bef`)
> **วันที่:** 15 สิงหาคม 2569
> **ขอบเขต:** ลบ dead code + แก้คอมเมนต์ให้ตรงความจริง — ไม่ปรับโครงสร้าง ไม่เปลี่ยนชื่อ ไม่เพิ่ม abstraction

---

## 1. ภาพรวม

| หัวข้อ | จำนวน |
|---|---|
| commit (ไม่รวม merge) | 6 |
| ไฟล์ที่ถูกแตะ | 21 |
| ลบทั้งไฟล์ | 4 ไฟล์ / 361 บรรทัด |
| รวมบรรทัดที่ลบ | 638 |
| รวมบรรทัดที่เพิ่ม (ส่วนใหญ่คือคอมเมนต์ที่แก้ให้ถูก) | 205 |
| **สุทธิ** | **−433 บรรทัด** |

**ผลทดสอบหลัง merge:** `rag_service` 32 passed · `backend` 171 passed + 26 subtests
**ด่านตรวจทุก commit:** `python -c "import main"` และ `python -c "from RAG import GraphRAGAgent"` ผ่านทั้งคู่

### เหตุผลตั้งต้น

โค้ดสะสมสามอย่างจากการ refactor หลายรอบ: เส้นทางที่ไม่มีใครเรียกถึงแล้ว, flag ของฟีเจอร์ที่เลิกใช้, และคอมเมนต์ที่บรรยายพฤติกรรมเก่า งานนี้แบ่งเป็น 2 เฟส — เฟส 1 สำรวจอย่างเดียวไม่แก้โค้ด (ผลลัพธ์คือ `CLEANUP_INVENTORY.md`) เฟส 2 ค่อยลบจริง

การแยกเฟสคุ้มมาก เพราะเฟส 1 พบว่าสามในสี่ข้อสมมติฐานตั้งต้น **ไม่ตรงกับโค้ดจริง** ถ้าลบเลยตั้งแต่แรกจะพังสามจุด (ดู §5)

---

## 2. ลบอะไรบ้าง

### 2.1 ลบทั้งไฟล์

| ไฟล์ | บรรทัด | เหตุผล |
|---|---|---|
| `pipeline/thanoy_client.py` | 105 | client ของ Thanoy (AI กฎหมายไทย จาก iApp) ไม่มีใคร import เลยทั้ง repo — ไม่อยู่ใน `pipeline/__init__.py` ไม่มี router เรียก เขียนไว้สำหรับส่วน "คำแนะนำทางกฎหมาย" ของรายงานที่ backend ไม่เคยสร้างขึ้นมา |
| `howtothanoy.md` | 115 | คู่มือตั้งค่าของ client ข้างบน |
| `app/_perf_probe.py` | 141 | สคริปต์วัด perf ที่ระบุตัวเองว่า throwaway ไม่อยู่ใน allowlist `COPY` ของ Dockerfile จึงไม่เคยขึ้น production และไปเรียก `GraphRetriever._expand_single` ซึ่งเป็น private |

### 2.2 เส้นทาง chain ที่ไม่มีใครเรียกถึง

`QueryRequest.use_agent` มีค่า default เป็น `True` และ `backend/app/services/chat/rag_client.py` ก็ hard-code `use_agent=True` ทุกครั้งที่เรียก แปลว่าครึ่ง chain ของ `query_rag()` ไม่มีทางถูกเรียกถึง

- ลบ chain branch ออกจาก `POST /query`
- ลบ `print("Agent requested")` ที่หลงเหลือ
- ลบ `rag_chain` ออกจาก startup ใน `app/main.py`
- ลบ key `rag_chain` ออกจาก `/health`
- ลบ re-export `ChainResponse` / `GraphRAGChain` ออกจาก `__init__.py` 3 ไฟล์

**ผลพลอยได้ที่ใหญ่กว่าที่คาด:** เดิม service สร้าง **ทั้ง** `GraphRAGChain` และ `GraphRAGAgent` ตอน boot แต่ละตัวเปิด Neo4j driver ของตัวเอง, Qdrant client ของตัวเอง และ chat model อีกคู่หนึ่ง ตอนนี้เหลือชุดเดียว

### 2.3 Ollama / `use_local` ออกจากเส้นทางที่ให้บริการ

`USE_LOCAL` default เป็น false และไม่ได้ตั้งไว้ทั้งใน `docker-compose.yml` และ `deploy.yml` แปลว่า service ไม่เคยสร้าง `ChatOllama` เลย

ลบออกจาก: `GraphRAGAgent`, `ContextEvaluator`, `app/main.py` (รวม `llm_mode` ที่พิมพ์ว่า "LOCAL (Ollama)" ซึ่งไม่มีทางเป็นจริง) และ config `USE_LOCAL`

### 2.4 ค่าคงที่และ schema ที่ตายแล้ว

| สิ่งที่ลบ | ที่อยู่ | เหตุผล |
|---|---|---|
| `CHROMA_DIR`, `CHROMA_HOST`, `CHROMA_PORT`, `CHROMA_SSL`, `CHROMA_API_KEY`, `CHROMA_COLLECTION_*` | `config.py` | ตกค้างจากยุคก่อนย้ายไป Qdrant ไม่มีใครอ่าน |
| `GRAPH_EXPANSION_DEPTH` | `config.py` | ไม่มีใครใช้ — `GraphRetriever` รับ depth เป็น argument |
| `THANOY_API_KEY`, `THANOY_API_URL`, `THANOY_TIMEOUT`, `THANOY_ENABLED` | `config.py` | ป้อนให้ client ที่ลบไปแล้ว |
| `print(ATTACK_DOMAINS.items())` | `config.py` | debug print ระดับ module — ยิงทุกครั้งที่ import รวมถึงใน container และทุกครั้งที่รัน test |
| `ReviewStatusRequest` | `schemas/rag.py` | ไม่มี router ใช้ — RAG service ไม่มี endpoint review |
| ตัวแปร `gap_warning` ที่อ่านมาแล้วไม่ใช้ | `agent_graph.py` | ดู §4 |

> **หมายเหตุ:** บล็อกคอมเมนต์ `LEGACY` ของ E5 และ mmarco reranker **เก็บไว้** เพราะเป็นบันทึกการตัดสินใจ ไม่ใช่โค้ด — ต่างจาก `CHROMA_*` ที่เป็นชื่อจริงที่ import ได้ ซึ่งเป็นช่องทางให้ dead config ถูกหยิบกลับมาใช้โดยไม่ตั้งใจ

---

## 3. แก้อะไรบ้าง

### 3.1 คอมเมนต์ในโค้ด

| ที่อยู่ | เดิมบอกว่า | ความจริง |
|---|---|---|
| `cross_lingual.py` docstring | pipeline 3 stage: แปล → reason → แปล | stage 1 หายไปจากเส้นทางที่ให้บริการแล้ว เขียนใหม่โดยแยกชัดว่าส่วนไหน agent ใช้ ส่วนไหนเหลือไว้ให้ `chain.py` + `evaluation/` |
| `get_fast_system_prompt()` | "prompt สำหรับโหมด `--fast`" | เป็น **prompt หลักของ production** — `SINGLE_CALL_GENERATION` เปิดโดย default ทำให้ reasoning node ของ agent ใช้ตัวนี้ คอมเมนต์นี้หลอกที่สุดในโค้ดชุดนี้ |
| `agent_graph.py` docstring | "Replaces the linear LCEL chain" / "Drop-in companion for `GraphRAGChain`" | อ้างถึงสิ่งที่ไม่ใช่ของคู่กันแล้ว |
| `_node_reasoning` docstring | "Stage 2 … สังเคราะห์เป็นคำตอบภาษาอังกฤษ" | เส้นทางจริงเขียนภาษาไทยจบในครั้งเดียว |
| `AgentState` หัวข้อ `── Translation ──` | คร่อม `english_query` | ไม่มีอะไรถูกแปล — field นี้ copy query เดิมมาตรง ๆ คอมเมนต์ใหม่บอกด้วยว่าทำไมยังใช้ชื่อเดิม (evaluator ผูกกับมันอยู่) |
| `config.py` คอมเมนต์ reranker | "ต้องรับคู่ไทย-อังกฤษ ตอน `DUAL_QUERY_RETRIEVAL` เปิด" | agent ไม่เคยอ่าน flag นั้น — ที่เป็นคู่ข้ามภาษาเพราะ **ไม่มีการแปล input เลย** ต่างหาก |
| `config.py` เส้นทาง STIX | ไม่มีคำอธิบาย | เพิ่มบันทึกว่าทำไมต้องมี existence check (ใน Docker image bundle อยู่ที่ `rag_service/` แต่ใน repo อยู่ระดับ root) |
| `main.py` (CLI) | `python main.py --ingest` | คำสั่งนี้พังด้วย `ImportError` — package ใช้ relative import ต้องรันด้วย `-m` |
| `run_ingest()` docstring | "load into Neo4j + **ChromaDB**" | โหลดเข้า Qdrant |
| `--agent` / `--fast` help | "…with self-reflection and **follow-up**" | โมดูล follow-up ถูกลบไปแล้ว |

### 3.2 `CLAUDE.md`

| เดิม | แก้เป็น |
|---|---|
| "LangGraph (agentic loop) + LangChain **LCEL**" | LangGraph ทำ orchestration, LangChain ให้ abstraction ของ LLM และ message — และระบุชัดว่า **LangGraph เป็นคนละ library ไม่ใช่ส่วนหนึ่งของ LangChain** ส่วน LCEL เหลือใช้เฉพาะ evaluation |
| diagram มี stage `[CROSS-LINGUAL] Translate query to English` | stage นั้นไม่มีจริง วาดใหม่ให้ตรงโค้ด — เพิ่ม `[PREPARE]` (ตรวจภาษาอย่างเดียว) กับ `[DECOMPOSE]` + quota retrieval ที่ทำงานจริงแต่ไม่เคยถูกเขียนถึง |
| `--local` เป็น flag ของ RAG CLI | ไม่เคยมีอยู่จริง — มีเฉพาะสคริปต์ใน `evaluation/` |
| Reasoning LLM = `claude-sonnet-4-20250514` | default จริงคือ OpenRouter `openai/gpt-5.6-luna` (ตั้ง `CORE_LLM_PROVIDER=anthropic` ถึงจะได้ `claude-haiku-4-5`) |
| เตือนว่า `--ingest` หาโฟลเดอร์ STIX ผิดที่ | **แก้ไปแล้วในโค้ด** — ลบคำเตือนทิ้ง (ดู §5.3) |

### 3.3 เอกสารไทยชุดใหญ่

`ARCHITECTURE.md`, `docs/RAG_Module.md`, `docs/ARCHITECTURE_v2.md`, `docs/PRIMER.md` มี reference ถึง `use_local` / Ollama / `GraphRAGChain` อยู่หลายสิบจุด การเขียนใหม่ทั้งหมดใหญ่เกินขอบเขตงานนี้

เอกสารพวกนี้**ประกาศตัวเองว่าถอดมาจากซอร์สโค้ดปัจจุบัน** การปล่อยเงียบไว้จึงเป็นทางเลือกที่หลอกกว่า — ใส่ banner ระบุวันที่ตรวจและลิสต์จุดที่ไม่ตรงแล้วแทน (ไฟล์ `.pdf` ที่ generate คู่กันก็เก่าตามไปด้วย)

---

## 4. สิ่งที่จงใจเก็บไว้ (และทำไม)

งานนี้เจอหลายอย่างที่ "ดูเหมือนตาย" แต่จริง ๆ ยังมีคนใช้

### `chain.py` + ครึ่ง translation ของ `cross_lingual.py`

`evaluation/eval_runner.py --mode generation` และ `evaluation/crosslingual_benchmark.py` สร้าง `GraphRAGChain` ตรง ๆ และเป็น baseline ที่ใช้วัด agent อยู่ ส่วน `evaluation/` ถูกกันไว้ไม่ให้แตะเพราะมีงานค้างบน branch `eval/real-cti-dataset`

วิธีจัดการ: เก็บไฟล์ไว้ แต่**ถอดออกจาก `pipeline/__init__.py`** เพื่อไม่ให้การ import package ลากมันมาด้วย แล้วเขียน header บอกตรง ๆ ว่าเป็น evaluation-only และการปลดระวางต้องย้าย `eval_runner` มาใช้ `GraphRAGAgent` ก่อน

### stage แปลเป็นไทย (`_node_translate_output`)

ยังเรียกถึงได้จริง เพราะ `_node_reasoning` มีทางออก 3 ทาง แต่มีแค่ทางเดียวที่ set `answer_is_final`:

| เส้นทาง | `answer_is_final` | ผล |
|---|---|---|
| query ไทย + reasoning ปกติ | `True` | ข้าม translate ← เส้นทางหลัก |
| `ACKNOWLEDGE_LIMIT` (evaluator ยอมแพ้) | ไม่ถูก set → `False` | **translate ทำงานจริง** |
| ไม่มี `reasoning_llm` (ไม่มี API key) | ไม่ถูก set → `False` | translate ถูกเรียกแต่เป็น no-op เพราะ `translation_llm` ก็เป็น `None` พร้อมกัน |

เส้น `ACKNOWLEDGE_LIMIT` คืนข้อความของ evaluator ตรง ๆ โดยไม่เรียก LLM เขียนคำตอบ และข้อความนั้นไม่การันตีว่าเป็นภาษาไทย (system prompt ของ evaluator เป็นอังกฤษ) — stage แปลจึงทำหน้าที่เป็นตาข่ายกันพลาด นอกจากนี้ `SINGLE_CALL_GENERATION=false` ก็ปลุกเส้นทาง two-stage กลับมาทั้งเส้น

### Ollama ใน config + `langchain-ollama`

**ในเส้นทางที่ให้บริการ ไม่เหลือแล้ว** แต่ `OLLAMA_BASE_URL`, `LOCAL_LLM_MODEL`, `LOCAL_EVAL_MODEL`, `LOCAL_NUM_CTX` ต้องอยู่ต่อ เพราะยังมีผู้ใช้ 6 จุดใน `evaluation/` + `finetune/`:

- `generation_metrics.py:152` — `OllamaEmbeddings("nomic-embed-text")` สำหรับ RAGAS `answer_correctness` **ไม่ได้ gate ด้วย `--local`** (เดิมใช้ OpenAI embeddings แล้วโดน 429 → ได้ `nan` แถม retry ค้างทั้ง run)
- `crosslingual_generation_benchmark.py:398` — local arm ของ A/B เทียบ fine-tune
- `chain.py`, `cross_lingual.py`, `query_decomposer.py`, `router.py` — branch `if use_local:` ที่ตอนนี้เปิดได้จาก evaluation/finetune เท่านั้น

> **ข้อควรรู้:** RAGAS **judge** เป็น cloud อยู่แล้ว (Claude Haiku → OpenRouter) Ollama ที่เหลือทั้งหมดไม่ใช่ judge

### อื่น ๆ

`MITRE_TABLE_SCORE_THRESHOLD`, `_TYPE_WEIGHTS`, `retrieve_multi_quota()` — ตามที่สั่งไว้ว่ารอการตัดสินใจ
`query_fast` / `query_ultrafast` — ยังทำงานได้ เป็นเครื่องมือทดลอง latency โดยตั้งใจ
`backend/` — ไม่แตะเลยสักไฟล์

---

## 5. เรื่องที่พบระหว่างทาง

### 5.1 มี behaviour change หนึ่งจุด

`python -m RAG.GraphRAG.main` เปล่า ๆ เดิมรัน **chain** ตอนนี้รัน **agent**

จำเป็นต้องทำ เพราะถ้าไม่ทำ CLI จะกลายเป็นที่เดียวที่ยังลากโมดูล evaluation-only เข้ามาใน `app/` ซึ่งขัดกับ header ที่เพิ่งเขียนไว้ใน `chain.py` เอง ส่วน `--agent` ยังรับได้แต่เป็น no-op เพื่อไม่ให้ script เดิมพัง

### 5.2 `PARTIAL_ANSWER` ไม่ได้ต่อสาย

evaluator มี strategy ตัวที่สามชื่อ `PARTIAL_ANSWER` (ตอบเท่าที่มี + เตือนว่าข้อมูลขาดตรงไหน) แต่ `agent_graph.py` **ไม่มีที่ไหนเช็ค** และ `gap_warning` ที่อุตส่าห์ส่งมาก็ถูกอ่านเก็บไว้แล้วไม่ใช้ต่อ — ผู้ใช้ไม่เคยเห็นคำเตือนนั้น

docstring เดิมเขียนว่า *"PARTIAL_ANSWER / ACKNOWLEDGE_LIMIT are then honoured downstream"* ซึ่งจริงครึ่งเดียว

งานนี้ลบเฉพาะตัวแปรที่ตายและแก้ docstring ให้บอกตรง ๆ — การต่อสายให้ทำงานจริงเป็น **feature ไม่ใช่ cleanup** จึงปล่อยไว้ให้ตัดสินใจ

### 5.3 ปัญหา STIX ingestion แก้ไปแล้ว

`CLAUDE.md` เตือนว่า `--ingest` หาโฟลเดอร์ STIX จาก `_PROJECT_ROOT` ซึ่งชี้ไป `rag_service/` แต่ bundle อยู่ที่ repo root — **ไม่จริงแล้ว** `config.py` มี fallback เช็ค existence อยู่ ยืนยันด้วยการ import จริง: `ATTACK_DOMAINS` ชี้ไป `…/Mitre_ATT&CK Doc/enterprise-attack` ที่มีอยู่จริง

ไม่ต้องแก้โค้ด แค่ลบคำเตือนที่ล้าสมัยและเพิ่มบรรทัดอธิบายว่าทำไมต้องมี fallback

### 5.4 การ merge กับ `main` — เกือบพัง 3 จุด

ระหว่างทำงาน `main` เดินหน้าไป 6 commits และ **ลบ chain branch ออกจาก `/query` ไปเองแล้ว** โดยไปไกลกว่า: ตัด field `answer` ออกจาก HTTP boundary ทั้งหมด (เหลือ `context` + `mitre_table`) และใส่ `extra="forbid"` ทุก schema

conflict มี 2 ไฟล์ ต้องแก้ด้วยมือ 3 จุด:

1. **auto-merge สร้างบั๊กเงียบ** — git เอา `from typing import Any` ของ branch มารวมกับ `Literal["completed"]` ของ main → `NameError` ตอน import คือ service ไม่ขึ้นเลย
2. **`use_agent` ต้องเอากลับมา** — เหตุผลเดิมที่ลบได้คือ pydantic เมิน field แปลกปลอม แต่ `extra="forbid"` ของ main ทำให้เหตุผลนั้นใช้ไม่ได้ ถ้าปล่อยไปตามเดิม backend ที่ยังส่ง `use_agent: true` จะโดน **422 ทุก request**
3. **`/health`** — main ลบ chain ออกจาก router แล้ว แต่ `/health` ยังอ่าน `app.state.rag_chain` และ `app/main.py` บน main ก็ยังสร้าง `GraphRAGChain` ทิ้งไว้เฉย ๆ งานนี้ปิดทั้งสองฝั่งให้ตรงกัน

### 5.5 ปัญหาที่ไม่เกี่ยวกับงานนี้

`cd backend && pytest tests` **collection พังทั้ง suite** เพราะโฟลเดอร์ `backend/alembic/` (ไม่มี `__init__.py` ไม่มี `config.py`) ไปบัง package `alembic` ที่ติดตั้งไว้ ทำให้ `from alembic.config import Config` หาไม่เจอ ต้องใช้ `--ignore` ถึงจะรันได้

ยืนยันว่ามีอยู่บน `main` ก่อนแล้ว — branch นี้ไม่มี commit ที่แตะ `backend/` เลย

---

## 6. งานที่ยังค้าง

| เรื่อง | สถานะ |
|---|---|
| ลบ `chain.py` ทิ้งจริง | เลื่อนไว้ตามที่ตัดสินใจ — ต้องย้าย `eval_runner --mode generation` มาใช้ `GraphRAGAgent` ก่อน ซึ่งจะทำให้ตัวเลข eval เปลี่ยน |
| ตัด Ollama ออกจาก `evaluation/` + `finetune/` | รอ `eval/real-cti-dataset` merge ก่อน · ต้องหา embeddings แทน `nomic-embed-text` (BGE-M3 ที่โหลดอยู่แล้วน่าจะเหมาะสุด) และตัดสินใจเรื่อง local arm ของ fine-tune A/B |
| `query_fast` / `query_ultrafast` (~140 บรรทัด) | ยังไม่ตัดสิน — เรียกได้จาก CLI เท่านั้น ไม่มี HTTP route ถ้าถือว่าการทดลอง latency จบแล้ว นี่คือก้อนใหญ่อันดับสองที่ตัดได้ และตัดได้แบบไม่กระทบใคร |
| router ที่ยิง LLM แล้วทิ้งคำตอบ | ยังไม่ตัดสิน — `_edge_after_route` ถูก hard-wire ให้คืน `"incident"` เสมอ แต่ `_node_route_query` ยังเรียก LLM ทุก request แล้วโยนผลทิ้ง (มีคอมเมนต์ `TEMPORARILY DISABLED ROUTER`) การข้ามการเรียกนี้ประหยัด LLM call ได้ 1 ครั้งต่อ request แต่เป็น behaviour change |
| ต่อสาย `PARTIAL_ANSWER` | เป็น feature ไม่ใช่ cleanup |
| แก้ `backend/alembic` ที่บัง package | ตั้ง task แยกไว้แล้ว |

---

*รายละเอียดเต็มของการสำรวจเฟส 1 พร้อมหลักฐาน grep ว่าใครเรียกใช้อะไรบ้าง อยู่ใน `rag_service/docs/CLEANUP_INVENTORY.md`*
