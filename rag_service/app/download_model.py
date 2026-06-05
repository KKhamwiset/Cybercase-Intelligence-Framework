"""
Utility script to download and cache the embedding model during Docker build.
This ensures the model is baked into the image for faster startup and offline use.
"""

import os

from FlagEmbedding import BGEM3FlagModel
from sentence_transformers import CrossEncoder


def download_model():
    # 1. Embedding Model
    embed_model_name = "BAAI/bge-m3"
    print(f"[BUILD] Downloading and caching embedding model: {embed_model_name}")
    BGEM3FlagModel(embed_model_name, use_fp16=True)

    # 2. Reranker Model
    reranker_model_name = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
    print(f"[BUILD] Downloading and caching reranker model: {reranker_model_name}")
    CrossEncoder(reranker_model_name)

    print("[BUILD] All models downloaded and cached successfully.")


if __name__ == "__main__":
    download_model()
