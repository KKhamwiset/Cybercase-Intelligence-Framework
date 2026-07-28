# Primer — รู้อะไรก่อน ถึงจะอ่าน ARCHITECTURE.md รู้เรื่อง

> เอกสารปูพื้น สำหรับคนที่เพิ่งเข้าโปรเจกต์ `rag_service` อ่านอันนี้ให้จบก่อน แล้วค่อยไป [ARCHITECTURE.md](../ARCHITECTURE.md)
> เป้าหมาย: พาจาก "เป็น dev ทั่วไป" → "อ่านสถาปัตยกรรมและโค้ดของ pipeline นี้เข้าใจ"

ความรู้ที่ต้องมีแบ่งเป็น **4 กลุ่ม** — แนะนำอ่านตามลำดับนี้:

```
(1) โดเมน MITRE ATT&CK   →  (2) RAG พื้นฐาน  →  (3) GraphRAG + เทคนิค retrieval  →  (4) Agentic / Cross-lingual / Stack
```

ถ้ามีเวลาน้อย: อ่าน **ส่วนที่ 1 + 2 + 9 (glossary)** ก็พอเริ่มอ่าน ARCHITECTURE.md ส่วนภาพรวมได้

---

## 1. โดเมน: MITRE ATT&CK *(สำคัญที่สุด — ทั้งระบบหมุนรอบสิ่งนี้)*

**MITRE ATT&CK** คือ "ฐานความรู้สาธารณะของพฤติกรรมผู้โจมตีไซเบอร์" ที่จัดหมวดหมู่ว่าผู้โจมตี *ทำอะไรได้บ้าง* และ *ทำยังไง* — โปรเจกต์นี้ใช้มันเป็น "ตำรา" ในการแปลคำบรรยายเหตุการณ์ (ไทย) → เทคนิคมาตรฐานที่อ้างอิงได้ในสำนวนคดี

### 1.1 ลำดับชั้น: Tactic / Technique / Sub-technique
| ระดับ | ตอบคำถาม | ตัวอย่าง | รหัส |
|---|---|---|---|
| **Tactic** | *ทำไป "เพื่ออะไร"* (เป้าหมาย/ขั้นตอน) | Initial Access, Credential Access | `TA0001` |
| **Technique** | *"ทำยังไง"* | Phishing | `T1566` |
| **Sub-technique** | วิธีย่อยของ technique | Spearphishing Attachment | `T1566.001` |

> จุดที่คนสับสนบ่อย: **tactic ≠ technique** — tactic คือ "หมวดเป้าหมาย" (มี 14 อัน), technique คือ "วิธีจริง" (มีหลายร้อยอัน) เวลาทำรายงานคดี เราอยากได้ **technique (T-code)** เป็นหลักเพราะเฉพาะเจาะจงกว่า

### 1.2 Kill chain — 14 tactic เรียงตามลำดับเหตุการณ์
ผู้โจมตีมักไล่จากซ้ายไปขวา (ไม่จำเป็นต้องครบทุกขั้น):

```
Reconnaissance → Resource Development → Initial Access → Execution → Persistence →
Privilege Escalation → Defense Evasion → Credential Access → Discovery →
Lateral Movement → Collection → Command & Control → Exfiltration → Impact
```

| Tactic | แปล | ตัวอย่างในคดี |
|---|---|---|
| Initial Access (TA0001) | เจาะเข้าครั้งแรก | อีเมลฟิชชิ่ง, เจาะเว็บ |
| Execution (TA0002) | รันโค้ด/มัลแวร์ | เปิดไฟล์แนบแล้ว macro ทำงาน |
| Persistence (TA0003) | ฝังตัวให้อยู่ได้นาน | ติดตั้ง backdoor |
| Privilege Escalation (TA0004) | ยกระดับสิทธิ์ | กลายเป็น admin/root |
| Credential Access (TA0006) | ขโมยรหัสผ่าน | dump credential, keylogger |
| Lateral Movement (TA0008) | ย้ายไปเครื่องอื่น | RDP/SMB ไปเซิร์ฟเวอร์ |
| Collection (TA0009) | รวบรวมข้อมูล | รวมไฟล์ก่อนขโมย |
| **Exfiltration (TA0010)** | **ขโมยข้อมูลออกไป** | copy ฐานข้อมูลส่งออกนอก |
| **Impact (TA0040)** | **สร้างความเสียหาย** | ransomware เข้ารหัส, ลบข้อมูล |

