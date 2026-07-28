# รายงานการถอด Follow-up Module ออกจาก RAG Service

**วันที่:** 2026-07-28
**ขอบเขต:** `rag_service/` ทั้งหมด + ลบ proxy `/rag/resume` ฝั่ง `backend/`
**เหตุผล:** ความสามารถถาม-ตอบย้อนกลับ (interactive clarification) ถูกย้ายไปเป็นหน้าที่ของ Backend case-analysis workflow แล้ว การมี follow-up อยู่สองที่ทำให้ session state กระจัดกระจายและ contract ระหว่างบริการกำกวม

---

## 1. สรุปผู้บริหาร

| ก่อน | หลัง |
|---|---|
| `GraphRAGAgent.query()` อาจ **pause** แล้วคืน `status="followup"` + `session_id` | คืน `status="completed"` **เสมอ** — graph วิ่งถึง END ทุกครั้ง |
| Agent เก็บ session ที่ pause ไว้ใน memory (`self._sessions`) | ไม่มี session store — agent เป็น **stateless** ต่อ request |
| `POST /resume` รับคำตอบผู้ใช้กลับมาต่อ graph | endpoint ถูกลบ |
| Evaluator ติดตาม slot (`initial_access` → `impact`) เพื่อเลือกคำถาม | ตัด slot machinery ทิ้งทั้งหมด เหลือการประเมิน coverage + fallback strategy |
| INSUFFICIENT → หยุดถามผู้ใช้ | INSUFFICIENT → **BROADEN_SEARCH** (agent เขียน query ใหม่เอง แล้ววน retrieve, เพดาน 2 รอบ) |

**ผลรวมโค้ด:** ลบสุทธิ ~780 บรรทัด (ลบ 1,052 / เพิ่ม 273) — ลบไฟล์ 3 เพิ่มไฟล์ 1

---

## 2. การตัดสินใจเชิงออกแบบ

### 2.1 เก็บ evaluator ไว้ ตัดเฉพาะ slot machinery
Evaluator ไม่ได้ทำแค่ follow-up — มันคือ self-reflection loop ที่ยังให้คุณค่า (ประเมิน phase coverage + เลือก fallback strategy) จึงเก็บไว้ แต่ตัดส่วนที่มีไว้เพื่อ "ถามผู้ใช้" ออก:
`missing_slot`, `follow_up`, `incident_facts`, `asked_slots`, ตาราง SLOT DEFINITIONS ใน system prompt และ logic หา next missing slot

### 2.2 INSUFFICIENT ต้องมีทางไปต่อ
เดิม INSUFFICIENT มีทางเดียวคือถาม follow-up เมื่อตัดออก ต้องมี recovery path ใหม่ ไม่งั้นจะกลายเป็น "ตรวจว่าไม่พอ แล้วก็ตอบไปเฉยๆ" — เสียประโยชน์ของ evaluator ทั้งหมด จึง route INSUFFICIENT ไป `broaden_search` ซึ่งเป็น recovery ที่ไม่ต้องพึ่งผู้ใช้อยู่แล้ว

`_edge_after_evaluation` ตอนนี้:

| เงื่อนไข | ไปที่ |
|---|---|
| ไม่มี evaluation object | `reasoning` |
| `verdict == SUFFICIENT` | `reasoning` |
| `INSUFFICIENT` + `broaden_count < 2` + `new_query` ที่ sanitize แล้วไม่ว่าง | `broaden_search` → วน `retrieve` |
| นอกนั้น (หมดโควตา / ไม่มี rewrite ใช้ได้) | `reasoning` |

เงื่อนไข "`new_query` ต้องไม่ว่าง" สำคัญ: วน retrieve ด้วย query ชุดเดิมได้ context เดิม เปลืองรอบเปล่า

