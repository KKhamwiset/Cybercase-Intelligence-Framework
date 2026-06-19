"""
Fine-tune Module — Central Configuration
=========================================
All knobs for turning the local generation model (``qwen2.5:7b``) into a
MITRE ATT&CK specialist, while keeping the original model intact for A/B
comparison.

The original model stays as ``qwen2.5:7b`` in Ollama. The fine-tuned model is
registered separately as ``mitre-qwen:7b`` (see ``export/Modelfile``). Switching
between them in the RAG pipeline is done purely via the ``LOCAL_LLM_MODEL`` env
var — no pipeline code changes required.
"""

from __future__ import annotations

import sys
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
# PATHS
# ──────────────────────────────────────────────────────────────────────────────
MODULE_DIR = Path(__file__).resolve().parent           # rag_service/finetune
RAG_SERVICE_DIR = MODULE_DIR.parent                     # rag_service
REPO_ROOT = MODULE_DIR.parents[1]                       # repo root

# Package root that makes ``GraphRAG`` importable (mirrors eval_runner.py:26).
RAG_PKG_ROOT = RAG_SERVICE_DIR / "app" / "RAG"          # rag_service/app/RAG

# STIX bundles live at the repo root (NOT under rag_service — config.py's
# ATTACK_DOMAINS points at a path that does not exist on disk, so we resolve
# the real location ourselves here).
STIX_DATA_DIR = REPO_ROOT / "Mitre_ATT&CK Doc"
STIX_DOMAIN_DIRS = {
    "enterprise": STIX_DATA_DIR / "enterprise-attack",
    "mobile": STIX_DATA_DIR / "mobile-attack",
    "ics": STIX_DATA_DIR / "ics-attack",
}

# Datasets to hold out (never train on these entities → leak-free generalization
# test). Only the small curated eval set is held out by default: Thai_dataset.json
# (2.2k rows) is derived from nearly the ENTIRE ATT&CK KB, so holding it out would
# leave almost no training data. Treat Thai_dataset as an *in-domain* benchmark
# instead; use eval_dataset.json for the clean, leak-free comparison.
EVAL_DIR = RAG_PKG_ROOT / "GraphRAG" / "evaluation"
HELDOUT_EVAL_FILES = [
    EVAL_DIR / "eval_dataset.json",
]

# Outputs
OUTPUT_DIR = MODULE_DIR / "data" / "output"
TRAIN_FILE = OUTPUT_DIR / "train.jsonl"
VAL_FILE = OUTPUT_DIR / "val.jsonl"
STATS_FILE = OUTPUT_DIR / "dataset_stats.json"

# ──────────────────────────────────────────────────────────────────────────────
# MODELS
# ──────────────────────────────────────────────────────────────────────────────
# Active target = Qwen3.5-4B, trained with 16-bit LoRA. Qwen3.5 is a NEW
# architecture (Gated DeltaNet, bf16-native, thinking-by-default); Unsloth
# explicitly warns AGAINST 4-bit QLoRA for it (quantization error too high), so
# we load the base in 16-bit and train a LoRA on top. Needs transformers v5 + a
# recent unsloth/unsloth_zoo (see requirements.txt).
BASE_MODEL_OLLAMA = "qwen3.5:4b"            # stock model in Ollama = A/B baseline
BASE_MODEL_HF = "Qwen/Qwen3.5-4B"           # HF checkpoint used for training
FT_MODEL_OLLAMA = "mitre-qwen3.5:4b"        # fine-tuned model registered in Ollama

# Previous target — kept for reference (the committed Qwen2.5-7B GGUFs/Modelfiles
# still work; swap these back in to reproduce the v1/v3 7B specialist):
#   BASE_MODEL_OLLAMA = "qwen2.5:7b"
#   BASE_MODEL_HF     = "Qwen/Qwen2.5-7B-Instruct"
#   FT_MODEL_OLLAMA   = "mitre-qwen:7b"

# ──────────────────────────────────────────────────────────────────────────────
# DATASET
# ──────────────────────────────────────────────────────────────────────────────
# Parse only the newest STIX bundle per domain by default (each versioned file
# is ~40 MB; parsing every version is slow and redundant).
USE_LATEST_VERSION_ONLY = True
DOMAINS_TO_BUILD = ["enterprise", "mobile"]   # ICS available but off by default

