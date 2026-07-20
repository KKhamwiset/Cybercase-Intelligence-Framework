# CyberCase RAG Service — Architecture v2.0

> เอกสารนี้เขียนใหม่ทั้งหมดจากการอ่านซอร์สโค้ดปัจจุบันของ `rag_service/` (กรกฎาคม 2569)
> เน้น **สถาปัตยกรรม + diagram + design ที่เป็นปัจจุบัน** (single-call generation, multi-turn
> follow-up, batched retrieval, device-aware) — สำหรับรายละเอียดระดับ *ทุกฟังก์ชัน* ดู
> [`ARCHITECTURE.md`](../ARCHITECTURE.md) (per-function reference)

**การเปลี่ยนแปลงหลักจาก v1 → v2** (diagram v1 ยัง reflect ของเก่า):
- **Generation:** two-stage (reason EN → translate TH) → **single-call variant C** (call เดียว เขียนไทยเลย)
- **Follow-up resume:** คืน completed เสมอ → **multi-turn** (คืน followup รอบใหม่ได้)
- **Graph expansion:** วนทีละ seed (3N round-trip) → **batched** (3 UNWIND Cypher)
- **Model device:** fp16 hardcoded → **auto GPU/CPU** (fp16 เฉพาะ GPU)

---

## 1. บริบทระบบ (3 services)

`rag_service` เป็น FastAPI microservice (พอร์ต 8001) ที่โฮสต์ GraphRAG pipeline ทั้งหมด
Backend gateway เป็น proxy บางๆ ที่ forward RAG call มาที่นี่ผ่าน HTTP

```mermaid
flowchart LR
  FE["Frontend<br/>Next.js :3000"] --> BE["Backend Gateway<br/>FastAPI :8000<br/>users · reports · PostgreSQL"]
  BE -->|HTTP RAG_SERVICE_URL| RS["RAG Service :8001<br/>GraphRAG pipeline"]
  RS --> QD[("Qdrant Cloud<br/>BGE-M3 vectors<br/>entities + relationships")]
  RS --> NEO[("Neo4j Cloud<br/>MITRE ATT&CK<br/>STIX graph")]
  RS --> LLM["Claude Haiku<br/>Anthropic API"]
  RS -.->|optional| OLL["Ollama<br/>local models (--local)"]
```

**หลักภาษา (Language contract):** input เป็นสำนวนคดี**ไทย**เสมอ, output **ไทย**เสมอ;
context จาก MITRE เป็น**อังกฤษ** (ไม่แปล query ขาเข้า — BGE-M3 multilingual)

---

## 2. Tech stack & Models

| ชั้น | เทคโนโลยี | หมายเหตุ |
|---|---|---|
| API | FastAPI (lifespan โหลดโมเดล/ต่อ DB ครั้งเดียว) | `/query`, `/resume`, `/health`, `/retrieval-context/{id}` |
| Agentic engine | LangGraph `StateGraph` | node + conditional edges + in-memory session store |
| Embedding | `BAAI/bge-m3` (1024-d dense + sparse) | fp16 บน GPU / fp32 บน CPU |
| Vector DB | Qdrant Cloud (native RRF fusion) | collection: entities, relationships |
| Reranker | `BAAI/bge-reranker-v2-m3` (cross-encoder) | device-aware; คอขวด latency บน CPU |
| Graph DB | Neo4j Cloud (STIX 2.1) | Technique/Tactic/Group/Software/Campaign/Mitigation/DataComponent |
| LLM (reasoning/translation/eval) | Claude Haiku 4.5 (`LLM_MODEL`) | temp 0; local Ollama optional |

**Device selection:** `config.DEVICE` = cuda ถ้ามี GPU ไม่งั้น cpu; `USE_FP16 = (DEVICE=="cuda")`;
override `RAG_DEVICE=cpu|cuda`. **Production (Railway) = CPU** (torch CPU wheel + `python:3.11-slim`)

---

## 3. Request lifecycle — `POST /query` (agent)

```mermaid
flowchart TD
  START(["POST /query · use_agent=true"]) --> RQ["route_query"]
  RQ -->|incident| PREP["prepare<br/>lang detect · no input translation"]
  RQ -.->|"general (disabled)"| GE["general_explanation"] --> E1(["END"])
  PREP --> RET["retrieve<br/>decompose → retrieve_multi_quota → build_context"]
  RET --> EV{"evaluate_context"}
  EV -->|SUFFICIENT| RE["reasoning"]
  EV -->|INSUFFICIENT| FU["prepare_followup<br/>default question ถ้าว่าง"]
  FU --> PAUSE(["END — pause<br/>status=followup + session_id"])
  EV -->|BROADEN_SEARCH| BR["broaden_search"] --> RET
  RE -->|"single-call default: answer_is_final"| E2(["END — Thai answer"])
  RE -->|"two-stage: respond_in_thai"| TR["translate_output"] --> E3(["END — Thai answer"])
```

