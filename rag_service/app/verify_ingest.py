"""
Verification Script for Ingested MITRE ATT&CK Data
==================================================
1. Verifies that the offline STIX parser successfully filters out T1527.
2. Connects to the active Neo4j database to assert T1527 node does not exist.
3. Connects to the active Qdrant database to assert T1527 vectors do not exist.
"""

import sys
from pathlib import Path

# Add project app directory to path
_APP_DIR = Path(__file__).resolve().parent
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from RAG.GraphRAG.ingestion.stix_parser import parse_all_domains
from RAG.GraphRAG.config import (
    QDRANT_URL,
    QDRANT_HOST,
    QDRANT_PORT,
    QDRANT_API_KEY,
    QDRANT_COLLECTION_ENTITIES,
    NEO4J_URI,
    NEO4J_USER,
    NEO4J_PASSWORD,
)


def verify_parser():
    print("=" * 60)
    print("1. RUNNING OFFLINE PARSER VERIFICATION")
    print("=" * 60)

    try:
        parser = parse_all_domains()
    except Exception as e:
        print(f"[-] Parser failed to run: {e}")
        return False

    print("\n[+] Parser entity counts by label:")
    counts = {}
    for entity in parser.entities:
        counts[entity.node_label] = counts.get(entity.node_label, 0) + 1
    for label, count in sorted(counts.items()):
        print(f"    - {label}: {count}")

    print(f"\n[+] Total tombstoned IDs collected: {len(parser.tombstoned_ids)}")

    # Check for T1527 presence
    t1527_found = [e for e in parser.entities if e.attack_id == "T1527"]
    if t1527_found:
        print("[-] FAILED: T1527 found in parser entities!")
        for e in t1527_found:
            print(f"    STIX ID: {e.stix_id}, Name: {e.name}")
        return False
    else:
        print("[+] SUCCESS: T1527 is NOT present in final parsed entities.")
        return True


def verify_neo4j():
    print("\n" + "=" * 60)
    print("2. RUNNING NEO4J DATABASE VERIFICATION")
    print("=" * 60)

    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        print(f"[+] Connecting to Neo4j at {NEO4J_URI}...")
        
        with driver.session() as session:
            result = session.run("MATCH (n:Entity {attack_id: 'T1527'}) RETURN count(n) AS c").single()
            count = result["c"] if result else 0

        driver.close()

        if count > 0:
            print(f"[-] FAILED: Neo4j contains {count} node(s) with attack_id == 'T1527'")
            return False
        else:
            print("[+] SUCCESS: Neo4j contains 0 nodes with attack_id == 'T1527'")
            return True
    except Exception as e:
        print(f"[-] Warning: Failed to check Neo4j: {e}")
        print("    (If Neo4j is not running locally or credentials are not configured, skip this check.)")
        return None


def verify_qdrant():
    print("\n" + "=" * 60)
    print("3. RUNNING QDRANT VECTOR DATABASE VERIFICATION")
    print("=" * 60)

    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        if QDRANT_URL:
            print(f"[+] Connecting to Qdrant Cloud: {QDRANT_URL}...")
            client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        elif QDRANT_HOST:
            print(f"[+] Connecting to Qdrant local: {QDRANT_HOST}:{QDRANT_PORT}...")
            client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, api_key=QDRANT_API_KEY)
        else:
            print("[-] Skip: Qdrant configuration is in-memory or not set.")
            return None

        if not client.collection_exists(QDRANT_COLLECTION_ENTITIES):
            print(f"[-] Skip: Collection '{QDRANT_COLLECTION_ENTITIES}' does not exist yet.")
            return None

        # Scroll all items and filter in Python to avoid payload index requirements
        scroll_result, _ = client.scroll(
            collection_name=QDRANT_COLLECTION_ENTITIES,
            limit=10000,
            with_payload=True,
            with_vectors=False
        )

        found_points = []
        for point in scroll_result:
            payload = point.payload or {}
            if payload.get("attack_id") == "T1527":
                found_points.append(point)

        if found_points:
            print(f"[-] FAILED: Qdrant contains {len(found_points)} vector(s) with attack_id == 'T1527'")
            for point in found_points:
                print(f"    Point ID: {point.id}, Payload: {point.payload}")
            return False
        else:
            print("[+] SUCCESS: Qdrant contains 0 vectors with attack_id == 'T1527'")
            return True
    except Exception as e:
        print(f"[-] Warning: Failed to check Qdrant: {e}")
        print("    (If Qdrant is not running or credentials are not configured, skip this check.)")
        return None


def main():
    print("\n" + "#" * 60)
    print("           CYBERCASE INGEST VERIFICATION")
    print("#" * 60)

    parser_ok = verify_parser()
    neo4j_ok = verify_neo4j()
    qdrant_ok = verify_qdrant()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Parser Verification:        {'PASS' if parser_ok else 'FAIL'}")
    print(f"Neo4j Database:            {'PASS' if neo4j_ok is True else 'FAIL' if neo4j_ok is False else 'SKIPPED'}")
    print(f"Qdrant Vector DB:          {'PASS' if qdrant_ok is True else 'FAIL' if qdrant_ok is False else 'SKIPPED'}")
    print("=" * 60)

    if parser_ok and neo4j_ok is not False and qdrant_ok is not False:
        print("\nAll active checks PASSED!")
        sys.exit(0)
    else:
        print("\nSome verification checks FAILED!")
        sys.exit(1)


if __name__ == "__main__":
    main()