VAL_SPLIT = 0.08          # ~8% held out for validation
RANDOM_SEED = 42
MAX_DESC_CHARS = 900      # truncate long technique descriptions in answers
MAX_MIT_DESC_CHARS = 280  # per-mitigation blurb cap (first full sentence, word-safe)
MAX_LIST_ITEMS = 12       # cap items in "list" answers (mitigations, techniques…)

# ──────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPTS  (English-only — translation to Thai is a separate downstream
# stage in the pipeline, so the reasoning model is trained to output English.)
# ──────────────────────────────────────────────────────────────────────────────
SPECIALIST_SYSTEM_PROMPT = (
    "You are a MITRE ATT&CK cybersecurity specialist. Answer questions about "
    "ATT&CK techniques, tactics, mitigations, groups, software, and campaigns "
    "accurately and concisely. Always cite ATT&CK IDs (e.g., T1566, G0016, "
    "S0154, M1037, TA0001) for every entity you mention. Base your answers only "
    "on established MITRE ATT&CK knowledge; never fabricate."
)

GROUNDED_SYSTEM_PROMPT = (
    "You are a MITRE ATT&CK cybersecurity specialist. Using ONLY the provided "
    "context, answer the question. Only use ATT&CK IDs (e.g. T1059, G0016, S0154, "
    "M1037, TA0001) that appear in the context; never invent, guess, or recall an "
    "ID from memory — if a name has no ID in the context, write the name without "
    "an ID. Do not add any technique, group, software, mitigation, or fact that is "
    "not in the context. If the context does not contain the answer, say so plainly "
    "and do not guess."
)

# ──────────────────────────────────────────────────────────────────────────────
# TRAINING — 16-bit LoRA, tuned for a free Kaggle/Colab T4 or P100 (16 GB)
# ──────────────────────────────────────────────────────────────────────────────
MAX_SEQ_LEN = 2048
# Qwen3.5: 4-bit QLoRA is NOT recommended (Unsloth) → load the base in 16-bit and
# train a LoRA on top. A 4.7B base in 16-bit (~9.4 GB) + LoRA + activations fits a
# single free T4/P100. (T4 has no bf16 → Unsloth auto-uses fp16; LoRA keeps the
# frozen base stable, unlike a fp16 FULL fine-tune of a bf16-native model.)
LOAD_IN_4BIT = False
LOAD_IN_16BIT = True
# Full fine-tune of a bf16-native 4.7B on fp16-only T4 is unstable and needs
# 2xT4 + DeepSpeed ZeRO-3 — left off by default. Flip to True only on a >=40 GB
# bf16 GPU (A100/H100) or a properly sharded 2xT4 setup.
FULL_FINETUNING = False
# Qwen3.5 is a thinking model (thinking ON by default). Our dataset is direct
# English answers with no <think> blocks, so render the chat template with
# thinking DISABLED at train time to match the pipeline's inference shape.
ENABLE_THINKING = False

LORA_R = 16
LORA_ALPHA = 16
LORA_DROPOUT = 0.0
LORA_TARGET_MODULES = [
    "q_proj", "k_proj", "v_proj", "o_proj",
    "gate_proj", "up_proj", "down_proj",
]

# 1 epoch for Qwen3.5: the base is already strong and the SFT answers are
# template-shaped — a 2nd pass mostly memorises the templates (robotic answers +
# erodes general fluency). Bump back to 2 if the A/B shows under-fitting.
NUM_EPOCHS = 1
LEARNING_RATE = 2e-4
PER_DEVICE_BATCH = 2
GRAD_ACCUM = 8            # effective batch = 16
WARMUP_RATIO = 0.03
WEIGHT_DECAY = 0.01
LR_SCHEDULER = "cosine"
LOGGING_STEPS = 10

# Where training writes the LoRA adapter / merged model (relative to module).
ADAPTER_DIR = MODULE_DIR / "train" / "outputs" / "mitre-qwen-lora"
MERGED_DIR = MODULE_DIR / "export" / "outputs" / "mitre-qwen-merged"
GGUF_DIR = MODULE_DIR / "export" / "outputs" / "gguf"
GGUF_QUANT = "Q4_K_M"


def add_rag_to_path() -> None:
    """Put ``rag_service/app/RAG`` on sys.path so ``import GraphRAG.*`` works.

    Mirrors the bootstrap in evaluation/eval_runner.py so the fine-tune module
    can reuse the existing STIX parser and pipeline helpers unchanged.
    """
    p = str(RAG_PKG_ROOT)
    if p not in sys.path:
        sys.path.insert(0, p)
