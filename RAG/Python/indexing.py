import faiss

from llama_index.core import (
    VectorStoreIndex,
    StorageContext,
)
from llama_index.vector_stores.faiss import FaissVectorStore

import config

def build_index(nodes):
    config.INDEX_DIR.mkdir(parents=True, exist_ok=True)

    print("[FAISS] Building vector store...")

    faiss_index = faiss.IndexFlatL2(
        config.EMBED_DIM
    )

    vector_store = FaissVectorStore(
        faiss_index=faiss_index
    )

    storage_context = StorageContext.from_defaults(
        vector_store=vector_store
    )

    index = VectorStoreIndex(
        nodes,
        storage_context=storage_context,
        show_progress=True,
    )

    index.storage_context.persist(
        persist_dir=str(config.INDEX_DIR)
    )

    print(f"[FAISS] Saved to {config.INDEX_DIR}")

    return index

def load_index():
    from llama_index.core import load_index_from_storage

    print(f"[FAISS] Loading from {config.INDEX_DIR}")

    vector_store = FaissVectorStore.from_persist_dir(
        str(config.INDEX_DIR)
    )

    storage_context = StorageContext.from_defaults(
        vector_store=vector_store,
        persist_dir=str(config.INDEX_DIR)
    )

    index = load_index_from_storage(
        storage_context
    )

    return index
