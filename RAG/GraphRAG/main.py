"""
MITRE ATT&CK GraphRAG — CLI Entrypoint
========================================
Usage:
    python main.py --ingest       # Parse STIX data → load Neo4j + ChromaDB
    python main.py --test          # Run test queries
    python main.py                 # Interactive mode
    python main.py --retrieve-only # Retrieval without LLM (for debugging)
"""

# ──────────────────────────────────────────────────────────────────────────────
# UTF-8 FIX FOR WINDOWS
# ──────────────────────────────────────────────────────────────────────────────
import sys
import io

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace"
    )

# ──────────────────────────────────────────────────────────────────────────────
# IMPORTS
# ──────────────────────────────────────────────────────────────────────────────
import argparse
from sentence_transformers import SentenceTransformer

from config import (
    EMBED_MODEL,
    CHROMA_DIR,
    ENTERPRISE_ATTACK_JSON,
    MOBILE_ATTACK_JSON,
    sep,
)


# ──────────────────────────────────────────────────────────────────────────────
# INGEST
# ──────────────────────────────────────────────────────────────────────────────
def run_ingest():
    """Parse STIX data and load into Neo4j + ChromaDB."""
    from ingestion.stix_parser import StixParser
    from ingestion.graph_loader import GraphLoader
    from ingestion.vector_loader import VectorLoader

    sep("STIX PARSING")

    parser = StixParser()

    # Parse enterprise
    if ENTERPRISE_ATTACK_JSON.exists():
        parser.parse_file(ENTERPRISE_ATTACK_JSON, domain="enterprise")
    else:
        print(f"[ERROR] {ENTERPRISE_ATTACK_JSON} not found!")
        return

    # Parse mobile
    if MOBILE_ATTACK_JSON.exists():
        parser.parse_file(MOBILE_ATTACK_JSON, domain="mobile")
    else:
        print(f"[WARN] {MOBILE_ATTACK_JSON} not found — skipping mobile domain")
        print(f"       Download from: https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/mobile-attack/mobile-attack.json")

    print(f"\n[PARSE] Total: {len(parser.entities)} entities, {len(parser.relationships)} relationships")

    # Load into Neo4j
    sep("NEO4J INGESTION")
    graph_loader = GraphLoader()
    try:
        graph_loader.load_all(parser)
    finally:
        graph_loader.close()

    # Load into ChromaDB
    sep("CHROMADB INGESTION")
    print(f"[EMBED] Loading {EMBED_MODEL}...")
    embed_model = SentenceTransformer(EMBED_MODEL)

    vector_loader = VectorLoader(embed_model=embed_model)
    vector_loader.load_all(parser)

    sep("INGESTION COMPLETE")
    print("✓ Neo4j: Graph loaded with nodes + edges")
    print("✓ ChromaDB: Entity + relationship embeddings stored")
    print(f"✓ ChromaDB path: {CHROMA_DIR}")


# ──────────────────────────────────────────────────────────────────────────────
# TEST
# ──────────────────────────────────────────────────────────────────────────────
TEST_QUERIES = [
    # Thai queries
    "APT29 ใช้เทคนิคอะไรบ้าง",
    "วิธีป้องกัน Phishing มีอะไรบ้าง",
    "กลุ่มแฮกเกอร์ที่ใช้ Scheduled Task มีกลุ่มไหนบ้าง",

    # English queries
    "What techniques does Lazarus Group use?",
    "How do adversaries steal credentials from web browsers?",
]


def run_tests(retrieve_only: bool = False):
    """Run test queries."""
    from pipeline.chain import GraphRAGChain

    chain = GraphRAGChain()

    sep("TEST SUITE")
    print(f"Running {len(TEST_QUERIES)} test queries")
    print(f"Mode: {'retrieve-only' if retrieve_only else 'full pipeline'}")

    try:
        for i, query in enumerate(TEST_QUERIES, 1):
            print(f"\n{'=' * 72}")
            print(f"  TEST {i}/{len(TEST_QUERIES)}")
            print(f"{'=' * 72}")

            if retrieve_only:
                context = chain.retrieve_only(query)
                sep("RETRIEVED CONTEXT")
                print(context[:2000])
                sep()
            else:
                chain.query(query, verbose=True)
    finally:
        chain.close()


# ──────────────────────────────────────────────────────────────────────────────
# INTERACTIVE
# ──────────────────────────────────────────────────────────────────────────────
def run_interactive(retrieve_only: bool = False):
    """Interactive query mode."""
    from pipeline.chain import GraphRAGChain

    chain = GraphRAGChain()

    mode = "RETRIEVE-ONLY" if retrieve_only else "FULL PIPELINE"

    print(f"\n{'=' * 72}")
    print(f"  MITRE ATT&CK GraphRAG — Interactive Mode ({mode})")
    print(f"  Type 'quit' or 'q' to exit")
    print(f"  Supports Thai and English queries")
    print(f"{'=' * 72}")

    try:
        while True:
            try:
                query = input("\n🔍 Query> ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nBye!")
                break

            if query.lower() in ("exit", "quit", "q"):
                print("Bye!")
                break

            if not query:
                continue

            if retrieve_only:
                context = chain.retrieve_only(query)
                sep("RETRIEVED CONTEXT")
                print(context[:3000])
                sep()
            else:
                chain.query(query, verbose=True)
    finally:
        chain.close()


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────
def main():
    arg_parser = argparse.ArgumentParser(
        description="MITRE ATT&CK GraphRAG Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --ingest          # Load data into Neo4j + ChromaDB
  python main.py --test            # Run test queries (full pipeline)
  python main.py --test --retrieve-only  # Test retrieval without LLM
  python main.py                   # Interactive mode
        """,
    )

    arg_parser.add_argument(
        "--ingest",
        action="store_true",
        help="Parse STIX data and load into Neo4j + ChromaDB",
    )

    arg_parser.add_argument(
        "--test",
        action="store_true",
        help="Run test queries",
    )

    arg_parser.add_argument(
        "--retrieve-only",
        action="store_true",
        help="Retrieval without LLM generation (for debugging)",
    )

    args = arg_parser.parse_args()

    if args.ingest:
        run_ingest()
    elif args.test:
        run_tests(retrieve_only=args.retrieve_only)
    else:
        run_interactive(retrieve_only=args.retrieve_only)


if __name__ == "__main__":
    main()
