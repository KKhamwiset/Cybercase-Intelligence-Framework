technique_coverage
วิธีที่ 2 — ATT&CK Technique Coverage (แนะนำเพิ่ม) ⭐
เหมาะมากสำหรับโปรเจกต์นี้โดยเฉพาะ ไม่ต้องใช้ LLM judge เลย

# ไอเดีย: นับว่าคำตอบ mention MITRE IDs ที่ถูกต้องกี่ตัว
def technique_coverage(answer: str, relevant_stix_ids: list[str]) -> float:
    # ดึง T-IDs จาก answer (เช่น T1566, T1078)
    # เทียบกับ IDs ที่ควรพูดถึงใน ground truth
    # คืน precision / recall / F1
ระบบนี้มี relevant_stix_ids ทุก sample อยู่แล้ว — สร้าง domain metric ได้ทันที