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