> **Exfiltration / Impact อยู่ท้ายสุด** และเป็นสิ่งที่คดีสนใจมากสุด (ข้อมูลรั่ว/ถูกทำลาย = ความเสียหายจริง) — นี่คือเหตุผลที่ใน ARCHITECTURE.md ย้ำว่าห้ามให้ขั้น "decompose" ตัดสองอันนี้ทิ้ง

### 1.3 ชนิด Entity ที่เก็บในฐานข้อมูล
นอกจาก Technique/Tactic ยังมี entity อื่นที่เชื่อมโยงกัน:

| Entity | คือ | รหัส |
|---|---|---|
| **Group** | กลุ่มผู้โจมตี (APT) | `G0016` (APT29) |
| **Software** | เครื่องมือ/มัลแวร์ | `S0002` (Mimikatz) |
| **Campaign** | ปฏิบัติการโจมตีที่ระบุชื่อ | `C0027` |
| **Mitigation** | มาตรการป้องกัน | `M1037` |
| **DataSource / DataComponent** | แหล่งข้อมูล/สัญญาณที่ใช้ "ตรวจจับ" technique | — |

### 1.4 ความสัมพันธ์ (edges) — หัวใจของ "Graph"
ATT&CK ไม่ใช่แค่ลิสต์ แต่เป็น **กราฟ**: entity เชื่อมกันด้วยความสัมพันธ์
- `USES` — Group/Software ใช้ Technique (เช่น APT29 USES Phishing)
- `MITIGATES` — Mitigation ป้องกัน Technique
- `SUBTECHNIQUE_OF` — sub อยู่ใต้ technique แม่
- `ATTRIBUTED_TO` — Campaign โยงไป Group
- `DETECTS` — DataComponent ตรวจจับ Technique
- `IN_TACTIC` — Technique อยู่ใน Tactic ไหน
- `HAS_COMPONENT` — DataSource มี DataComponent

### 1.5 STIX
**STIX 2.1** = ฟอร์แมต JSON มาตรฐานที่ MITRE ใช้แจกข้อมูล ATT&CK — ในโปรเจกต์เราเอาไฟล์ STIX มา "parse" (แยกออกเป็น entity + relationship) แล้วโหลดเข้า DB (ดู `ingestion/` ใน ARCHITECTURE.md)

---

## 2. RAG พื้นฐาน (Retrieval-Augmented Generation)

**ปัญหา:** LLM (เช่น Claude) เก่งภาษา แต่ (ก) ไม่รู้ข้อมูลเฉพาะทาง/ล่าสุด และ (ข) ชอบ **hallucinate** (มั่วขึ้นเอง) เช่น แต่งรหัส ATT&CK ที่ไม่มีจริง

**ทางแก้ = RAG:** ก่อนให้ LLM ตอบ ให้ไป "ค้น" ข้อมูลจริงมาแปะใส่คำถามก่อน วน 3 จังหวะ:

```
Retrieve (ค้นเอกสารที่เกี่ยว) → Augment (เอามาแปะเป็น "context") → Generate (LLM ตอบโดยอิง context)
```

ผลคือ LLM ตอบจาก **หลักฐานจริง** (เรียกว่า *grounding*) ไม่ใช่ความจำที่อาจมั่ว

