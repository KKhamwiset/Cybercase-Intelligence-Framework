"""
Utility script to download and cache the embedding model during Docker build.
This ensures the model is baked into the image for faster startup and offline use.
"""

import os

from FlagEmbedding import BGEM3FlagModel


def download_model():
    model_name = "BAAI/bge-m3"
    print(f"[BUILD] Downloading and caching model: {model_name}")

    # We use CPU-only check if needed, but for build time standard init is fine.
    # The weights will be saved to the default Hugging Face cache directory:
    # ~/.cache/huggingface/hub/
    BGEM3FlagModel(model_name, use_fp16=True)

    print("[BUILD] Model downloaded and cached successfully.")


if __name__ == "__main__":
    download_model()