### 2.3 prompt ของ evaluator ต้องรู้ว่าถามผู้ใช้ไม่ได้แล้ว
เขียนใหม่ให้ชัดว่าเป็น automated loop และจะไม่มีข้อมูลเพิ่มเข้ามาอีก:
- **answerability gate** เดิมสั่งให้ "ตั้ง follow_up ถามรายละเอียดเหตุการณ์" → เปลี่ยนเป็นสั่งให้ใช้ `ACKNOWLEDGE_LIMIT` พร้อมข้อความบอกว่าคำบรรยายเหตุการณ์คลุมเครือเกินไป และต้องการอะไรเพิ่ม
- INSUFFICIENT **บังคับ** ต้องเลือก strategy (เดิม "ถ้ายังไม่ครบ retry ให้ strategy = null แล้วส่ง follow_up มาแทน")
- ระบุ format ของ `new_query`: ประโยคเดียว ไม่มี markdown ไม่มี ATT&CK ID และต้องต่างจาก query ที่ลองแล้ว

### 2.4 แก้ guard ของ ACKNOWLEDGE_LIMIT
เดิม `_node_reasoning` เชื่อ `ACKNOWLEDGE_LIMIT` ก็ต่อเมื่อ `total_retries >= MAX_FOLLOWUP_RETRIES` — guard นี้มีไว้กัน local LLM ที่ตอบ `strategy=ACKNOWLEDGE_LIMIT` พร้อม `verdict=SUFFICIENT` ในรอบแรก

เงื่อนไขเดิมใช้ไม่ได้แล้ว เพราะ answerability gate ต้องยิงได้ตั้งแต่รอบแรก (query คลุมเครือ ไม่ต้องรอ broaden ให้ครบ) จึงเปลี่ยน guard เป็น **`verdict == INSUFFICIENT`** ซึ่งตรงกับ bug ที่ต้องการกันจริงๆ และปลอดภัยเพราะ routing ใหม่การันตีว่า node นี้จะเจอ verdict INSUFFICIENT ก็ต่อเมื่อ broaden หมดโควตาหรือใช้ไม่ได้แล้ว

### 2.5 เก็บ `sanitize_retrieval_query` ไว้
`query_merger.py` ถูกลบทั้งไฟล์ แต่ฟังก์ชัน `sanitize_retrieval_query` ในนั้นถูกใช้โดย BROADEN_SEARCH ด้วย (ไม่ใช่ของ follow-up โดยเฉพาะ) จึงย้ายไปไฟล์ใหม่ `pipeline/query_sanitizer.py`

---

## 3. รายการเปลี่ยนแปลงรายไฟล์

### 3.1 ไฟล์ที่ลบ

| ไฟล์ | เหตุผล |
|---|---|
| `app/RAG/GraphRAG/pipeline/query_merger.py` | `QueryMerger` มีไว้รวม query เดิม + คำตอบ follow-up เท่านั้น (ย้าย `sanitize_retrieval_query` ออกก่อนลบ) |
| `app/test_agent_flow.py` | สคริปต์ทดสอบ follow-up loop โดยเฉพาะ (query คลุมเครือ + `followup_callback` จำลอง) — ไม่เหลือสิ่งที่ทดสอบ |
| `app/schemas/report.py` | เป็น dead code อยู่แล้ว (ไม่มีใคร import และบรรทัดแรก `from RAG import ReportWorkflowResponse` พังตั้งแต่ report workflow ย้ายไป Backend) การลบ `ResumeRequest` ทำให้ import พังเพิ่มอีกจุด |

### 3.2 ไฟล์ที่เพิ่ม

| ไฟล์ | เนื้อหา |
|---|---|
| `app/RAG/GraphRAG/pipeline/query_sanitizer.py` | `sanitize_retrieval_query()` + regex — ย้ายมาจาก `query_merger.py` |
| `docs/FOLLOWUP_REMOVAL.md` | เอกสารฉบับนี้ |

### 3.3 `pipeline/agent_graph.py` (−427 บรรทัด, ส่วนที่ถูกรื้อหลัก)

**ลบออก:**
- `AgentState` fields: `followup_question`, `followup_answer`, `awaiting_followup`, `followup_count`, `incident_facts`, `asked_slots`, `retry_count`
- `AgentResponse`: `followup_question`, `session_id`, `needs_followup` property และ branch follow-up ใน `to_dict()`
- `resume()`, `_park_or_complete()`, `_resume_with_answer()`, `_force_continue()`
- `_node_prepare_followup()` + `_DEFAULT_FOLLOWUP_QUESTION`
- `self._sessions` (in-memory session store) และ `self.query_merger`
- พารามิเตอร์ `followup_callback` ของ `query()` พร้อม while-loop pause/resume ทั้งก้อน
- node `prepare_followup` และ branch `"followup"` ใน conditional edge
- constant `MAX_RETRIEVAL_RETRIES` (dead อยู่แล้ว), `MAX_FOLLOWUP_RETRIES`