**Embedding + Vector DB** = หัวใจของ "Retrieve":
- **Embedding** = แปลงข้อความเป็นเวกเตอร์ตัวเลข ที่ข้อความความหมายใกล้กันจะมีเวกเตอร์ใกล้กัน
- **Vector DB** (Qdrant) = ที่เก็บเวกเตอร์ + ค้นหา "เอกสารที่ใกล้เคียงเชิงความหมาย" ได้เร็ว
- ดังนั้นถาม "ผู้ต้องหาส่งอีเมลหลอก..." → ระบบหาเอกสาร MITRE ที่ใกล้สุด = Phishing โดยไม่ต้องตรงคำเป๊ะ

---

## 3. GraphRAG + เทคนิค Retrieval ที่ใช้

### 3.1 ทำไมต้อง "Graph" RAG
- **Vector search อย่างเดียว** เก่งเรื่อง "หาเอกสารคล้าย" แต่ไม่เห็น *ความสัมพันธ์* ที่ชัดเจน
- **Graph (Neo4j)** เก็บความสัมพันธ์ตรงๆ (technique นี้กลุ่มไหนใช้, ป้องกันยังไง)
- **GraphRAG = รวมสองอย่าง:** vector หา node ตั้งต้น → "ขยายกราฟ" (graph expansion) ดูเพื่อนบ้าน → ได้ context ครบทั้งความหมาย + โครงสร้าง

### 3.2 ศัพท์ retrieval ที่จะเจอใน ARCHITECTURE.md
| ศัพท์ | ความหมายสั้น |
|---|---|
| **Dense / Sparse** | dense = เวกเตอร์เชิงความหมาย; sparse = เชิงคำ/keyword (จับคำตรง เช่น "T1566") — ใช้คู่กัน |
| **Hybrid search** | ค้นด้วย dense + sparse พร้อมกัน |
| **RRF** (Reciprocal Rank Fusion) | สูตรรวมอันดับจากหลายช่องทางเป็นอันดับเดียว |
| **Rerank / Reranker** | เอาผลรอบแรกมา *จัดอันดับใหม่* ด้วยโมเดลแม่นกว่า ก่อนส่ง LLM |
| **top-K** | เก็บผลแค่ K อันดับแรก (เช่น top-K=6) |
| **Graph expansion** | จาก node ที่เจอ ดึงเพื่อนบ้านในกราฟมาเสริม |
| **Dual-query** | ค้นด้วย query ไทย + ที่แปลอังกฤษ พร้อมกัน |
| **Decomposition** | แตก incident ยาว → sub-query ย่อยทีละ technique |
| **Quota retrieval** | การันตีทุก sub-query ได้พื้นที่ในผลลัพธ์ (ไม่ให้ technique ใดหาย) |
| **Faithful (table)** | ตารางที่สร้างจาก "ของจริงที่ค้นเจอ" ไม่ใช่จากที่ LLM พูด → รหัสไม่ถูกมั่ว |

---

## 4. Agentic RAG & LangGraph

### 4.1 Chain (เส้นตรง) vs Agent (มีสมอง)
- **Chain** = pipeline เส้นตรง ทำตามสเต็ปคงที่ (translate → retrieve → reason → translate) จบ
- **Agent** = มี "การตัดสินใจ" ระหว่างทาง: ประเมินว่าข้อมูลพอไหม, ถ้าไม่พอจะ *ถามกลับ* หรือ *ค้นใหม่*

### 4.2 LangGraph = state machine
- เขียน pipeline เป็น **กราฟของ node** แต่ละ node ทำงานหนึ่งอย่าง แล้วส่ง "state" (ข้อมูลที่สะสมมา) ต่อ
- **edge** = เส้นเชื่อม node; **conditional edge** = แยกทางตามเงื่อนไข (เช่น "พอ" → ไปตอบ, "ไม่พอ" → ไปถาม)
- คำที่จะเจอ: **self-reflection / evaluator** (LLM ประเมิน context ตัวเอง), **broaden** (เขียน query ใหม่แล้วค้นกว้างขึ้น)

> ดูรูป "LangGraph state machine" ใน ARCHITECTURE.md §6.2 จะเห็นภาพชัด

---

## 5. Cross-lingual (ไทย ↔ อังกฤษ)

