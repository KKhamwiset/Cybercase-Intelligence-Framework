"""
Central Configuration for MITRE ATT&CK GraphRAG
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# ──────────────────────────────────────────────────────────────────────────────
# PATHS
# ──────────────────────────────────────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent.parent

load_dotenv(_SCRIPT_DIR / ".env")
load_dotenv()

# STIX data folders (each contains versioned .json bundles)
_STIX_DATA_DIR = _PROJECT_ROOT / "Mitre_ATT&CK Doc"
if not _STIX_DATA_DIR.exists():
    _STIX_DATA_DIR = _PROJECT_ROOT.parent / "Mitre_ATT&CK Doc"
ENTERPRISE_ATTACK_DIR = _STIX_DATA_DIR / "enterprise-attack"
MOBILE_ATTACK_DIR = _STIX_DATA_DIR / "mobile-attack"
ICS_ATTACK_DIR = _STIX_DATA_DIR / "ics-attack"

# ──────────────────────────────────────────────────────────────────────────────
# EMBEDDING MODEL — BGE-M3 (Hybrid: Dense + Sparse)
# ──────────────────────────────────────────────────────────────────────────────
EMBED_MODEL = "BAAI/bge-m3"
EMBED_DIM = 1024  # BGE-M3 dense vector dimension


# ──────────────────────────────────────────────────────────────────────────────
# INFERENCE DEVICE — auto-detect GPU, else CPU
# ──────────────────────────────────────────────────────────────────────────────
# BGE-M3 and the cross-encoder reranker run on GPU when one is available (local
# dev), else CPU (Railway prod ships the CPU torch wheel + a slim base image, so
# there is no GPU there). fp16 is a GPU optimization — on CPU it is emulated and
# slower, so it is enabled ONLY on CUDA. Override with RAG_DEVICE=cpu|cuda (set
# in the shell BEFORE start so it takes effect before torch initializes CUDA).
def _resolve_device() -> str:
    forced = os.getenv("RAG_DEVICE", "").strip().lower()
    if forced == "cpu":
        os.environ["CUDA_VISIBLE_DEVICES"] = "-1"  # hide GPU from all torch models
        return "cpu"
    try:
        import torch
        if forced == "cuda":
            if not torch.cuda.is_available():
                print("[CONFIG] RAG_DEVICE=cuda but no CUDA device; using CPU")
                return "cpu"
            return "cuda"
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


DEVICE = _resolve_device()
USE_FP16 = DEVICE == "cuda"  # fp16 only on GPU; CPU uses fp32
print(f"[CONFIG] Inference device: {DEVICE} (fp16={USE_FP16})")

# ──────────────────────────────────────────────────────────────────────────────
# LEGACY — E5 Configuration (kept for reference / rollback)
# ──────────────────────────────────────────────────────────────────────────────
# EMBED_MODEL = "intfloat/multilingual-e5-large"
# EMBED_DIM = 1024
# E5_QUERY_PREFIX = "query: "
# E5_PASSAGE_PREFIX = "passage: "

# ──────────────────────────────────────────────────────────────────────────────
# QDRANT — Vector Database (replaces ChromaDB)
# ──────────────────────────────────────────────────────────────────────────────
# Supports: local Docker, Qdrant Cloud, or in-memory (fallback)
QDRANT_HOST = os.getenv("QDRANT_HOST")
_qdrant_port_str = os.getenv("QDRANT_PORT")
QDRANT_PORT = int(_qdrant_port_str) if _qdrant_port_str else 6333
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_URL = os.getenv(
    "QDRANT_URL"
)  # Full URL for Qdrant Cloud (e.g., https://xxx.aws.cloud.qdrant.io)

QDRANT_COLLECTION_ENTITIES = os.getenv("QDRANT_COLLECTION_ENTITIES", "mitre_entities")
QDRANT_COLLECTION_RELATIONSHIPS = os.getenv(
    "QDRANT_COLLECTION_RELATIONSHIPS", "mitre_relationships"
)

# ──────────────────────────────────────────────────────────────────────────────
# LEGACY — ChromaDB Configuration (kept for reference / rollback)
# ──────────────────────────────────────────────────────────────────────────────
CHROMA_DIR = _SCRIPT_DIR / "chroma_db"
CHROMA_HOST = os.getenv("CHROMA_HOST")
CHROMA_PORT = os.getenv("CHROMA_PORT", "8000")
CHROMA_SSL = os.getenv("CHROMA_SSL", "False").lower() == "true"
CHROMA_API_KEY = os.getenv("CHROMA_API_KEY")
CHROMA_COLLECTION_ENTITIES = "mitre_entities"
CHROMA_COLLECTION_RELATIONSHIPS = "mitre_relationships"

# ──────────────────────────────────────────────────────────────────────────────
# HYBRID RETRIEVAL — RRF (Reciprocal Rank Fusion)
# ──────────────────────────────────────────────────────────────────────────────
RRF_K = 60  # Standard RRF constant: score = 1 / (k + rank)
DENSE_WEIGHT = 1.0  # Weight for dense (semantic) results in RRF
SPARSE_WEIGHT = 1.0  # Weight for sparse (lexical/keyword) results in RRF
# Tip: For CTI domain, try SPARSE_WEIGHT=1.2 to boost exact ID matches

# ──────────────────────────────────────────────────────────────────────────────
# NEO4J
# ──────────────────────────────────────────────────────────────────────────────
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# ──────────────────────────────────────────────────────────────────────────────
# LLM (Claude & OpenRouter)
# ──────────────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
LLM_MODEL = "claude-haiku-4-5"
LLM_MAX_TOKENS = 4096
LLM_TEMPERATURE = 0

# Single-call generation (benchmark variant C): for Thai queries the
# reasoning LLM writes the final Thai answer directly — no separate
# translation stage. Measured statistically equal to the two-stage path
# (ID-F1 delta -0.011, CI crosses 0) at 2.3x lower latency and 44% fewer
# output tokens on 45 incident samples; the translation stage never
# altered ATT&CK IDs (id_survival 1.0). See
# evaluation/results/crosslingual_generation_report.md. Set to "false"
# to roll back to the two-stage reason->translate path.
SINGLE_CALL_GENERATION = (
    os.getenv("SINGLE_CALL_GENERATION", "true").lower() == "true"
)

# Ultrafast mode (--ultrafast): vector-only retrieve (no graph) + terse, capped
# output. Output-token count dominates LLM latency, so the answer is short.
ULTRAFAST_MAX_TOKENS = int(os.getenv("ULTRAFAST_MAX_TOKENS", "1024"))
ULTRAFAST_TOP_K = int(os.getenv("ULTRAFAST_TOP_K", "6"))

EVALUATOR_LLM_MODEL = "claude-haiku-4-5"
EVALUATOR_MAX_TOKENS = (
    1024  # Must fit: verdict + reason + covered/missing phases + rewritten_query
)
EVALUATOR_TEMPERATURE = 0

RAGAS_LLM_MODEL = "qwen/qwen-2.5-72b-instruct"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# ──────────────────────────────────────────────────────────────────────────────
# THANOY — Thai legal AI (iApp) for the report's "legal advice" section.
# A SEPARATE specialist from the MITRE pipeline: our pipeline explains the
# technical incident, Thanoy maps it to Thai law (Computer Crime Act, Cybersecurity
# Act, Criminal Code …). OPTIONAL — if THANOY_API_KEY is unset, the legal section
# is simply skipped (the report still renders). Docs: iapp.co.th/docs/llm/thanoy-legal
# ──────────────────────────────────────────────────────────────────────────────
THANOY_API_KEY = os.getenv("THANOY_API_KEY", "")
THANOY_API_URL = os.getenv("THANOY_API_URL", "https://api.iapp.co.th/thanoy")
THANOY_TIMEOUT = float(os.getenv("THANOY_TIMEOUT", "30"))
THANOY_ENABLED = bool(THANOY_API_KEY)

# ──────────────────────────────────────────────────────────────────────────────
# LOCAL MODELS (Ollama) — used when --local flag is passed
# Install: https://ollama.com  |  pip install langchain-ollama
# Pull   : ollama pull qwen2.5:7b && ollama pull gemma3:4b
# ──────────────────────────────────────────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Model 1 — Pipeline  (reasoning + translation + routing)
# qwen2.5:7b  Q4_K_M ≈ 4.1 GB VRAM  |  best multilingual in 7B class, good Thai support
LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "qwen2.5:7b")

# Model 2 — Evaluation judge  (context sufficiency + query merger + offline RAGAS)
# gemma3:4b   Q4_K_M ≈ 2.6 GB VRAM  |  different family → lower judge bias
LOCAL_EVAL_MODEL = os.getenv("LOCAL_EVAL_MODEL", "gemma3:4b")

# Master switch — when true the SERVICE runs the WHOLE pipeline on local Ollama
# models (reasoning + translation + routing + report) instead of Claude, mirroring
# the CLI's --local flag. Set USE_LOCAL=true in the env to enable.
USE_LOCAL = os.getenv("USE_LOCAL", "false").lower() in ("1", "true", "yes")

# Context window for local Ollama models. ChatOllama otherwise defaults to a small
# num_ctx and SILENTLY truncates large prompts (decomposition input + retrieved
# context) → degenerate/empty output. Must comfortably hold the incident text.
LOCAL_NUM_CTX = int(os.getenv("LOCAL_NUM_CTX", "8192"))

# ──────────────────────────────────────────────────────────────────────────────
# RETRIEVAL
# ──────────────────────────────────────────────────────────────────────────────
VECTOR_TOP_K = 10  # Initial vector retrieval count
GRAPH_EXPANSION_DEPTH = 2  # How many hops to expand in graph
FINAL_TOP_K = 5  # After reranking

# Restrict entity vector search to one ATT&CK domain. The corpus is ingested with
# mobile + enterprise, but mobile entities (Pegasus, FluBot, mobile-only Phishing
# variants) pollute enterprise incident analysis. Set to "" / unset to disable.
# NOTE: only the ENTITY collection is domain-tagged; relationships are not, so a
# few mobile relationship hits can still slip through — re-ingest enterprise-only
# for a 100% clean corpus.
ATTACK_DOMAIN_FILTER = os.getenv("ATTACK_DOMAIN_FILTER", "enterprise").strip() or None

# Reranker — must handle Thai↔English pairs when DUAL_QUERY_RETRIEVAL is on
# (mmarco-mMiniLMv2 was trained on 14 mMARCO languages, Thai not included)
RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"

# MITRE mapping table sent to the backend: vector hits below this rerank score
# (sigmoid [0,1] × type weight) are dropped unless the answer cites them.
# Calibrated against live Qdrant data (2026-07-03): the cross-encoder saturates
# at sigmoid≈0.500 for no-signal pairs, so after the ×1.2 Technique weight the
# noise floor sits at 0.600 — irrelevant techniques score 0.600-0.607, genuinely
# relevant ones 0.65-0.87. 0.62 cuts the floor while keeping real signal.
MITRE_TABLE_SCORE_THRESHOLD = float(os.getenv("MITRE_TABLE_SCORE_THRESHOLD", "0.62"))

# ──────────────────────────────────────────────────────────────────────────────
# LEGACY — mmarco reranker (kept for reference / rollback)
# ──────────────────────────────────────────────────────────────────────────────
# RERANKER_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"

# ──────────────────────────────────────────────────────────────────────────────
# CROSS-LINGUAL RETRIEVAL — Dual-Query (Thai original + English translation)
# ──────────────────────────────────────────────────────────────────────────────
# Translate-then-retrieve alone (tRAG) makes the LLM translation a single
# point of failure: one bad translation poisons dense, sparse, and every
# follow-up rewrite (cf. arXiv:2504.03616). With dual-query the original
# Thai query is retrieved in parallel — BGE-M3's cross-lingual dense space
# and exact English keywords embedded in the Thai text (sparse) can recover
# results the translation missed.
DUAL_QUERY_RETRIEVAL = os.getenv("DUAL_QUERY_RETRIEVAL", "true").lower() == "true"

# ──────────────────────────────────────────────────────────────────────────────
# DOMAINS
# ──────────────────────────────────────────────────────────────────────────────
# Ingest historical files (default: False, parsing only latest enterprise-attack.json / mobile-attack.json)
INGEST_HISTORICAL = os.getenv("INGEST_HISTORICAL", "false").lower() in ("1", "true", "yes")

ATTACK_DOMAINS = {"enterprise": ENTERPRISE_ATTACK_DIR, "mobile": MOBILE_ATTACK_DIR}


# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────
def sep(title=""):
    """Print a separator line for console output."""
    width = 72
    if title:
        pad = (width - len(title) - 2) // 2
        print("\n" + "─" * pad + f" {title} " + "─" * pad)
    else:
        print("\n" + "─" * width)

print(ATTACK_DOMAINS.items())