- **prepare:** ตรวจว่าตอบไทยไหม, ตั้ง `english_query = query` (ไม่แปลขาเข้า)
- **retrieve:** full query เป็น channel แรก + sub-queries (decompose) + rewrites → quota retrieval
- **evaluate_context:** LLM ประเมิน context พอไหม → SUFFICIENT / INSUFFICIENT / BROADEN_SEARCH
  (self-reflection loop, bounded `MAX_FOLLOWUP_RETRIES = 2`)
- **reasoning:** *single-call (default)* — `get_fast_system_prompt` เขียนไทยเลย ตั้ง `answer_is_final=True`
  → ข้าม translate_output; *two-stage* (`SINGLE_CALL_GENERATION=false`) — reason EN แล้ว translate_output → TH

---

## 4. Multi-turn follow-up — `POST /resume`

เมื่อ context ไม่พอ agent หยุดถาม follow-up (status=followup + session_id เก็บใน `_sessions`)
Frontend ส่งคำตอบกลับผ่าน `/resume` — **อาจถูกถามซ้ำได้หลายรอบ** (แก้ v2: `_park_or_complete`)

```mermaid
sequenceDiagram
  participant FE as Frontend/Backend
  participant RS as RAG Agent
  FE->>RS: POST /query (สำนวนคดีไทย)
  RS-->>FE: status=followup · session_id · Q1 (เช่น "เข้าถึงระบบยังไง?")
  FE->>RS: POST /resume (session_id, answer1)
  Note over RS: _resume_with_answer<br/>เก็บ slot + merge query + re-run graph<br/>→ _park_or_complete
  RS-->>FE: status=followup · session_id2 · Q2 (context ยังไม่พอ)
  FE->>RS: POST /resume (session_id2, answer2)
  RS-->>FE: status=completed · คำตอบไทย (≤ 2 รอบ แล้วบังคับตอบ)
```

> ⚠️ **Integration:** caller (backend proxy + frontend) ต้อง **loop `/resume` จนกว่า `status=="completed"`**
> ไม่ใช่สมมติว่า resume จบเสมอ — ยังไม่ได้ verify ฝั่ง backend/frontend (งานค้าง)

---

## 5. Retrieval subsystem

```mermaid
flowchart TD
  Q["Thai incident + rewrites"] --> DEC["QueryDecomposer<br/>→ atomic sub-queries (native lang)"]
  DEC --> RMQ["retrieve_multi_quota<br/>per-query quota + round-robin interleave"]
  subgraph perSubQuery["ต่อ sub-query"]
    VEC["VectorRetriever<br/>BGE-M3 dense+sparse → Qdrant RRF"] --> DOM["domain filter (enterprise)"]
    DOM --> RR["Reranker<br/>cross-encoder (device-aware)"]
    RR --> RW["reweight by node type<br/>(technique ลอยขึ้น)"]
  end
  RMQ --> perSubQuery
  RW --> SEED["รวม seed ข้าม sub-query (dedup)"]
  SEED --> EXP["GraphRetriever.expand_batch<br/>3 UNWIND Cypher (แทน 3N round-trip)"]
  EXP --> CTX["build_context → EN MITRE context (15 vec / 8 graph)"]
```

**Per-query quota** เก็บ top-k ของแต่ละ sub-query แล้ว round-robin → ทุก technique มีที่ใน context
(กัน final top-K ตัดทั้ง technique) · **batched expand** ลด Neo4j round-trip 3.5× (behavior-preserving)

---

## 6. Generation (single-call variant C)

```mermaid
flowchart LR
  CTX["EN MITRE context"] --> RE
  Q["Thai query"] --> RE
  RE{"SINGLE_CALL_GENERATION?"}
  RE -->|"true (default)"| SC["1 call: get_fast_system_prompt<br/>reason internally + write Thai<br/>answer_is_final=True"]
  RE -->|false| TS["2 calls: reason EN<br/>→ translate_output TH"]
  SC --> OUT["คำตอบไทย 4 หัวข้อ<br/>(ATT&CK ID/ชื่อ = อังกฤษ)"]
  TS --> OUT
```

**หลักฐาน (benchmark 45 sample):** single-call ≈ two-stage (ID-F1 Δ−0.011, CI คร่อม 0) แต่ latency ครึ่งเดียว,
token −44%; ชั้นแปลไม่เคยทำ ATT&CK ID หาย (id_survival = 1.0). 4 หัวข้อ: สรุปเหตุการณ์ / ลำดับการโจมตี /
เทคนิคที่ตรวจพบ / ผลกระทบ

---

## 7. Mapping — ตาราง MITRE ส่ง backend