**ข้อตกลงของโปรเจกต์ (language contract):**
- input = **ไทยเสมอ** (สำนวนคดี), output = **ไทยเสมอ**
- แต่ตำรา MITRE เป็น **อังกฤษ** → ระบบจึงแปลเป็นอังกฤษ *ภายใน* เพื่อใช้ค้น/คิด แล้วแปลกลับเป็นไทยตอนตอบ
- 3 จังหวะ: **translate query** (TH→EN) → **reasoning** (คิดเป็น EN) → **translation** (EN→TH)
- คำที่เกี่ยว: **code-switch** = อาการที่ LLM สลับภาษากลางประโยค (เช่นพิมพ์คำจีนปนมา), **CJK** = อักษรจีน-ญี่ปุ่น-เกาหลี, **CJK guard** = ตัวกันไม่ให้อักษรพวกนี้หลุดในรายงานไทย

---

## 6. เครื่องมือ/โมเดล ที่ควรรู้จักชื่อ

| ชื่อ | คืออะไร |
|---|---|
| **BGE-M3** | โมเดล embedding (ทำได้ทั้ง dense + sparse, รองรับหลายภาษ รวมไทย) |
| **bge-reranker-v2-m3** | โมเดล reranker (cross-encoder) จัดอันดับผลค้นใหม่ |
| **Claude (Haiku/Sonnet)** | LLM บน cloud ของ Anthropic — ใช้ reasoning/แปล/ประเมิน |
| **Ollama** | ตัวรันโมเดลภาษาบนเครื่อง local (โหมด `--local`, เช่น qwen2.5) |
| **Neo4j** | กราฟดาต้าเบส (เก็บ entity + relationship), ค้นด้วยภาษา **Cypher** |
| **Qdrant** | vector database (เก็บ embedding + ค้นความใกล้เคียง) |
| **FastAPI** | เฟรมเวิร์ก Python ทำ REST API (บริการพอร์ต 8001) |
| **LangChain / LangGraph** | ไลบรารีเชื่อม LLM + เครื่องมือ; LangGraph ทำ state machine |
| **Pydantic** | นิยาม schema ข้อมูลแบบ typed (ใช้กับ models + รายงาน) |
| **Doppler** | ตัวจัดการ secret/ตัวแปรลับ (แทน .env ตอน deploy) |

---

## 7. ทักษะรอบตัวที่ช่วยให้อ่านโค้ดง่ายขึ้น
- **Python**: type hints, `dataclass` / Pydantic models, `async`/`await` (FastAPI + Thanoy client), decorator
- **REST API**: endpoint, request/response body, status code (200/404/503)
- **JSON / STIX**: โครงสร้าง nested object
- **env vars**: ค่าคอนฟิกมาจาก environment (เช่น `ANTHROPIC_API_KEY`, `USE_LOCAL`)
- **Docker เบื้องต้น**: รู้ว่า service ถูกแพ็กเป็น image, โหลดโมเดลตอน build
- **สัญชาตญาณเรื่อง latency**: LLM ตอบช้าตามจำนวน "token ที่ output", ยิ่งเรียก LLM หลายรอบ/ค้นหลายรอบยิ่งช้า (เป็นที่มาของโหมด `--fast`/`--ultrafast`)

---

## 8. ตัวย่อ/สัญลักษณ์ที่เจอบ่อย
- `T1566`, `T1566.001` = Technique / Sub-technique
- `TA0001` = Tactic | `G####` = Group | `S####` = Software | `M####` = Mitigation | `C####` = Campaign
- `stix_id` = รหัสภายในของ STIX (เช่น `attack-pattern--xxxx`) ใช้เป็น key เชื่อม DB
- `top_k`, `RRF`, `LLM`, `RAG`, `EN`/`TH`

---

## 9. Glossary รวม (เรียงตามกลุ่ม)

