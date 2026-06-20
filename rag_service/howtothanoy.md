# How to use the Thanoy legal integration

Thanoy (ทนอย) คือ Thai legal AI ของ iApp — เราใช้มันเติม **ส่วนที่ 3: คำแนะนำทางกฎหมาย**
ของรายงาน (`/generate-report`) โดย map เหตุการณ์ไซเบอร์ → กฎหมายไทย (พ.ร.บ.คอมพิวเตอร์,
พ.ร.บ.ไซเบอร์, ประมวลกฎหมายอาญา ฯลฯ)

> เป็น specialist แยกจาก pipeline MITRE: pipeline อธิบาย "เหตุการณ์เชิงเทคนิค",
> Thanoy แมป "ข้อกฎหมาย" — เราจงใจไม่สอนกฎหมายให้โมเดล MITRE (มันจะมโนเลขมาตรา)

---

## 1. เชื่อมอะไรบ้าง (architecture)

```
POST /generate-report
   ↓ 1. translate (ไทย→อังกฤษ) + retrieve context (Qdrant + Neo4j)
   ↓ 2. report_gen.generate()   → CyberCaseReport (ส่วน 1 case_summary + ส่วน 2 mitre_mapping)
   ↓ 3. get_legal_advice(case_summary)  → เรียก Thanoy API  → report.legal_advice (ส่วน 3)
   ↓ return CyberCaseReport (ครบ 3 ส่วนใน JSON ก้อนเดียว → UI render)
```

Output 3 ส่วนใน `CyberCaseReport`:
| field | ส่วน | ที่มา |
|---|---|---|
| `case_summary` | 1. สรุปรูปคดี | report_generator (Claude) |
| **`mitre_entities`** | 2. ตาราง MITRE (id/name/type) | **retrieval** (faithful — ใช้ render ตาราง) |
| `mitre_mapping` | (ID ที่ LLM map — ใช้ประกอบเหตุผล ไม่ใช่ตาราง) | LLM (Claude) |
| `legal_advice` | 3. คำแนะนำทางกฎหมาย | **Thanoy API** (+ disclaimer) |

> **ตาราง MITRE ให้ render จาก `mitre_entities`** (id+name+type จาก retrieval จริง) **ไม่ใช่ `mitre_mapping`**
> (ตัวหลังเป็น ID ที่ Claude generate → อาจมั่ว/ไม่ครบ เก็บไว้แค่ประกอบ mapping_justification)

ไฟล์ที่เกี่ยวข้อง:
- `app/RAG/GraphRAG/pipeline/thanoy_client.py` — client เรียก Thanoy + parse + disclaimer + fallback
- `app/RAG/GraphRAG/config.py` — env config (`THANOY_*`)
- `app/RAG/GraphRAG/pipeline/report_generator.py` — field `legal_advice` ใน `CyberCaseReport`
- `app/main.py` — `/generate-report` เรียก `get_legal_advice()` หลัง generate

---

## 2. ตั้งค่าก่อนใช้ (REQUIRED)

### 2.1 ขอ API key
สมัคร + ขอ key ที่ iApp AI Portal: <https://ai.iapp.co.th/product/thanoy_legal_ai>
แล้วเติมเครดิต (คิดเงินแบบ token: input ~10 THB / 1M, output ~20 THB / 1M → ต่อคดีเศษสตางค์)

### 2.2 ตั้ง env var
RAG config อ่านจาก **process env เท่านั้น** (ไม่ auto-load ไฟล์ `.env`) → ใช้ Doppler หรือ export เอง

| env | จำเป็น | default |
|---|---|---|
| `THANOY_API_KEY` | ✅ ใช่ | `""` (ว่าง = ปิด feature) |
| `THANOY_API_URL` | ไม่ | `https://api.iapp.co.th/thanoy` |
| `THANOY_TIMEOUT` | ไม่ | `30` (วินาที) |

**Doppler (แนะนำ):**
```bash
doppler secrets set THANOY_API_KEY=<your-key>
doppler run -- uvicorn app.main:app --port 8001 --reload
```

**Local (.env / shell):** เนื่องจาก config ไม่โหลด .env เอง ต้อง export เข้า env จริง:
```bash
# bash / WSL
export THANOY_API_KEY=<your-key>
# PowerShell
$env:THANOY_API_KEY = "<your-key>"
uvicorn app.main:app --port 8001 --reload
```

---

## 3. วิธีเรียกใช้ + เทส

เรียก endpoint เดิม ไม่มี param เพิ่ม:
```bash
curl -X POST http://localhost:8001/generate-report \
  -H "Content-Type: application/json" \
  -d '{"query":"ผู้โจมตีใช้ SQL Injection เข้าระบบ แล้ว credential dumping ยกระดับเป็น root ก่อนลบฐานข้อมูล postgres ทั้งหมด"}'
```
ดู field `legal_advice` ใน response — ควรมีข้อกฎหมาย + เลขมาตรา + disclaimer ต่อท้าย

---

## 4. พฤติกรรม (fallback — ออกแบบให้ไม่พังรายงาน)

| สถานการณ์ | ผล |
|---|---|
| ไม่ตั้ง `THANOY_API_KEY` | `legal_advice = null` — รายงานออกครบ 2 ส่วนแรกตามปกติ |
| Thanoy timeout / error / status ผิด | log `[THANOY] ... skipping` แล้ว `legal_advice = null` (ไม่ throw) |
| response ว่าง | `legal_advice = null` |
| สำเร็จ | `legal_advice = "<คำแนะนำ>\n\n<disclaimer ไทย>"` |

---

## 5. ⚠️ ข้อควรระวัง (เครื่องมืออัยการ)

1. **ตรวจความแม่นของมาตรา** — Thanoy เป็น AI ลองยิงเทสจริงดูว่า cite เลขมาตราถูกแค่ไหน
   ถ้ามั่ว = อันตรายกว่าไม่ใส่ → ปรับ `_QUERY_TEMPLATE` ใน `thanoy_client.py` หรือเพิ่มขั้น verify
2. **disclaimer ติดมาในตัวแล้ว** (ห้ามลบ) — output ระบุชัดว่าเป็น AI เบื้องต้น ต้องให้อัยการ/นิติกรตรวจ
3. **ส่งภาษาไทย** — Thanoy เป็นไทย เราส่ง `case_summary` (ไทย) ไปเป็น query

---

## 6. ปรับแต่ง

- **เปลี่ยนคำถามที่ส่งให้ Thanoy:** แก้ `_QUERY_TEMPLATE` ใน `thanoy_client.py`
- **เปลี่ยน disclaimer:** แก้ `LEGAL_DISCLAIMER` ในไฟล์เดียวกัน
- **response shape ของ Thanoy เปลี่ยน:** แก้ `_parse_response()` (ตอนนี้รองรับ `response` เป็น list ของ `{text}` หรือ string)
