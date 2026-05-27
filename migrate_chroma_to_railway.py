"""
DEPRECATED: ChromaDB to Railway Migration Script
==============================================
Note: The system has been migrated to Qdrant for BGE-M3 hybrid retrieval. 
This script is kept for historical reference but is no longer actively maintained. 
Old ChromaDB data cannot be migrated directly to Qdrant — a full re-embed via 
`python main.py --ingest` is required.

Script for migrating a local ChromaDB instance to a remote Railway-hosted instance.
Uses ChromaDB's HTTP client for remote connections and PersistentClient for local.
"""

import os
import sys
from urllib.parse import urlparse

import chromadb
from chromadb.config import Settings
from dotenv import load_dotenv

# Load environment variables from the file we created earlier
load_dotenv("backend.env")

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────

# Path to the local ChromaDB files
# The script is in the root, and data is in backend/RAG/GraphRAG/chroma_db
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_CHROMA_PATH = os.path.join(BASE_DIR, "backend", "RAG", "GraphRAG", "chroma_db")

# Railway Configuration
RAILWAY_CHROMA_URL = os.getenv("RAILWAY_CHROMA_URL")
RAILWAY_CHROMA_API_KEY = os.getenv("RAILWAY_CHROMA_API_KEY")


def get_remote_client(url, api_key=None):
    """Parses URL and returns a Chroma HttpClient."""
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port

    # Default ports if not specified
    if not port:
        port = 443 if parsed.scheme == "https" else 8000

    print(f"📡 Connecting to: {host}:{port} (SSL: {parsed.scheme == 'https'})")

    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    return chromadb.HttpClient(
        host=host,
        port=str(port),
        ssl=(parsed.scheme == "https"),
        headers=headers if headers else None,
    )


def migrate():
    print("🚀 Starting ChromaDB Migration to Railway...")

    # 1. Validate Local Path
    if not os.path.exists(os.path.join(LOCAL_CHROMA_PATH, "chroma.sqlite3")):
        print(f"❌ Error: Local database not found at {LOCAL_CHROMA_PATH}")
        print("Please check the path in the script.")
        return

    # 2. Validate Remote URL
    if not RAILWAY_CHROMA_URL or "your-chroma-project" in RAILWAY_CHROMA_URL:
        print("❌ Error: RAILWAY_CHROMA_URL is not configured in backend.env")
        return

    try:
        # 3. Initialize Clients
        print(f"📂 Loading local database from: {LOCAL_CHROMA_PATH}")
        local_client = chromadb.PersistentClient(path=LOCAL_CHROMA_PATH)

        remote_client = get_remote_client(RAILWAY_CHROMA_URL, RAILWAY_CHROMA_API_KEY)

        # Test remote connection
        version = remote_client.get_version()
        print(f"✅ Connected! Remote Chroma version: {version}")

        # 4. Get Collections
        collections = local_client.list_collections()
        if not collections:
            print("❓ No collections found in the local database.")
            return

        print(f"📋 Found {len(collections)} collections to migrate.")

        for coll_obj in collections:
            # Note: list_collections returns objects in newer versions, names in older
            coll_name = coll_obj.name if hasattr(coll_obj, "name") else coll_obj
            print(f"\n📦 Processing Collection: '{coll_name}'")

            local_coll = local_client.get_collection(name=coll_name)
            count = local_coll.count()
            print(f"  - Local items: {count}")

            if count == 0:
                print("  - Skipping empty collection.")
                continue

            # 5. Fetch Data
            print("  - Fetching data from local storage...")
            data = local_coll.get(include=["embeddings", "documents", "metadatas"])

            # 6. Prepare Remote Collection
            # We don't pass embedding_function because we are migrating raw embeddings
            remote_coll = remote_client.get_or_create_collection(name=coll_name)

            # 7. Upload in Batches
            batch_size = 500  # Smaller batches are safer for cloud environments
            ids = data["ids"]
            embeddings = data["embeddings"]
            documents = data["documents"]
            metadatas = data["metadatas"]

            total_batches = (count + batch_size - 1) // batch_size

            for i in range(0, count, batch_size):
                end = min(i + batch_size, count)
                current_batch = (i // batch_size) + 1

                print(
                    f"  - Uploading batch {current_batch}/{total_batches} ({i} to {end})...",
                    end="\r",
                )

                remote_coll.upsert(
                    ids=ids[i:end],
                    embeddings=embeddings[i:end] if embeddings is not None else None,
                    metadatas=metadatas[i:end] if metadatas is not None else None,
                    documents=documents[i:end] if documents is not None else None,
                )

            print(f"\n  ✅ Collection '{coll_name}' migrated successfully.")

        print("\n✨ All done! Migration complete.")

    except Exception as e:
        print(f"\n💥 Critical Error: {str(e)}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    migrate()
