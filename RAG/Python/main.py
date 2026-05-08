import sys
import io
import argparse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer,
        encoding="utf-8",
        errors="replace"
    )

import config
from models import setup_models
from ingestion import load_documents, build_nodes
from indexing import build_index, load_index
from query_engine import rag_query

TEST_QUERIES = [
    "PDPA คืออะไร",
    "บทลงโทษของ พ.ร.บ.คอมพิวเตอร์ คืออะไร",
    "มาตรการด้าน Cybersecurity ของไทยมีอะไรบ้าง",
    "ธุรกรรมอิเล็กทรอนิกส์คืออะไร",
    "What penalties exist under Computer Crime Act?",
]

def run_tests(index):
    config.sep("TEST SUITE")

    for i, q in enumerate(TEST_QUERIES, 1):
        print(f"\nTEST {i}/{len(TEST_QUERIES)}")
        rag_query(index, q)

def main():
    parser = argparse.ArgumentParser(
        description="Advanced Legal RAG"
    )

    parser.add_argument(
        "--ingest",
        action="store_true"
    )

    parser.add_argument(
        "--test",
        action="store_true"
    )

    args = parser.parse_args()

    # models
    setup_models()

    # ingest
    if args.ingest or not config.INDEX_DIR.exists():
        config.sep("INGESTION")

        documents = load_documents()
        nodes = build_nodes(documents)
        index = build_index(nodes)
    else:
        index = load_index()

    # tests
    if args.test:
        run_tests(index)
        return

    # interactive
    print("\n" + "=" * 72)
    print("  LEGAL RAG INTERACTIVE MODE")
    print("=" * 72)

    while True:
        try:
            query = input("\nQuery> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye!")
            break

        if query.lower() in ["exit", "quit", "q"]:
            print("Bye!")
            break

        if not query:
            continue

        rag_query(index, query)

if __name__ == "__main__":
    main()
