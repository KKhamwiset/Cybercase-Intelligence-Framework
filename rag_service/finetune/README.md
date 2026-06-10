# Fine-tune Module — MITRE ATT&CK Specialist

Fine-tune โมเดล local ที่ใช้ **generate คำตอบ** (`qwen2.5:7b` ผ่าน Ollama) ให้กลายเป็น
**cybersecurity MITRE ATT&CK specialist** โดย **เก็บโมเดลเดิมไว้** เพื่อเทียบ 2 โมเดล (A/B)

> โมเดลเดิม `qwen2.5:7b` ไม่ถูกแตะ ตัว fine-tuned จะถูกลงทะเบียนเป็นโมเดลแยกชื่อ
> `mitre-qwen:7b` ใน Ollama → สลับใช้ใน pipeline ผ่าน env `LOCAL_LLM_MODEL` ตัวเดียว
> โดย **ไม่ต้องแก้โค้ด pipeline เลย**

## ทำไมต้องเทรนบน Cloud
GPU ของเครื่องนี้ (RTX 2050, **VRAM 4 GB**) ไม่พอ fine-tune โมเดล 7B (QLoRA ต้องการ
~12–16 GB) → **เทรนบน Cloud GPU ฟรี (Colab/Kaggle T4 16 GB)** แล้ว export เป็น GGUF
กลับมารันใน Ollama เครื่องนี้ (inference 7B Q4 รันบนเครื่องได้ปกติ)

## โครงสร้าง
```
finetune/
├── ft_config.py            # ค่ากลางทั้งหมด (โมเดล, paths, LoRA/training hyperparams)
├── requirements.txt        # deps ตอนเทรน — ติดตั้งเฉพาะบน cloud
├── data/
│   ├── build_dataset.py    # STIX → train.jsonl/val.jsonl  (รันบนเครื่องนี้ได้)
│   ├── templates.py        # Q&A templates ต่อ category
│   └── output/             # ผลลัพธ์ (gitignored)
├── train/
│   ├── train_unsloth.py    # QLoRA trainer (รันบน cloud)
│   └── Finetune_Colab.ipynb
├── export/
│   ├── merge_and_gguf.py   # merge LoRA → GGUF (ทางเลือกแบบ llama.cpp)
│   └── Modelfile           # Ollama Modelfile → mitre-qwen:7b
└── compare/
    └── run_comparison.py   # รัน eval เดิมกับ 2 โมเดล → ตาราง side-by-side
```

---

## ขั้นตอน

### 1) สร้างชุดข้อมูล (รันบนเครื่องนี้)
```powershell
cd rag_service/finetune
python data/build_dataset.py --max-per-category 600
```
- ดึงข้อมูลจาก STIX bundle ล่าสุด (enterprise + mobile) ด้วย `StixParser` เดิม
- สร้างคู่ถาม-ตอบ **ภาษาอังกฤษ** เลียนฟอร์แมต `reference_answer` ของชุด eval
  (เพราะ reasoning LLM ใน pipeline output เป็นอังกฤษ — การแปลไทยเป็น stage แยก)
- ครอบคลุม category เดียวกับชุด eval: `technique_lookup`, `mitigation_lookup`,
  `technique_groups`, `group_techniques`, `group_software`, `software_techniques`,
  `software_type_query`, `tactic_techniques`, `campaign_attribution`
- ได้ไฟล์ `data/output/train.jsonl`, `val.jsonl`, `dataset_stats.json`

**Holdout (สำคัญ):**
- default `--holdout none` = เทรนทั้ง KB → เป็น specialist เต็มตัว
- `--holdout ids` = ตัด entity ที่อยู่ใน `eval_dataset.json` ออก (test รั่วน้อยลง แต่ชุดเล็กลงมาก
  เพราะคำถามแบบ list ใน eval อ้าง id จำนวนมหาศาล จนตัด software เกือบทั้ง KB)
