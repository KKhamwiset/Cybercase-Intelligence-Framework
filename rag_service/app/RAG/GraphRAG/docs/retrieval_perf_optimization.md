# Retrieval Performance Optimization — สรุปงานทั้งหมด

**Branch:** `perf/retrieval-batch-expand`
**วันที่:** 2026-07-11
**ขอบเขต:** ลด latency ของ retrieval ใน pipeline โดยไม่เปลี่ยนผลลัพธ์ (behavior-preserving)

---

## 1. ที่มา (ทำไมต้องแก้)

จากการวัด latency ของ pipeline พบว่า **retrieval กินเวลาส่วนใหญ่** และภายใน retrieval
ตัวถ่วงคือ **graph expansion บน Neo4j** ซึ่งวนขยายทีละ seed:

- `retrieve_multi_quota()` แตกสำนวนเป็น N sub-query (decompose) แล้ววนทีละตัว
- แต่ละ sub-query เรียก `retrieve()` → `graph_retriever.expand()`
- `expand()` วน `_expand_single()` ทีละ seed แต่ละ seed **เปิด Neo4j session ใหม่ + ยิง 3 Cypher**
  (center + outgoing + incoming)
- ต่อ 1 สำนวน (~7 sub-query × ~5 seed × 3 query) = **~100 sequential round-trip** ไป cloud Neo4j

คอขวดคือ round-trip จำนวนมากไป cloud DB ไม่ใช่การคำนวณ

---

## 2. สิ่งที่ทำ (3 อย่าง)

| # | สิ่งที่ทำ | สถานะ | ผล |
|---|----------|-------|-----|
| 1 | **Batch Neo4j expansion** — ยิง 3 Cypher (UNWIND) รวมทั้ง seed list แทน 3×N | ✅ commit `0e91f9c` | เร็วขึ้น 3.5× ที่ชั้น expand, ผลเหมือนเดิมเป๊ะ |
| 2/3 | **Batch ข้าม sub-query** — embed/Qdrant/rerank/graph ครั้งเดียวสำหรับทุก sub-query | ❌ ทิ้ง (พิสูจน์แล้วไม่คุ้ม) | GPU ~เท่าเดิม, CPU +10% ไม่สม่ำเสมอ; batch rerank ยิ่งช้า |
| 4 | **Device-aware model loading** — auto GPU/CPU + fp16 เฉพาะ GPU + log + override | ✅ commit `697731b` | แก้ fp16-on-CPU → CPU embedding เร็วขึ้น ~20% |

---

## 3. รายละเอียด item 1 — Batched Neo4j Expansion

**เดิม** (`_expand_single` ต่อ seed): N seed × 3 Cypher × session ใหม่ = 3N round-trip
**ใหม่** (`expand_batch`): 3 Cypher รวม (`UNWIND $ids`) ใน session เดียว = 3 round-trip

**เทียบ old vs new บน input เดียวกัน (GPU, controlled):**

| sample | old (per-seed loop) | new (batched UNWIND) | speedup |
|--------|--------------------:|---------------------:|:-------:|
| inc_auto_001 (8 seeds) | 1971 ms | 543 ms | 3.6× |
| inc_auto_002 (8 seeds) | 1226 ms | 378 ms | 3.2× |
| inc_auto_003 (8 seeds) | 959 ms | 222 ms | 4.3× |
| inc_auto_004 (8 seeds) | 1303 ms | 427 ms | 3.0× |
| **รวม** | **5458 ms** | **1571 ms** | **3.5×** |

**ความถูกต้อง:** `SET EQUIVALENCE: PASS` — center nodes (ลำดับเดียวกัน) + neighbor/edge
sets ทุก subgraph เหมือนเดิมเป๊ะ (ลำดับ neighbor ภายใน subgraph อาจต่างเพราะ Neo4j ไม่
การันตี row order แต่ set ของ ID ที่ retrieve ได้ไม่เปลี่ยน)

---

## 4. รายละเอียด item 2/3 — Batch ข้าม sub-query (ทิ้ง)

หลัง item 1 profile ต่อ sub-query สมดุลกัน 3 ส่วน (GPU): vector 0.50s / rerank 0.52s /
graph 0.50s = 1.52s ต่อ sub-query จึงลอง batch ทั้ง 3 ส่วนให้ทำครั้งเดียวสำหรับทุก sub-query

**ผลการทดลอง (set เหมือนเดิมทุกกรณี แต่ latency แย่/ไม่คุ้ม):**

| ฮาร์ดแวร์ | วิธี | ผล | สรุป |
|----------|------|-----|------|
| GPU | batched vs seq (แก้ order effect แล้ว) | 14.5s vs 14.7s = **1.01×** | เท่าเดิม |
| CPU | batched (รวม rerank) vs seq | 210.4s vs 186.4s = **0.89×** | ช้ากว่า |
| CPU | hybrid (batch ทุกอย่างเว้น rerank) vs seq | 170.3s vs 187.2s = **1.10×** | ดีขึ้นเล็กน้อย ไม่สม่ำเสมอ |

**สาเหตุ:** การ batch cross-encoder rerank (รวม pair ทุก sub-query เป็น predict เดียว)
**ช้ากว่า** การ rerank ทีละ query ทั้งบน GPU (VRAM pressure) และ CPU — stage timing บน CPU:
`search_all_batch=13.7s, rerank_batch=69.8s (!), expand_batch=1.3s` → rerank_batch คือตัวถ่วง