`pipeline/mitre_table.build_mitre_table(rag_result, answer)` แปลง raw retrieval → ตาราง technique
ที่กรอง noise 2 ชั้น:
1. **Answer-grounded:** เก็บ entity ที่ ID/ชื่อโผล่ในคำตอบ (LLM เลือกให้ฟรี)
2. **Score threshold:** ตัด vector hit ที่ไม่ถูกอ้าง + คะแนน rerank ต่ำ; ทิ้ง graph neighbor ที่ไม่ถูกอ้าง

ผล eval: raw retrieval ~64 ID/ข้อ (precision 0.08) → ตารางกรอง ~8 ID/ข้อ (precision 0.40)

---

## 8. Evaluation pipeline (3 ชั้นบน gold เดียวกัน)

```mermaid
flowchart LR
  GOLD["gold ต่อ sample<br/>attack_steps (named/described)<br/>gold_attack_ids"]
  GOLD --> R["Retrieval<br/>step-coverage@k<br/>(named vs described)"]
  GOLD --> M["Mapping<br/>build_mitre_table vs gold<br/>P/R/F1 + threshold sweep"]
  GOLD --> G["Generation<br/>ID-F1 (partial credit)<br/>tactic F1 · guards · faithfulness"]
```

**Harness:** `crosslingual_generation_benchmark.py` — เทียบ 5 variant (A baseline / B +MT query /
C single-call / D Haiku translator / E EN ceiling) บน **frozen context**, 3 เฟส resumable
(`retrieve` / `generate` / `score` + `score-mapping` + `score-retrieval`), paired bootstrap CI + Wilcoxon

**Dataset:** สำนวนคดีไทยเรียงเวลา — 45 group-sourced + 20 campaign-sourced (เหตุการณ์จริง เช่น SolarWinds
C0024, Operation Dream Job C0022) สร้างโดย `make_incident_dataset.py` (kill-chain + named/described cue);
lookup dataset เดิมโดย `generate_eval_dataset.py` (graph = ground truth)

---

## 9. Configuration & Deployment

| หมวด | ค่า/ตัวแปร |
|---|---|
| Generation | `SINGLE_CALL_GENERATION=true` (default) |
| Device | `DEVICE` (auto), `USE_FP16=(cuda)`, override `RAG_DEVICE=cpu\|cuda` |
| Retrieval | `VECTOR_TOP_K=10`, `FINAL_TOP_K=5`, `GRAPH_EXPANSION_DEPTH=2`, `ATTACK_DOMAIN_FILTER=enterprise` |
| LLM | `LLM_MODEL=claude-haiku-4-5`, `LLM_TEMPERATURE=0` |
| Follow-up | `MAX_FOLLOWUP_RETRIES=2` |
| Deploy | Docker (`python:3.11-slim`, torch CPU wheel) → **Railway = CPU inference** |

**คอขวด latency บน production (CPU):** cross-encoder reranker (~7-8s/sub-query) — batch ไม่ช่วย
(พิสูจน์แล้ว); งานปรับปรุงคนละก้อน (ลด sub-query / reranker เล็กลง / GPU host)

---

## 10. โครงสร้างไดเรกทอรี (rag_service/app/RAG/GraphRAG)

```
config.py                 # DEVICE/USE_FP16, SINGLE_CALL_GENERATION, model/DB settings
pipeline/
  agent_graph.py          # LangGraph state machine (query/resume, _park_or_complete)
  chain.py                # linear LCEL (legacy, two-stage; ใช้ใน eval generation)
  cross_lingual.py        # prompts: reasoning / translation / fast / ultrafast
  context_builder.py      # build_context, build_generation_prompt
  evaluator.py            # context sufficiency + slot-aware follow-up
  query_decomposer.py     # incident → atomic sub-queries
  query_merger.py         # merge follow-up answer → MITRE-aligned rewrite
  mitre_table.py          # answer-grounded MITRE mapping table
  router.py               # general vs incident (ปิดชั่วคราว)
retrieval/
  hybrid_retriever.py     # retrieve / retrieve_multi / retrieve_multi_quota
  vector_retriever.py     # BGE-M3 + Qdrant hybrid RRF
  reranker.py             # cross-encoder (device-aware)
  graph_retriever.py      # expand_batch (batched Neo4j)
ingestion/                # STIX parse → Neo4j + Qdrant
evaluation/               # metrics, benchmark harness, dataset builders (ดู §8)
```

---

## 11. อ้างอิงเพิ่มเติม
- [`ARCHITECTURE.md`](../ARCHITECTURE.md) — per-function reference ทุกไฟล์ (รายละเอียดระดับฟังก์ชัน)
- [`docs/retrieval_perf_optimization.md`](retrieval_perf_optimization.md) — งาน batched expand + device (CPU/GPU)
- `evaluation/results/` — รายงาน benchmark (generation / mapping / retrieval)
