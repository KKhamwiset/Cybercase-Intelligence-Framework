"""
Qdrant Vector Loader
=======================
Embeds ATT&CK entity descriptions and relationship descriptions into Qdrant.
Uses BGE-M3 for hybrid retrieval (Dense + Sparse).
Follows the schema_design.md embedding strategy:
  - Entities: "[Type]: [Name]. [Description]"
  - Relationships: "[Source] [REL_TYPE] [Target]: [Description]"
"""

import uuid
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, SparseVector, VectorParams, SparseVectorParams
from FlagEmbedding import BGEM3FlagModel

from ..config import (
    QDRANT_COLLECTION_ENTITIES,
    QDRANT_COLLECTION_RELATIONSHIPS,
    QDRANT_HOST,
    QDRANT_PORT,
    QDRANT_API_KEY,
    QDRANT_URL,
    EMBED_MODEL,
    EMBED_DIM,
    USE_FP16,
    sep,
)
from ..models import AttackEntity, AttackRelationship
from .stix_parser import StixParser


def uuid_from_stix_id(stix_id: str) -> str:
    """Generate a valid UUID from a STIX ID."""
    import hashlib
    import uuid as uuid_lib
    
    if "--" in stix_id:
        parts = stix_id.split("--", 1)
        if len(parts) == 2:
            try:
                # Validate if it's already a UUID
                return str(uuid_lib.UUID(parts[1]))
            except ValueError:
                pass
                
    # Fallback to hashing the string into a UUID
    hash_obj = hashlib.md5(stix_id.encode("utf-8"))
    return str(uuid_lib.UUID(hash_obj.hexdigest()))


