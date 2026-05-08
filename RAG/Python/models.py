import os
from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core.postprocessor import SentenceTransformerRerank
from llama_index.llms.anthropic import Anthropic

import config

def setup_models():
    print(f"[EMBED] Loading {config.EMBED_MODEL}")

    embed_model = HuggingFaceEmbedding(
        model_name=config.EMBED_MODEL,
        device="cpu",
    )

    Settings.embed_model = embed_model
    config.RERANKER = SentenceTransformerRerank(
        model="cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
        top_n=config.TOP_K
    )

    # Claude
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if api_key:
        print("[LLM] Claude enabled")
        Settings.llm = Anthropic(
            model="claude-sonnet-4-20250514",
            api_key=api_key,
            temperature=0,
            max_tokens=4096,
        )
    else:
        print("[WARN] No ANTHROPIC_API_KEY")
        Settings.llm = None

    return embed_model
