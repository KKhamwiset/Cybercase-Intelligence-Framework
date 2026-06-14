technique_coverage
วิธีที่ 2 — ATT&CK Technique Coverage (แนะนำเพิ่ม) ⭐
เหมาะมากสำหรับโปรเจกต์นี้โดยเฉพาะ ไม่ต้องใช้ LLM judge เลย

# ไอเดีย: นับว่าคำตอบ mention MITRE IDs ที่ถูกต้องกี่ตัว
def technique_coverage(answer: str, relevant_stix_ids: list[str]) -> float:
    # ดึง T-IDs จาก answer (เช่น T1566, T1078)
    # เทียบกับ IDs ที่ควรพูดถึงใน ground truth
    # คืน precision / recall / F1

# Parallel Retrieval
ระบบนี้มี relevant_stix_ids ทุก sample อยู่แล้ว — สร้าง domain metric ได้ทันที

ตามที่ขอเพิ่ม: ทุก part มีคำอธิบายระดับ ไฟล์นี้ทำอะไร / ฟังก์ชันนี้ทำอะไร ครบ

จุดสำคัญที่เจอระหว่างอ่านโค้ด (อยู่ใน §16)
ผมเจอจุดที่โค้ดจริง ไม่ตรง กับเอกสาร/config เดิม ซึ่งสำคัญเวลาเขียนรายงานหรือแก้โค้ด เช่น:

Router ใน Agent ถูกปิดชั่วคราว — บังคับเข้า incident เสมอ
Graph expansion ทำแค่ 1 hop ทั้งที่ config ตั้ง GRAPH_EXPANSION_DEPTH=2 (ค่านี้ไม่ถูกอ่าน)
RRF_K / DENSE_WEIGHT / SPARSE_WEIGHT ตั้งไว้แต่ Qdrant native RRF ไม่รับค่าพวกนี้
RAGAS model จริงเป็น qwen-2.5-72b ไม่ใช่ llama-3.3-70b ตามที่ CLAUDE.md บอก

pararell retrieve

20 นาทีนี่นานผิดปกติสำหรับ generate ครั้งเดียว — ขอเช็กว่ามันคืบหน้าหรือค้าง

เจอแล้ว — มัน**ค้าง ไม่ได้ generate จริง**:
- `ollama ps` ว่างเปล่า (ไม่มีโมเดลโหลดอยู่)
- GPU ใช้แค่ 885MB / util 16% (idle)
- output file ยังมีแค่บรรทัด header

สาเหตุ: `ollama run` แบบ non-interactive ใน background ของ PowerShell มักค้างรอ TTY (spinner) ไม่จบ — ผมจะ**ฆ่าตัวที่ค้าง** แล้วเทสต์ใหม่ผ่าน **REST API** (จำกัด token + จับเวลา เชื่อถือได้กว่า)

ทำงานได้สมบูรณ์ ปัญหาคือ `ollama run` ค้างเรื่อง TTY ล้วน ๆ **ไม่ใช่ฮาร์ดแวร์ช้า** — REST API ได้ **11.7 tok/s** (เร็วพอเลย!) และคำตอบออกมาในสไตล์ specialist เป๊ะ ("X (Txxxx) is a MITRE ATT&CK technique — ...") ตรงกับชุดเทรน + อ้าง T1003 ถูก

ขอรันโมเดลเดิมด้วยคำถามเดียวกัน (params เท่ากัน) เพื่อเทียบ:

ได้ผลที่น่าสนใจมาก! โมเดลเดิม **มั่ว ID** — แต่คำตอบ fine-tuned ถูกตัดที่ 140 token เลยยังไม่ทันโชว์ส่วน mitigations ขอรัน fine-tuned อีกครั้งแบบยาวพอให้จบ เพื่อเทียบความแม่นของ ID ตรง ๆ:

ค้นพบพฤติกรรมสำคัญ: fine-tuned ตอบส่วน "What is T1003?" ในสไตล์ MITRE เป๊ะแล้ว**หยุด** (79 token) ไม่ต่อ mitigations — เพราะชุดเทรนเป็น template **แยก** ("what is X" กับ "what mitigations for X" คนละตัวอย่าง) พอเจอคำถามรวม มันตอบแบบ lookup แล้วจบ

ลองถามตรง ๆ เป็นคำถาม mitigation (ตรง template ที่เทรน) เพื่อดูว่ามันอ้าง M-ID ถูกไหม:

ผลออกมาชัดเจนและน่าประทับใจมากครับ 🎯 — fine-tuned ตอบคำถาม mitigation ด้วย **M-ID ที่ถูกต้องจริง** (M1027, M1026, M1028) ขณะที่โมเดลเดิม**มั่ว ID**

## เทียบคำตอบ: "mitigations ของ OS Credential Dumping (T1003)"

| | 🔵 `qwen2.5:7b` (เดิม) | 🟢 `mitre-qwen:7b` (fine-tuned) |
|---|---|---|
| **Mitigation IDs** | `T1562.001`, `T1484` | `M1027`, `M1026`, `M1028` |
| **ถูกต้องไหม** | ❌ **มั่ว** — ทั้งคู่เป็น *technique* (T-) ไม่ใช่ mitigation | ✅ **ถูกหมด** — เป็น mitigation จริงของ MITRE (M-) |
| **รู้ convention M vs T** | ❌ สับสน เอา T มาเป็น mitigation | ✅ ใช้ M-prefix สำหรับ mitigation ถูกต้อง |
| **สำนวน** | กว้าง ๆ แบบทั่วไป | สไตล์ MITRE เป๊ะ ("...is a MITRE ATT&CK technique —") |
| **ความเร็ว** | 11.1 tok/s | 11.7 tok/s |

**นี่คือคุณค่าหลักของ fine-tune:** โมเดลเดิม "hallucinate ID" (อันตรายมากใน use-case ที่ต้องอ้างอิงแม่นยำ) — ตัว fine-tuned เลิกมั่ว เพราะซึมซับ KB + convention ของ MITRE เข้าไปใน weights แล้ว

## ⚠️ ข้อสังเกต (trade-off ที่ตรงไปตรงมา)
- คำถาม**รวม** ("อธิบาย + ขอ 2 mitigations" ในประโยคเดียว) → fine-tuned ตอบส่วน lookup แล้วหยุด เพราะชุดเทรนเป็น template **แยกเรื่อง** ไม่มีแบบรวม
- เป็นไปตามที่เขียนไว้ใน **Limitations** ของรายงานแล้ว → งานต่อยอดคือเติมตัวอย่างแบบ compound/incident-style (distill จาก Claude) เพื่อให้ตอบคำถามซับซ้อนได้ครบ

## ✅ ข่าวดีเชิงเทคนิค
**ฮาร์ดแวร์เร็วพอ** (11+ tok/s) — ตอนแรกที่ค้างเป็นบั๊ก `ollama run` กับ TTY ล้วน ๆ ดังนั้น **A/B เชิงปริมาณ (`run_comparison.py`) รันไหวแน่นอน** (--max-samples 10 ≈ 2 โมเดล × 10 + RAGAS judge ≈ ไม่กี่นาที)

แนวทาง	เมื่อไหร่ควรใช้
A. อังกฤษล้วน (ปัจจุบัน) ✅	reasoning เป็นอังกฤษ, ปล่อย Thai ให้ stage แปล — ตรงสถาปัตยกรรม แนะนำ
B. เพิ่ม bilingual บางส่วน	ถ้าอยากให้คำแปลไทยใช้ศัพท์ MITRE ที่ถูก (เช่นไม่แปล "Credential Dumping" มั่ว) → เติม Thai example คุณภาพดีจำนวนหนึ่ง โดยคง EN เป็นหลัก
C. แยกโมเดลแปล	ใช้ qwen2.5:7b เดิมทำ translation, mitre-qwen ทำ reasoning (ต้องเพิ่ม config แยก 2 ตัว)