- คำแนะนำ: ใช้ `none` เพื่อสร้างโมเดล แล้วตีความผล A/B ว่าเป็น *in-domain knowledge absorption*
  (train/eval ใช้คนละสำนวนคำถาม) — ถ้าต้องการ test รั่วน้อยให้ build เพิ่มด้วย `--holdout ids`

> หมายเหตุ: STIX export ชุดนี้ไม่มี `detects` relationship → category `technique_detection`
> จะว่าง เป็นเรื่องปกติ

### 2) เทรน QLoRA (บน Cloud GPU)
**ทางที่ง่ายสุด — Colab:** เปิด `train/Finetune_Colab.ipynb` บน Google Colab (เลือก runtime
GPU T4) แล้วกดรันทีละ cell (clone repo → upload `train.jsonl`/`val.jsonl` → train → export GGUF)

**หรือรัน script เอง** (บนเครื่อง cloud/WSL ที่มี GPU ≥12 GB):
```bash
cd rag_service/finetune
pip install -r requirements.txt    # Colab: ใช้ one-liner ใน requirements.txt
python train/train_unsloth.py --max-steps 5     # smoke test ก่อน
python train/train_unsloth.py --gguf            # เทรนจริง + export GGUF Q4_K_M
```
- base: `Qwen/Qwen2.5-7B-Instruct` (ตระกูล/ขนาดเดียวกับ Ollama base → เทียบ apples-to-apples)
- QLoRA 4-bit, LoRA r=16, train เฉพาะ assistant tokens, 2 epochs (แก้ได้ใน `ft_config.py`)

### 3) Export + ลงทะเบียนใน Ollama (บนเครื่องนี้)
หลังได้ไฟล์ `.gguf` (จากขั้นตอน 2) วางไว้ที่ `export/outputs/gguf/` แล้ว:
```powershell
cd rag_service/finetune
# ปรับ FROM ใน export/Modelfile ให้ตรงชื่อไฟล์ .gguf จริงก่อน
ollama create mitre-qwen:7b -f export/Modelfile
ollama run mitre-qwen:7b "What is T1105?"
```
ตรวจว่ามีทั้ง 2 โมเดล:
```powershell
ollama list      # ต้องเห็นทั้ง qwen2.5:7b และ mitre-qwen:7b
```

> ทางเลือก (ไม่ใช้ Unsloth GGUF): ใช้ `export/merge_and_gguf.py` เพื่อ merge adapter แล้ว
> แปลงด้วย llama.cpp เอง

### 4) เปรียบเทียบ 2 โมเดล
ต้องมี Neo4j + Qdrant ขึ้น (`docker-compose up -d`) และ ingest แล้ว + Ollama เสิร์ฟทั้ง 2 โมเดล
```powershell
cd rag_service/finetune
python compare/run_comparison.py --max-samples 20
```
- รัน generation eval เดิม (`eval_runner.py`) สองรอบ สลับ `LOCAL_LLM_MODEL` (base → ft)
- พิมพ์ตาราง side-by-side: Faithfulness / Answer Relevancy / Answer Correctness / Token F1 /
  ROUGE-L / BERTScore / Latency พร้อม Δ
- เขียนผลที่ `compare/comparison_<dataset>.md`

---

## หมายเหตุทางเทคนิค
- **ไม่แตะโค้ด pipeline เดิม** — การสลับโมเดลทำผ่าน env `LOCAL_LLM_MODEL` ที่ `config.py` อ่านอยู่แล้ว
- ตัว fine-tuned เป็น LoRA บนโมเดล instruct เดิม → ความสามารถทั่วไป (แปล/route ในโหมด `--local`)
  ยังอยู่ ขณะที่เพิ่มความรู้ MITRE
- deps การเทรนติดตั้ง **เฉพาะบน cloud** — ไม่ยุ่งกับ `rag_service/requirements.txt`