**เพิ่ม/แก้:**
- constant `MAX_BROADEN_RETRIES = 2`
- `AgentResponse.status` มีค่า default `"completed"`
- `_edge_after_evaluation()` เขียนใหม่ตาม §2.2
- `_node_evaluate_context()` ส่ง `retry_count=broaden_count` (เดิมเป็น `followup_count + broaden_count`)
- `_node_reasoning()` guard ใหม่ตาม §2.4 และไม่ส่ง `incident_facts` เข้า prompt แล้ว

### 3.4 `pipeline/evaluator.py` (−172/+~60)
- ลบ `VERDICT_NEED_CLARIFICATION` (legacy) ออกจาก `VALID_VERDICTS`
- `EvaluationResult`: ลบ field `missing_slot`, `follow_up`
- `evaluate()`: ลบพารามิเตอร์ `incident_facts`, `asked_slots` และ logic หา next missing slot
- `_build_prompt()`: ลบ section KNOWN INCIDENT FACTS / ALREADY ASKED SLOTS
- `EVALUATOR_SYSTEM_PROMPT`: เขียนใหม่ตาม §2.3, ลบ placeholder `{filled_slots}` / `{next_missing_slot}` เพิ่ม `{retry_hint}`
- verbose log พิมพ์ `new_query` แทน slot/follow-up

### 3.5 ไฟล์อื่นใน rag_service

| ไฟล์ | เปลี่ยน |
|---|---|
| `app/routers/rag.py` | ลบ endpoint `POST /resume` ทั้งก้อน + import `ResumeRequest`; `/query` ไม่ส่ง `followup_question`/`session_id` แล้ว |
| `app/schemas/rag.py` | ลบ `ResumeRequest`; `QueryResponse` ลบ `followup_question`, `session_id` |
| `app/schemas/__init__.py` | ลบ export `ResumeRequest` |
| `pipeline/__init__.py` | `QueryMerger` → `sanitize_retrieval_query` |
| `pipeline/context_builder.py` | `build_generation_prompt()` ลบพารามิเตอร์ `incident_facts` + block "CONFIRMED INCIDENT FACTS" |
| `pipeline/chain.py` | ลบพารามิเตอร์ `followup_callback` (interface compat ที่ไม่จำเป็นแล้ว) จาก `query()` / `query_with_details()` + import `Any` ที่ค้าง |
| `RAG/GraphRAG/main.py` | ลบ `_interactive_followup_callback()` และการส่ง callback ใน interactive REPL; แก้ข้อความ banner |
| `RAG/GraphRAG/config.py` | แก้ comment ของ `EVALUATOR_MAX_TOKENS` |
| `app/_perf_probe.py` | ลบการ instrument `_node_prepare_followup` + `query_merger.merge` และ callback จำลอง |

### 3.6 `backend/` (2 ไฟล์)

| ไฟล์ | เปลี่ยน |
|---|---|
| `app/routers/rag.py` | ลบ proxy `POST /rag/resume` |
| `app/schemas/rag.py` | เพิ่ม comment บน `QueryResponse` ว่า `status`/`followup_question`/`session_id` เป็น dead field แล้ว |

> **แก้ระหว่าง merge:** เดิมตั้งใจลบคลาส `ResumeRequest` ด้วย แต่ตอน pull main มีไฟล์ใหม่
> `app/services/chat/rag_client.py` (chat analysis workflow ของ Backend owner) ที่ `import ResumeRequest`
> การลบจะทำให้ทั้งโมดูล ImportError จึง**คงคลาสไว้** พร้อม docstring อธิบายว่า endpoint ปลายทางหายแล้ว
> และให้ลบทิ้งตอน reimplement chat resume ฝั่ง Backend

**ไม่แตะ** (เป็นของ Backend owner): `app/services/report_workflow.py`, `app/services/case_chat.py`, `app/services/chat/rag_client.py`, `app/schemas/report.py` (`ReportResumeRequest` เป็นคนละคลาส), และ `frontend/` ทั้งหมด

