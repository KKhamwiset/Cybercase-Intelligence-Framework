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
# From rag_service/app/RAG/GraphRAG/ to root:
# 1. GraphRAG/ -> RAG/
# 2. RAG/ -> app/
# 3. app/ -> rag_service/
# 4. rag_service/ -> root
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent.parent.parent

load_dotenv(_SCRIPT_DIR / ".env")
load_dotenv()

# STIX data folders (each contains versioned .json bundles)
_STIX_DATA_DIR = _PROJECT_ROOT / "Mitre_ATT&CK Doc"
ENTERPRISE_ATTACK_DIR = _STIX_DATA_DIR / "enterprise-attack"
MOBILE_ATTACK_DIR = _STIX_DATA_DIR / "mobile-attack"
ICS_ATTACK_DIR = _STIX_DATA_DIR / "ics-attack"

# ──────────────────────────────────────────────────────────────────────────────
# EMBEDDING MODEL — BGE-M3 (Hybrid: Dense + Sparse)
# ──────────────────────────────────────────────────────────────────────────────
EMBED_MODEL = "BAAI/bge-m3"
EMBED_DIM = 1024  # BGE-M3 dense vector dimension
USE_FP16 = True  # Halve memory usage (~2.3GB → ~1.2GB)

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
LLM_MODEL = "claude-sonnet-4-20250514"
LLM_MAX_TOKENS = 4096
LLM_TEMPERATURE = 0

RAGAS_LLM_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# ──────────────────────────────────────────────────────────────────────────────
# RETRIEVAL
# ──────────────────────────────────────────────────────────────────────────────
VECTOR_TOP_K = 10  # Initial vector retrieval count
GRAPH_EXPANSION_DEPTH = 2  # How many hops to expand in graph
FINAL_TOP_K = 5  # After reranking

# Reranker
RERANKER_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"

# ──────────────────────────────────────────────────────────────────────────────
# DOMAINS
# ──────────────────────────────────────────────────────────────────────────────
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
