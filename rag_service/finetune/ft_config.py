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
# Original — kept untouched for comparison.
BASE_MODEL_OLLAMA = "qwen2.5:7b"
# HF checkpoint used for training (same family/size as the Ollama base).
BASE_MODEL_HF = "Qwen/Qwen2.5-7B-Instruct"
# Fine-tuned model name registered in Ollama (see export/Modelfile).
FT_MODEL_OLLAMA = "mitre-qwen:7b"

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
    "context, answer the question. Cite the ATT&CK ID for every technique you "
    "mention. If the context does not contain the answer, say so plainly."
)

# ──────────────────────────────────────────────────────────────────────────────
# TRAINING (QLoRA) — defaults tuned for a free Colab/Kaggle T4 (16 GB)
# ──────────────────────────────────────────────────────────────────────────────
MAX_SEQ_LEN = 2048
LOAD_IN_4BIT = True

LORA_R = 16
LORA_ALPHA = 16
LORA_DROPOUT = 0.0
LORA_TARGET_MODULES = [
    "q_proj", "k_proj", "v_proj", "o_proj",
    "gate_proj", "up_proj", "down_proj",
]

NUM_EPOCHS = 2
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