**การตัดสินใจ:** ทิ้ง item 2/3 — ผลได้ ~10% บน CPU ไม่สม่ำเสมอ แลกกับโค้ดซับซ้อน +
ความเสี่ยง float-equivalence จาก batched embed ไม่คุ้ม

**Insight ที่ได้:** คอขวดจริงบน production (CPU) คือ **cross-encoder reranker เอง**
(~7-8s ต่อ sub-query) ที่ batch ไม่ได้ — เป็นงานปรับปรุงคนละก้อน (ลดจำนวน sub-query /
reranker เล็กลง / rerank ครั้งเดียวบน merged candidates / ย้ายไป GPU host)

---

## 5. รายละเอียด item 4 — Device-Aware Loading

**ปัญหาที่พบ:** `USE_FP16 = True` ถูก hardcode — fp16 เป็น GPU optimization บน CPU
ต้อง emulate (ช้า) และ production (Railway) รันบน **CPU** (torch CPU wheel + `python:3.11-slim`)

**การแก้:**
- `config.DEVICE` = `cuda` ถ้ามี GPU ไม่งั้น `cpu`
- `USE_FP16 = (DEVICE == "cuda")` — fp16 เฉพาะ GPU, CPU ใช้ fp32
- `RAG_DEVICE=cpu|cuda` override (สำหรับเทสต์/บังคับ target)
- log ตอน startup: `[CONFIG] Inference device: …`
- reranker ส่ง `device=DEVICE` ชัดเจน

**ยืนยัน:** default → `cuda` (fp16=True) reranker บน `cuda:0`; `RAG_DEVICE=cpu` → `cpu`
(fp16=False) ซ่อน GPU สำเร็จ

**ผล fp16 → fp32 บน CPU (prod-like):** e2e retrieval เร็วขึ้น ~20% (ดูตาราง §6)

---

## 6. เปรียบเทียบ CPU / GPU (โค้ดสุดท้าย: item 1 + device fix, production path)

e2e retrieval (retrieve_multi_quota, sequential path จริงของ production):

| sample (sub-q) | **GPU** (cuda, fp16) | **CPU fp32** (prod-like, ใหม่) | CPU fp16 (เก่า, ก่อนแก้) |
|----------------|---------------------:|-------------------------------:|-------------------------:|
| inc_auto_001 (9) | 16.8s | 51.6s | ~68–76s |
| inc_auto_002 (8) | 13.5s | 55.2s | ~67–70s |
| inc_auto_003 (6) | 10.1s | 39.4s | ~41–50s |

**อ่านตาราง:**
- **GPU เร็วกว่า CPU ~3-4×** — แต่ production คือ CPU (Railway ไม่มี GPU)
- **CPU fp32 (ใหม่) เร็วกว่า CPU fp16 (เก่า) ~20%** — ผลของการแก้ device (fp16-on-CPU)
- latency แปรผันตามจำนวน sub-query (decompose มาก = ช้า) + **cloud variance สูง**
  (Qdrant/Neo4j cloud แกว่ง เคยเห็น seq เดียวกันช่วง 19-31s บน GPU) — ตัวเลข e2e
  จึงเป็น "แนวโน้ม" ไม่ใช่ค่าตายตัว

**⚠️ ข้อควรระวัง:** ตัวเลข GPU วัดบน RTX 2050 ในเครื่อง dev — production ใช้ CPU เสมอ
การตัดสินใจ latency เชิง production ต้องอิงคอลัมน์ CPU fp32

---

## 7. สรุปการทดสอบ — ครบทุกแบบหรือยัง?

| การวัด | GPU | CPU |
|--------|:---:|:---:|
| item 1 equivalence (controlled) | ✅ | — (network-bound, hardware-agnostic) |
| stage profile ต่อ sub-query | ✅ | — |
| item 2/3 batched vs seq | ✅ | ✅ |
| item 2/3 hybrid vs seq | — | ✅ |
| โค้ดสุดท้าย e2e | ✅ | ✅ (fp32) |
| device detection | ✅ | ✅ |

ทุกการทดสอบเป็น **retrieval-only ไม่ใช้ LLM** (ไม่มีค่า API) และบันทึกเวลาไว้ทุกรอบ

---

## 8. สถานะ Push / Merge

**อยู่บน main แล้ว** (จาก session ก่อนหน้า):
- PR #12 — single-call Thai generation (variant C)
- PR #13 — fix follow-up empty answer

**รอ push + PR — branch `perf/retrieval-batch-expand` (2 commits):**
- `0e91f9c` perf(retrieval): batch Neo4j graph expansion (item 1)
- `697731b` feat(retrieval): device-aware model loading (item 4)

ทั้งสอง commit behavior-preserving + verified ทั้ง GPU/CPU → พร้อม merge

**ทิ้งแล้ว:** item 2/3 (revert ออกจาก working tree, ไม่ commit)

---

## 9. งานต่อยอด (นอกขอบเขตนี้)

- **คอขวดจริง = reranker บน CPU** — ตัวเลือก: ลดจำนวน sub-query, reranker ที่เล็ก/เร็วกว่า,
  rerank ครั้งเดียวบน merged candidates (เปลี่ยน semantics), หรือย้าย rag_service ไป GPU host
- **retrieval quality** — described-cue coverage 0.42 (คอขวดคุณภาพ แยกจาก latency)
