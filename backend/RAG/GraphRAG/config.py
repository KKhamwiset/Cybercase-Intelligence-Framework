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
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent.parent

# STIX data folders (each contains versioned .json bundles)
_STIX_DATA_DIR = _PROJECT_ROOT / "Mitre_ATT&CK Doc"
ENTERPRISE_ATTACK_DIR = _STIX_DATA_DIR / "enterprise-attack"
MOBILE_ATTACK_DIR = _STIX_DATA_DIR / "mobile-attack"
ICS_ATTACK_DIR = _STIX_DATA_DIR / "ics-attack"

# ChromaDB persistent storage
CHROMA_DIR = _SCRIPT_DIR / "chroma_db"

# Remote ChromaDB (Railway)
CHROMA_HOST = os.getenv("CHROMA_HOST")
CHROMA_PORT = os.getenv("CHROMA_PORT", "8000")
CHROMA_SSL = os.getenv("CHROMA_SSL", "False").lower() == "true"
CHROMA_API_KEY = os.getenv("CHROMA_API_KEY")

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
# NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
# NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
# NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_URI = "neo4j+s://71750b02.databases.neo4j.io"
NEO4J_USER = "71750b02"
NEO4J_PASSWORD = "4iS9NVZOgemWn3ZPwskAIAUJASd7DEw1Pi7RSRasP6I"

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
# CHROMA COLLECTION NAMES
# ──────────────────────────────────────────────────────────────────────────────
CHROMA_COLLECTION_ENTITIES = "mitre_entities"
CHROMA_COLLECTION_RELATIONSHIPS = "mitre_relationships"

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
