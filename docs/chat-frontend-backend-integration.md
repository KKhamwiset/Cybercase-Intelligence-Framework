# Chat Frontend–Backend Integration

เอกสารนี้สรุป integration ของ persistent chat ระหว่าง Next.js frontend, FastAPI backend,
PostgreSQL และ `rag_service` ตาม implementation ปัจจุบัน

## ขอบเขตและเจ้าของข้อมูล

- Frontend ดูแล UI state, thread selection, request cancellation และ polling
- Backend เป็นเจ้าของ thread lifecycle, message ordering, background runs และการ validate request
- PostgreSQL เป็นแหล่งข้อมูลถาวรของ threads, messages และ runs
- `rag_service` ประมวลผลแต่ละคำขอผ่าน `/query`; backend เป็นเจ้าของ clarification state
  และประกอบ context ที่สะสมจากข้อความใน PostgreSQL

ข้อมูลจาก `rag_service` ไม่ถูกเขียนตรงจาก frontend ทุก request ต้องผ่าน backend

## API contract

| Method | Endpoint | Success | หน้าที่ |
| --- | --- | --- | --- |
| `GET` | `/api/v1/chats` | `200` | รายการ thread เรียงตาม `updated_at` ล่าสุด |
| `POST` | `/api/v1/chats` | `201` | สร้าง thread ชื่อ `New chat` หรือชื่อที่กำหนด |
| `GET` | `/api/v1/chats/{thread_id}` | `200` | โหลด thread และ messages ตาม `ordinal` |
| `PATCH` | `/api/v1/chats/{thread_id}` | `200` | เปลี่ยนชื่อ thread |
| `DELETE` | `/api/v1/chats/{thread_id}` | `204` | ลบ thread, messages และ runs แบบถาวร |
| `POST` | `/api/v1/chats/{thread_id}/messages` | `202` | รับข้อความและสร้าง background run |
| `GET` | `/api/v1/chats/{thread_id}/runs/{run_id}` | `200` | อ่านสถานะ/error ของ run ที่รู้ ID |

Thread ที่ไม่มีอยู่ตอบ `404` พร้อม `detail: "Chat thread not found"`

## การส่งข้อความและ background run

```text
Frontend
  POST /chats/{thread_id}/messages
        ↓
Backend transaction
  lock thread row
  create user message + ordinal
  create queued ChatRun
  mark thread processing
        ↓
202 Accepted { message, run }
        ↓
Background worker → rag_service /query
  (original incident + accumulated clarification context เมื่อมี)
        ↓
Backend transaction
  create assistant message
  update thread status
  complete/fail run
```

Frontend สร้าง `idempotency_key` หนึ่งค่าต่อ logical submission เพื่อไม่ให้ retry
สร้างข้อความซ้ำ

## Polling และ follow-up

หลังได้รับ `202` frontend จะอ่าน `GET /chats/{thread_id}` ทุกประมาณหนึ่งวินาที
โดยใช้ thread detail เป็น authoritative state

- `processing`: รอและ poll ต่อ
- `awaiting_followup`: แสดง assistant follow-up และเปิด composer ให้ตอบ
- `idle`: แสดงคำตอบสุดท้ายและหยุด polling
- `failed`: แสดง error; ถ้ารู้ `run_id` สามารถอ่านรายละเอียดจาก run endpoint

เมื่อ thread เป็น `awaiting_followup` คำตอบถัดไปจะถูกบันทึกเป็น user message ตามปกติ
backend สร้าง clarification chain ใหม่จาก messages ที่เรียงลำดับแล้ว จากนั้นสร้าง run operation `query`
และเรียก `rag_service /query` อีกครั้งด้วย incident เดิม รวมคำถามและคำตอบ clarification ที่สะสมไว้

`rag_service` ไม่ได้เป็นเจ้าของ interactive follow-up session และ chat flow ปัจจุบันไม่เรียก `/resume`

Frontend ไม่ถือ RAG session เป็น source of truth และไม่เรียก `rag_service` โดยตรง

## การสลับ thread และ request cancellation

Frontend ใช้สอง guard:

1. `AbortController` ยกเลิก request/poll ของ selection เก่า
2. `selectionGenerationRef` ป้องกัน response เก่ากลับมาเขียน state ของ selection ใหม่

ก่อน apply response ต้องตรวจทั้ง thread ID และ generation เสมอ

## การลบ chat

```text
User confirms deletion
        ↓
DELETE /api/v1/chats/{thread_id}
        ↓
Backend SELECT ... FOR UPDATE
        ↓
DELETE chat_threads row
        ↓
PostgreSQL ON DELETE CASCADE
  ├─ chat_messages
  └─ chat_runs
        ↓
204 No Content
```

ไม่มี migration เพิ่มสำหรับ feature นี้ เพราะ foreign keys ของ `chat_messages.thread_id` และ
`chat_runs.thread_id` มี `ON DELETE CASCADE` อยู่แล้ว

ถ้าลบ active thread frontend จะ:

1. abort polling
2. เพิ่ม selection generation
3. clear active/pending refs ที่เกี่ยวข้อง
4. ลบ thread ออกจาก sidebar
5. เลือก thread ล่าสุดที่เหลือ หรือ clear workspace ถ้าไม่มี thread

ชุด deleted thread IDs ป้องกัน late response หรือ title update นำ thread ที่ลบแล้วกลับเข้า list

การลบ inactive thread ไม่ยกเลิก polling ของ active thread

## ตัวอย่าง request

```powershell
$thread = Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8000/api/v1/chats" `
  -ContentType "application/json" `
  -Body '{"title":"Deletion example"}'

Invoke-WebRequest `
  -Method Delete `
  -Uri "http://localhost:8000/api/v1/chats/$($thread.id)"
```

DELETE สำเร็จต้องได้ status `204` และ response body ว่าง

## Error handling

- Frontend ไม่ลบ local state จน backend ยืนยัน DELETE สำเร็จ
- ถ้าลบ active thread ไม่สำเร็จ frontend โหลด selection เดิมกลับมา
- Polling request มี timeout และ retry สำหรับ transient read failure
- Unknown thread เป็น `404`; duplicate/active-run conflicts ใน message creation ใช้ status ตาม backend contract

## ข้อจำกัดปัจจุบัน

1. ระบบเป็น single-user และ chat routes ยังไม่มี authentication/ownership boundary
2. DELETE เป็น hard delete และยังไม่มี Trash/Restore
3. การลบ processing thread ลบ persisted rows ทันที แต่ไม่สามารถ cancel upstream RAG request ได้
   worker อาจคำนวณต่อจนจบแล้วทิ้งผล เพราะ run/thread ถูกลบแล้ว
4. Report tab เป็น demo-only ที่ประกอบผลใน frontend จาก selected chat เท่านั้น ผลไม่ถูก persist แยกเป็น report,
   ยังไม่ผ่านการ verify และไม่มี backend case/report lifecycle

ก่อนใช้ใน multi-user deployment ต้องเพิ่ม authenticated user ownership และ filter ทุก chat query/delete
ตาม owner

## ไฟล์สำคัญ

- `backend/app/models/chat.py`
- `backend/app/services/chat/chat_management.py`
- `backend/app/services/chat/chat_message.py`
- `backend/app/services/chat/chat_worker.py`
- `backend/app/routers/chat.py`
- `frontend/src/lib/api.ts`
- `frontend/src/app/chat/page.tsx`
- `frontend/src/components/chat/WorkspaceSidebar.tsx`
- `frontend/src/components/chat/DeleteChatDialog.tsx`
