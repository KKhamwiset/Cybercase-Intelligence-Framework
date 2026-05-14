"""
Central Configuration for MITRE ATT&CK GraphRAG
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────────────────────────────────────
# PATHS
# ──────────────────────────────────────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent

# STIX data files
ENTERPRISE_ATTACK_JSON = _PROJECT_ROOT / "enterprise-attack.json"
MOBILE_ATTACK_JSON = _PROJECT_ROOT / "mobile-attack.json"

# ChromaDB persistent storage
CHROMA_DIR = _SCRIPT_DIR / "chroma_db"

# ──────────────────────────────────────────────────────────────────────────────
# EMBEDDING MODEL
# ──────────────────────────────────────────────────────────────────────────────
EMBED_MODEL = "intfloat/multilingual-e5-large"
EMBED_DIM = 1024

# E5 models require "query: " / "passage: " prefixes
E5_QUERY_PREFIX = "query: "
E5_PASSAGE_PREFIX = "passage: "

# ──────────────────────────────────────────────────────────────────────────────
# NEO4J
# ──────────────────────────────────────────────────────────────────────────────
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# ──────────────────────────────────────────────────────────────────────────────
# LLM (Claude)
# ──────────────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
LLM_MODEL = "claude-sonnet-4-20250514"
LLM_MAX_TOKENS = 4096
LLM_TEMPERATURE = 0

# ──────────────────────────────────────────────────────────────────────────────
# RETRIEVAL
# ──────────────────────────────────────────────────────────────────────────────
VECTOR_TOP_K = 10          # Initial vector retrieval count
GRAPH_EXPANSION_DEPTH = 2  # How many hops to expand in graph
FINAL_TOP_K = 5            # After reranking

# Reranker
RERANKER_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"

# ──────────────────────────────────────────────────────────────────────────────
# CHROMA COLLECTION NAMES
# ──────────────────────────────────────────────────────────────────────────────
CHROMA_COLLECTION_ENTITIES = "mitre_entities"
CHROMA_COLLECTION_RELATIONSHIPS = "mitre_relationships"

# ──────────────────────────────────────────────────────────────────────────────
# DOMAINS
# ──────────────────────────────────────────────────────────────────────────────
ATTACK_DOMAINS = {
    "enterprise": ENTERPRISE_ATTACK_JSON,
    "mobile": MOBILE_ATTACK_JSON,
}

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
