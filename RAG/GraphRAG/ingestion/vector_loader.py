"""
ChromaDB Vector Loader
=======================
Embeds ATT&CK entity descriptions and relationship descriptions into ChromaDB.
Follows the schema_design.md embedding strategy:
  - Entities: "[Type]: [Name]. [Description]"
  - Relationships: "[Source] [REL_TYPE] [Target]: [Description]"

Uses multilingual-e5-large with "passage: " prefix for documents.
"""

import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer
from typing import Optional

from config import (
    CHROMA_DIR,
    EMBED_MODEL,
    E5_PASSAGE_PREFIX,
    CHROMA_COLLECTION_ENTITIES,
    CHROMA_COLLECTION_RELATIONSHIPS,
    sep,
)
from models import AttackEntity, AttackRelationship
from .stix_parser import StixParser


class VectorLoader:
    """Embeds and stores ATT&CK data in ChromaDB."""

    def __init__(self, embed_model: Optional[SentenceTransformer] = None):
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=ChromaSettings(anonymized_telemetry=False),
        )

        if embed_model is None:
            print(f"[EMBED] Loading {EMBED_MODEL}...")
            self.embed_model = SentenceTransformer(EMBED_MODEL)
        else:
            self.embed_model = embed_model

        print(f"[CHROMA] Persistent storage at {CHROMA_DIR}")

    def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts with E5 passage prefix."""
        prefixed = [f"{E5_PASSAGE_PREFIX}{t}" for t in texts]
        embeddings = self.embed_model.encode(prefixed, show_progress_bar=True, normalize_embeddings=True)
        return embeddings.tolist()

    # ──────────────────────────────────────────────────────────────────────
    # ENTITY EMBEDDING
    # ──────────────────────────────────────────────────────────────────────
    def load_entities(self, entities: list[AttackEntity]) -> int:
        """Embed and store entity descriptions. Returns count stored."""
        sep("Embedding Entities into ChromaDB")

        # Get or create collection (delete first for fresh ingestion)
        try:
            self.client.delete_collection(CHROMA_COLLECTION_ENTITIES)
        except Exception:
            pass

        collection = self.client.get_or_create_collection(
            name=CHROMA_COLLECTION_ENTITIES,
            metadata={"hnsw:space": "cosine"},
        )

        # Prepare documents
        ids = []
        documents = []
        metadatas = []

        for entity in entities:
            if not entity.description:
                continue

            # Format: "[Type]: [Name]. [Description]"
            text = f"{entity.node_label}: {entity.name}. {entity.description}"

            # Truncate very long descriptions (ChromaDB has limits)
            text = text[:8000]

            ids.append(entity.stix_id)
            documents.append(text)
            metadatas.append({
                "stix_id": entity.stix_id,
                "attack_id": entity.attack_id,
                "entity_type": "Node",
                "node_label": entity.node_label,
                "name": entity.name,
                "domain": entity.domain,
                "url": entity.url,
            })

        if not documents:
            print("[CHROMA] No entities to embed")
            return 0

        # Batch embed and insert
        print(f"[CHROMA] Embedding {len(documents)} entity documents...")

        BATCH_SIZE = 64
        for i in range(0, len(documents), BATCH_SIZE):
            batch_ids = ids[i:i + BATCH_SIZE]
            batch_docs = documents[i:i + BATCH_SIZE]
            batch_meta = metadatas[i:i + BATCH_SIZE]
            batch_embeddings = self._embed_texts(batch_docs)

            collection.add(
                ids=batch_ids,
                documents=batch_docs,
                embeddings=batch_embeddings,
                metadatas=batch_meta,
            )

            if (i + BATCH_SIZE) % 256 == 0 or (i + BATCH_SIZE) >= len(documents):
                print(f"        Embedded {min(i + BATCH_SIZE, len(documents))}/{len(documents)} entities")

        print(f"[CHROMA] Stored {len(documents)} entity embeddings")
        return len(documents)

    # ──────────────────────────────────────────────────────────────────────
    # RELATIONSHIP EMBEDDING
    # ──────────────────────────────────────────────────────────────────────
    def load_relationships(self, relationships: list[AttackRelationship]) -> int:
        """Embed and store relationship descriptions. Returns count stored."""
        sep("Embedding Relationships into ChromaDB")

        try:
            self.client.delete_collection(CHROMA_COLLECTION_RELATIONSHIPS)
        except Exception:
            pass

        collection = self.client.get_or_create_collection(
            name=CHROMA_COLLECTION_RELATIONSHIPS,
            metadata={"hnsw:space": "cosine"},
        )

        ids = []
        documents = []
        metadatas = []

        for rel in relationships:
            if not rel.description:
                continue  # Skip relationships without descriptions (IN_TACTIC, HAS_COMPONENT)

            # Format: "[Source Name] [EDGE_LABEL] [Target Name]: [Description]"
            text = (
                f"{rel.source_name} {rel.edge_label} {rel.target_name}: "
                f"{rel.description}"
            )
            text = text[:8000]

            ids.append(rel.stix_id)
            documents.append(text)
            metadatas.append({
                "stix_id": rel.stix_id,
                "entity_type": "Relationship",
                "edge_label": rel.edge_label,
                "source_id": rel.source_ref,
                "target_id": rel.target_ref,
                "source_name": rel.source_name,
                "target_name": rel.target_name,
            })

        if not documents:
            print("[CHROMA] No relationships to embed")
            return 0

        print(f"[CHROMA] Embedding {len(documents)} relationship documents...")

        BATCH_SIZE = 64
        for i in range(0, len(documents), BATCH_SIZE):
            batch_ids = ids[i:i + BATCH_SIZE]
            batch_docs = documents[i:i + BATCH_SIZE]
            batch_meta = metadatas[i:i + BATCH_SIZE]
            batch_embeddings = self._embed_texts(batch_docs)

            collection.add(
                ids=batch_ids,
                documents=batch_docs,
                embeddings=batch_embeddings,
                metadatas=batch_meta,
            )

            if (i + BATCH_SIZE) % 256 == 0 or (i + BATCH_SIZE) >= len(documents):
                print(f"        Embedded {min(i + BATCH_SIZE, len(documents))}/{len(documents)} relationships")

        print(f"[CHROMA] Stored {len(documents)} relationship embeddings")
        return len(documents)

    # ──────────────────────────────────────────────────────────────────────
    # FULL LOAD
    # ──────────────────────────────────────────────────────────────────────
    def load_all(self, parser: StixParser) -> None:
        """Full vector ingestion: embed entities + relationships."""
        entity_count = self.load_entities(parser.entities)
        rel_count = self.load_relationships(parser.relationships)
        print(f"\n[CHROMA] Total: {entity_count} entity + {rel_count} relationship embeddings")