class VectorLoader:
    """Embeds and stores ATT&CK data in Qdrant (Hybrid)."""

    def __init__(self, embed_model: Optional[BGEM3FlagModel] = None):
        if QDRANT_URL:
            print(f"[QDRANT] Connecting to cloud: {QDRANT_URL}")
            self.client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        elif QDRANT_HOST:
            print(f"[QDRANT] Connecting to {QDRANT_HOST}:{QDRANT_PORT}")
            self.client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, api_key=QDRANT_API_KEY)
        else:
            print(f"[QDRANT] Using in-memory storage (dev only)")
            self.client = QdrantClient(":memory:")

        if embed_model is None:
            print(f"[EMBED] Loading {EMBED_MODEL} (FP16: {USE_FP16})...")
            self.embed_model = BGEM3FlagModel(EMBED_MODEL, use_fp16=USE_FP16)
        else:
            self.embed_model = embed_model

    def _embed_texts(self, texts: list[str]) -> dict:
        """Embed a batch of texts returning dense and sparse vectors."""
        output = self.embed_model.encode(
            texts, return_dense=True, return_sparse=True, return_colbert_vecs=False
        )
        return {
            "dense": output["dense_vecs"].tolist(),
            "sparse": output["lexical_weights"],
        }

    def _init_collection(self, collection_name: str):
        """Create Qdrant collection with both dense and sparse configurations."""
        if self.client.collection_exists(collection_name):
            self.client.delete_collection(collection_name)
            
        self.client.create_collection(
            collection_name=collection_name,
            vectors_config={
                "dense": VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
            },
            sparse_vectors_config={
                "sparse": SparseVectorParams(),
            }
        )

    # ──────────────────────────────────────────────────────────────────────
    # ENTITY EMBEDDING
    # ──────────────────────────────────────────────────────────────────────
    def load_entities(self, entities: list[AttackEntity]) -> int:
        """Embed and store entity descriptions. Returns count stored."""
        sep("Embedding Entities into Qdrant (Hybrid)")

        self._init_collection(QDRANT_COLLECTION_ENTITIES)

        # Prepare documents
        ids = []
        documents = []
        metadatas = []

        for entity in entities:
            if not entity.description:
                continue

            # Format: "[Type]: [Name]. [Description]"
            text = f"{entity.node_label}: {entity.name}. {entity.description}"

            # Truncate very long descriptions
            text = text[:8000]

            ids.append(entity.stix_id)
            documents.append(text)
            metadatas.append(
                {
                    "stix_id": entity.stix_id,
                    "attack_id": entity.attack_id,
                    "entity_type": "Node",
                    "node_label": entity.node_label,
                    "name": entity.name,
                    "domain": entity.domain,
                    "url": entity.url,
                    "document": text,
                }
            )

        if not documents:
            print("[QDRANT] No entities to embed")
            return 0

        # Batch embed and insert
        print(f"[QDRANT] Embedding {len(documents)} entity documents...")

        BATCH_SIZE = 16  # Smaller batch size for BGE-M3
        for i in range(0, len(documents), BATCH_SIZE):
            batch_ids = ids[i : i + BATCH_SIZE]
            batch_docs = documents[i : i + BATCH_SIZE]
            batch_meta = metadatas[i : i + BATCH_SIZE]
            
            embeddings = self._embed_texts(batch_docs)
            
            points = []
            for j in range(len(batch_ids)):
                dense_vec = embeddings["dense"][j]
                sparse_dict = embeddings["sparse"][j]
                
                sparse_indices = [int(k) for k in sparse_dict.keys()]
                sparse_values = list(sparse_dict.values())
                
                points.append(PointStruct(
                    id=uuid_from_stix_id(batch_ids[j]),
                    vector={
                        "dense": dense_vec,
                        "sparse": SparseVector(indices=sparse_indices, values=sparse_values),
                    },
                    payload=batch_meta[j],
                ))

            self.client.upsert(
                collection_name=QDRANT_COLLECTION_ENTITIES,
                points=points
            )

            if (i + BATCH_SIZE) % 128 == 0 or (i + BATCH_SIZE) >= len(documents):
                print(
                    f"        Embedded {min(i + BATCH_SIZE, len(documents))}/{len(documents)} entities"
                )

        print(f"[QDRANT] Stored {len(documents)} entity embeddings")
        return len(documents)

    # ──────────────────────────────────────────────────────────────────────
    # RELATIONSHIP EMBEDDING
    # ──────────────────────────────────────────────────────────────────────
    def load_relationships(self, relationships: list[AttackRelationship]) -> int:
        """Embed and store relationship descriptions. Returns count stored."""
        sep("Embedding Relationships into Qdrant (Hybrid)")

        self._init_collection(QDRANT_COLLECTION_RELATIONSHIPS)

        ids = []
        documents = []
        metadatas = []

        for rel in relationships:
            if not rel.description:
                continue

            # Format: "[Source Name] [EDGE_LABEL] [Target Name]: [Description]"
            text = (
                f"{rel.source_name} {rel.edge_label} {rel.target_name}: "
                f"{rel.description}"
            )
            text = text[:8000]

            ids.append(rel.stix_id)
            documents.append(text)
            metadatas.append(
                {
                    "stix_id": rel.stix_id,
                    "entity_type": "Relationship",
                    "edge_label": rel.edge_label,
                    "source_id": rel.source_ref,
                    "target_id": rel.target_ref,
                    "source_name": rel.source_name,
                    "target_name": rel.target_name,
                    "document": text,
                }
            )

        if not documents:
            print("[QDRANT] No relationships to embed")
            return 0

        print(f"[QDRANT] Embedding {len(documents)} relationship documents...")

        BATCH_SIZE = 16
        for i in range(0, len(documents), BATCH_SIZE):
            batch_ids = ids[i : i + BATCH_SIZE]
            batch_docs = documents[i : i + BATCH_SIZE]
            batch_meta = metadatas[i : i + BATCH_SIZE]
            
            embeddings = self._embed_texts(batch_docs)

            points = []
            for j in range(len(batch_ids)):
                dense_vec = embeddings["dense"][j]
                sparse_dict = embeddings["sparse"][j]
                
                sparse_indices = [int(k) for k in sparse_dict.keys()]
                sparse_values = list(sparse_dict.values())
                
                points.append(PointStruct(
                    id=uuid_from_stix_id(batch_ids[j]),
                    vector={
                        "dense": dense_vec,
                        "sparse": SparseVector(indices=sparse_indices, values=sparse_values),
                    },
                    payload=batch_meta[j],
                ))

            self.client.upsert(
                collection_name=QDRANT_COLLECTION_RELATIONSHIPS,
                points=points
            )

            if (i + BATCH_SIZE) % 128 == 0 or (i + BATCH_SIZE) >= len(documents):
                print(
                    f"        Embedded {min(i + BATCH_SIZE, len(documents))}/{len(documents)} relationships"
                )

        print(f"[QDRANT] Stored {len(documents)} relationship embeddings")
        return len(documents)

    # ──────────────────────────────────────────────────────────────────────
    # FULL LOAD
    # ──────────────────────────────────────────────────────────────────────
    def load_all(self, parser: StixParser) -> None:
        """Full vector ingestion: embed entities + relationships."""
        entity_count = self.load_entities(parser.entities)
        rel_count = self.load_relationships(parser.relationships)
        print(
            f"\n[QDRANT] Total: {entity_count} entity + {rel_count} relationship embeddings"
        )