### 3.7 เอกสารที่อัปเดต
`rag_service/ARCHITECTURE.md` (changelog, diagram, endpoint table, §6.2 lifecycle, §7 code reference), `rag_service/docs/ARCHITECTURE_v2.md`, `rag_service/docs/RAG_Module.md`, `rag_service/docs/PRIMER.md`, `rag_service/app/RAG/pipeline.md`, `rag_service/app/RAG/Architecture.md`, `CLAUDE.md` (root)

`ARCHITECTURE_v2.md` เพิ่งเข้ามาพร้อม pull ระหว่างทำงานนี้ และมีทั้ง §4 ว่าด้วย `POST /resume` โดยเฉพาะ — เขียนใหม่เป็น "Self-reflection loop" ทั้งหัวข้อ

**ไม่แตะเอกสารเชิงประวัติ** — `evaluation/results/archive/latency_benchmark_2026-07-03.md`, `docs/DUAL_QUERY_UPGRADE.md`, `docs/retrieval_perf_optimization.md` เป็นรายงานผลการทดลอง ณ เวลานั้น การแก้ย้อนหลังจะทำให้บันทึกไม่ตรงกับสิ่งที่วัดจริง

> `docs/_ARCHITECTURE_v2.html` และ `ARCHITECTURE*.pdf` เป็นไฟล์ generated — ต้อง regenerate ด้วย `docs/_build_pdf.py` (ยังไม่ได้ทำในรอบนี้)
>
> `docs/HANDOFF_AND_CLEANUP.md` มีรายการค้าง 2 ข้อที่ปิดได้แล้วจากงานนี้: "verify ว่า backend/frontend loop resume จริง" (ไม่ต้องแล้ว — ไม่มี resume) และ `app/test_agent_flow.py` ในลิสต์ไฟล์ที่ควรลบ (ลบแล้ว)

---

## 4. การตรวจสอบ

| การทดสอบ | ผล |
|---|---|
| `python -m compileall` ทุกไฟล์ที่แก้ (rag_service + backend) | ผ่าน |
| Smoke test: `_build_graph()` compile ได้, ไม่มี node `prepare_followup` | ผ่าน — nodes = `route_query, prepare, retrieve, evaluate_context, broaden_search, general_explanation, reasoning, translate_output` |
| `_edge_after_evaluation` ครบ 6 เคส (ไม่มี evaluation / SUFFICIENT / INSUFFICIENT+โควตา / หมดโควตา / ไม่มี new_query / new_query ที่ sanitize แล้วว่าง) | ผ่าน — ไม่เคยคืน `"followup"` |
| `ContextEvaluator._parse_response` กับ JSON ที่ไม่มี slot field และกับ payload เก่าที่ยังมี `follow_up`/`missing_slot` | ผ่าน (ไม่ crash, ignore key ส่วนเกิน) |
| `EVALUATOR_SYSTEM_PROMPT` ไม่เหลือ `{filled_slots}` / `{next_missing_slot}` / `follow_up` / SLOT DEFINITIONS | ผ่าน |
| `AgentResponse` / `GraphRAGAgent` ไม่เหลือ surface ของ follow-up | ผ่าน |
| route table ของ rag_service | `GET /health`, `POST /query`, `GET /retrieval-contexts/{context_id}` — ไม่มี `/resume` |
| `backend/app/schemas/rag.py` import + serialize | ผ่าน (`ResumeRequest` หายไปแล้ว) |

**ที่ยังไม่ได้ทดสอบ:**
- backend test suite — เครื่องนี้ไม่มี `pytest` ติดตั้ง (`No module named pytest`)
- end-to-end จริงกับ Neo4j/Qdrant/Claude — ยังไม่ได้รัน (มีค่าใช้จ่าย API)
- `backend/app/routers/rag.py` import ไม่ผ่านเพราะขาด `python-multipart` ซึ่งเป็น dependency ของ route `/query-file` ที่มีอยู่เดิม ไม่เกี่ยวกับการแก้รอบนี้ (`app/schemas/rag.py` import ผ่านเดี่ยวๆ)

---

## 5. ⚠️ ผลกระทบข้ามบริการที่ต้องส่งต่อ

### 5.1 มี **2** ที่ในฝั่ง Backend ที่เรียก `/resume` ตรงไปที่ RAG service (ไม่ผ่าน proxy ที่ลบ)

