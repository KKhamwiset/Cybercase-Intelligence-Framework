# Handoff & Cleanup Plan — rag_service

> ไฟล์นี้สรุป **สถานะปัจจุบัน** (สำหรับ session ถัดไปอ่านให้จบก่อนเริ่ม) + **แผนสังคายนาไฟล์รก**
> ปรับปรุงล่าสุด: 2026-07 · ทุกอย่างด้านล่างอยู่บน `origin/main` แล้ว (ผ่าน PR #12–#15)

---

## 1. สถานะปัจจุบัน — อ่านตรงนี้ก่อน

**Production pipeline (main):**
- **Generation = single-call (variant C):** query ไทย → reason บน EN context + เขียนไทยใน call เดียว
  (ตั้ง `answer_is_final=True` ข้าม translate_output). flag `SINGLE_CALL_GENERATION=true` (default);
  `=false` กลับ two-stage. พิสูจน์ด้วย benchmark: คุณภาพเท่าเดิม latency ครึ่งเดียว
- **Follow-up = multi-turn:** `resume()` คืน `status="followup"` ได้หลายรอบ (`_park_or_complete`)
  ⚠️ **ยังไม่ verify ฝั่ง backend/frontend ว่า loop resume จริง** (งานค้าง)
- **Retrieval:** batched Neo4j expansion (`graph_retriever.expand_batch`, 3.5× ที่ชั้น expand)
- **Device:** auto GPU/CPU, `USE_FP16=(cuda)`, override `RAG_DEVICE`. **Prod Railway = CPU**

**เอกสารสถาปัตยกรรม:**
- `docs/ARCHITECTURE_v2.pdf` / `.md` — สถาปัตยกรรม + diagram ปัจจุบัน (อ่านอันนี้)
- `ARCHITECTURE.md` (root) — per-function reference ทุกไฟล์ (อัปเดตแล้ว)
- `docs/retrieval_perf_optimization.md` — งาน batched expand + device (CPU/GPU)

**Evaluation:**
- Harness: `evaluation/crosslingual_generation_benchmark.py` (5 variant, 3 เฟส, mapping/retrieval scoring)
- Metrics: `retriever_metrics.py` (step-coverage@k), `attack_id_metrics.py` (ID-F1 + guards)
- Dataset (draft, **รอ human review**): `data/incident_draft.json` (45 group) +
  `data/incident_draft_campaign.json` (20 campaign จริง เช่น SolarWinds C0024) — ID ต่างกัน รวมเป็น 65 ได้

**งานค้าง (task #6):** รีวิว 20 campaign samples → รวม dataset 65 → faithfulness judge →
ตัดสิน `MITRE_TABLE_SCORE_THRESHOLD` 0.62→0.70 · integration: verify backend/frontend loop resume

---

## 2. แผนสังคายนา (Cleanup) — ทำ session แยก

### กฎเหล็ก (กัน main ระเบิด)
1. **ห้ามลบบน main ตรงๆ** — สร้าง branch `chore/cleanup-dead-files`
2. **tag restore point ก่อนเริ่ม:** `git tag pre-cleanup-2026-07 && git push origin pre-cleanup-2026-07`
   (git history เก็บทุกอย่างอยู่แล้ว — revert merge ก็กู้ได้ — tag แค่ทำให้จุดกู้ชัด)
3. **verify ก่อนลบทุกไฟล์:** `grep -rn "<stem>\|<ClassName>" rag_service --include=*.py | grep -v __pycache__`
   ถ้ามี reference จากที่อื่น = **อย่าลบ** (refactor reference ก่อน หรือเก็บไว้)
4. **verify หลังลบ:** `python -m py_compile` ทุกไฟล์ + `python evaluation/test_metrics.py` +
   import `agent_graph`/`main` ได้ + smoke query 1 ครั้ง — **แล้วค่อย PR**
5. Merge ผ่าน PR (ให้ CI/reviewer จับพัง) — ถ้าอะไรพัง main ไม่เคย merge = ปลอดภัย

### Candidate ที่ควรพิจารณาลบ (ต้อง verify usage ก่อน)

| กลุ่ม | ไฟล์ | หมายเหตุ |
|---|---|---|
| **Eval dataset ซ้ำ/ไม่ใช้** (เป้าใหญ่ ~10MB) | `evaluation/eval_dataset_0x01.json`, `eval_dataset_unused.json`, `eval_dataset_generated.json`, `Thai_dataset.json`, `Thai_dataset_08.json` | หลายอันซ้ำ/ชื่อบอก unused; เช็คว่า eval_runner/benchmark ชี้ไฟล์ไหนจริง |
| **Eval harness เก่า** | `evaluation/crosslingual_benchmark.py` | น่าจะถูกแทนด้วย `crosslingual_generation_benchmark.py` — grep ยืนยัน (พบ ref 1 ไฟล์) |
| **App scratch/utility** | `app/_perf_probe.py`, `app/test_agent_flow.py`, `app/verify_ingest.py`, `app/download_model.py` | utility รันครั้งเดียว — เช็คว่ายังจำเป็นไหม |
| **Docs build byproducts** | `docs/_ARCHITECTURE.html`, `docs/_ARCHITECTURE_v2.html` | สร้างจาก `_build_pdf.py` ทุกครั้ง → ควร **gitignore** ไม่ใช่ track |
| **Docs เก่า/ซ้ำ** | `docs/RAG_Module.md/.pdf`, `docs/DUAL_QUERY_UPGRADE.md` | RAG_Module ถูกแทนด้วย ARCHITECTURE; เช็คว่ายังอ้างถึงไหม |
| **Root result dumps** | `results.md`, `results_haiku.md`, `results_thai08.md`, `latency_benchmark_2026-07-03.md` | ผลรันเก่า — ย้ายเข้า `evaluation/results/` หรือลบ |
| **Reference dead code** | `graph_retriever._expand_single` | เก็บไว้เป็น equivalence reference ของ `expand_batch` — ลบได้ถ้าไม่ต้องการ (มี test อ้าง 2 ไฟล์) |

### ❌ ห้ามลบ (ยืนยันว่าใช้จริง)
- **`pipeline/chain.py` / `GraphRAGChain`** — ถูก import **8 ไฟล์** (eval generation + non-agent path) **ใช้จริง**
- pipeline nodes, retrieval/*, ingestion/* — core
- `evaluation/attack_id_metrics.py`, `retriever_metrics.py`, `crosslingual_generation_benchmark.py`,
  `make_incident_dataset.py`, `generate_eval_dataset.py` — eval ปัจจุบัน

---

## 3. Prompt สำหรับ session สังคายนา (คัดลอกไปใช้)

> อ่าน `rag_service/docs/HANDOFF_AND_CLEANUP.md` ให้จบก่อน แล้วทำ dead-code/dead-file cleanup ของ
> `rag_service/` ตามกฎเหล็กในนั้น: (1) สร้าง branch + tag restore point (2) สำหรับแต่ละ candidate
> ในตาราง §2 ให้ grep หา reference ก่อน — ลบเฉพาะที่ไม่มีใครใช้ (chain.py ใช้จริง ห้ามลบ)
> (3) ตั้ง .gitignore สำหรับ build byproducts (`docs/_*.html`) (4) verify: py_compile ทั้งหมด +
> รัน evaluation/test_metrics.py + import agent_graph/main + smoke query 1 ครั้ง (5) สรุปว่าลบอะไร/
> เก็บอะไร แล้วเปิด PR — อย่า merge main ตรง อย่าลบก่อน verify