**RAG / Retrieval**
- **RAG** — ค้นข้อมูลจริงมาเสริมก่อนให้ LLM ตอบ
- **Embedding** — ข้อความ → เวกเตอร์ตัวเลข
- **Dense / Sparse** — เชิงความหมาย / เชิงคำ
- **Hybrid search** — dense + sparse พร้อมกัน
- **RRF** — สูตรรวมอันดับหลายช่องทาง
- **Rerank** — จัดอันดับผลค้นใหม่ด้วยโมเดลแม่นกว่า
- **Graph expansion** — ดึงเพื่อนบ้านในกราฟมาเสริม
- **top-K** — เอา K อันดับแรก
- **Dual-query / Decomposition / Quota** — กลยุทธ์เพิ่ม coverage ของการค้น
- **Grounding** — ตอบโดยอิงหลักฐานจริง
- **Faithful** — สร้างผลจากของจริงที่ค้นเจอ ไม่ใช่จากที่ LLM พูด

**LLM / Agent**
- **LLM** — โมเดลภาษา (Claude, Qwen ฯลฯ)
- **Hallucinate** — LLM มั่ว/แต่งสิ่งที่ไม่มีจริง
- **Self-reflection / Evaluator** — LLM ประเมินว่า context พอตอบไหม
- **Broaden search** — context ไม่พอ → agent เขียน query ใหม่เองแล้วค้นซ้ำ (เพดาน 2 รอบ)
- **State machine (LangGraph)** — pipeline เป็นกราฟของ node + edge
- **Latency** — เวลาที่ใช้ตอบ (ยิ่งเรียก LLM/ค้นหลายรอบ ยิ่งนาน)
- **Token** — หน่วยข้อความที่ LLM ประมวล; output token เยอะ = ช้า

**ภาษา**
- **Cross-lingual** — ข้ามภาษา (ไทย↔อังกฤษ)
- **Code-switch** — LLM สลับภาษากลางประโยค
- **CJK** — อักษรจีน/ญี่ปุ่น/เกาหลี
- **CJK guard** — ตัวตรวจจับ+แก้อักษร CJK ที่หลุดในรายงานไทย

**MITRE / โดเมน**
- **MITRE ATT&CK** — ฐานความรู้พฤติกรรมผู้โจมตี
- **Tactic / Technique / Sub-technique** — เป้าหมาย / วิธี / วิธีย่อย
- **Kill chain** — ลำดับ tactic ของการโจมตี
- **Exfiltration (exfil)** — ขโมยข้อมูลออกนอกระบบ
- **Impact** — สร้างความเสียหาย (ransomware/ลบข้อมูล/ทำระบบล่ม)
- **STIX** — ฟอร์แมต JSON มาตรฐานของ ATT&CK
- **Group / Software / Campaign / Mitigation** — กลุ่มโจมตี / เครื่องมือ / ปฏิบัติการ / มาตรการป้องกัน

---

## 10. ไกด์ลำดับการอ่าน ARCHITECTURE.md

| ถ้าคุณอยาก... | อ่านส่วนไหนก่อน |
|---|---|
| เข้าใจภาพรวมว่าระบบทำอะไร | §1 ภาพรวม + ดู mermaid diagram |
| เข้าใจ "เทคนิคอะไรถูกใช้ ทำไม" | §2 เทคนิค/Method |
| รู้ว่าใช้โมเดล/DB อะไร | §3 โมเดล + §4 DB Schema |
| ตามรอย request หนึ่งอัน | §6 Request Lifecycle |
| ลงลึกโค้ดฟังก์ชันใดฟังก์ชันหนึ่ง | §7 อ้างอิงโค้ดทุกฟังก์ชัน (เปิดเฉพาะไฟล์ที่สนใจ) |
| รู้ข้อจำกัด/จุดที่ต้องระวัง | ภาคผนวกท้ายเอกสาร |

**เส้นทางแนะนำสำหรับมือใหม่:** §1 → §2 → ดู diagram §6 → แล้วค่อยเจาะ §7 เฉพาะ pipeline ที่ทำงานด้วย (เช่น `agent_graph.py` หรือ backend `generator.py`)