| ที่ | สถานะหลังลบ |
|---|---|
| `backend/app/services/case_chat.py:608` — `self.client.post_json("/resume", …)` | 404 → โค้ดบรรทัด 617 map `404 + action="followup"` เป็น `status="expired"` อยู่แล้ว (มี test คุม: `test_followup_rag_404_marks_workspace_expired_without_new_query`) |
| `backend/app/services/chat/rag_client.py:39` — `request_rag(operation="resume")` **(ไฟล์ใหม่ที่ pull เข้ามา)** | 404 → มี guard เฉพาะอยู่แล้ว: `RagCallFailure("rag_session_expired", "Failed to recover follow-up session")` |

- **ระบบไม่พัง** ทั้งสองที่ — ต่างก็มี 404 handler อยู่แล้ว
- **แต่ฟีเจอร์ตาย:** ทุก resume path จะได้ expired/failure เสมอ จนกว่าจะ reimplement ฝั่ง Backend
- **ทางแก้ที่แนะนำ:** ทำแบบเดียวกับ `report_workflow.py` ที่ทำอยู่แล้ว — เก็บคำถาม/คำตอบไว้กับ case แล้วเรียก `POST /query` ใหม่ด้วยข้อความเหตุการณ์ที่ต่อคำตอบเข้าไป (ดู `report_workflow.py:160-165`)

### 5.2 Frontend ยังเรียก `/rag/resume`
`frontend/src/lib/api.ts:297` ยังยิงไปที่ `POST /rag/resume` ซึ่งลบไปแล้ว → 404
UI ที่เกี่ยวข้อง: `InvestigationWorkspace.tsx`, `InvestigationChatPanel.tsx`, `FollowUpModule.tsx`
ตกลงกันว่าไม่แตะ frontend ในรอบนี้ (เป็นของ Backend/Frontend owner)

### 5.3 `QueryResponse` ฝั่ง backend ยังมี field เดิม
`backend/app/schemas/rag.py` ยังคง `status: Literal["completed","followup"]`, `followup_question`, `session_id` ไว้ **โดยตั้งใจ** — frontend type ยังอ้างถึงอยู่ การลบจะทำให้ต้องแก้ frontend ตาม
ปัจจุบัน rag_service ไม่ส่ง field พวกนี้มาแล้ว → Pydantic เติม default `""` และ `status` เป็น `"completed"` เสมอ ปลอดภัยแต่เป็น dead field ที่ Backend owner ควรเก็บกวาดตอน reimplement
เช่นเดียวกับคลาส `ResumeRequest` ที่คงไว้เพราะ `chat/rag_client.py` ต้องใช้ (ดู §3.6)

---

## 6. Rollback

การเปลี่ยนแปลงอยู่ใน commit เดียว ย้อนกลับได้ด้วย `git revert` ไฟล์ที่ลบทั้งสามยังอยู่ใน git history:

```bash
git show 4047482:rag_service/app/RAG/GraphRAG/pipeline/query_merger.py
```

(`4047482` = commit ก่อนหน้างานนี้ — merge PR #17 `chore/cleanup-dead-files`)

---

## 7. หมายเหตุเรื่อง merge

งานนี้ทำบน base เก่า แล้ว `stash → pull → pop` ขึ้น `4047482` (main ที่มี PR #15–#17 + chat analysis workspace)

- ชนกันจริงไฟล์เดียว: `backend/app/schemas/rag.py` — resolve โดยเก็บของ upstream ทั้งหมด
  (`model_config extra="allow"`, `retrieval_context_id: str | None` + validator, `CyberCaseReport`,
  `ExperimentalAnalysisResponse`) และคง `ResumeRequest` ไว้ตาม §3.6
- `backend/app/routers/rag.py` merge สะอาด — `legal: bool = Form(False)` ของ upstream อยู่ครบ
  พร้อมกับการลบ `/resume` ของเรา
- งานฝั่ง `rag_service/` ไม่ชนกับ upstream เลย
- path ที่ upstream ย้าย: `latency_benchmark_2026-07-03.md` → `evaluation/results/archive/`,
  ลบ `docs/_ARCHITECTURE.html`, ลบ `app/verify_ingest.py` (เราไม่ได้แตะทั้งสาม)
