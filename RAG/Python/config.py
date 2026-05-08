from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent

DOCS_DIR = _PROJECT_ROOT / "Documents"

INDEX_DIR = _SCRIPT_DIR.parent / "storage"
FAISS_DIR = INDEX_DIR / "faiss"

EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

TOP_K = 5
EMBED_DIM = 384

RERANKER = None

def sep(title=""):
    width = 72
    if title:
        pad = (width - len(title) - 2) // 2
        print("\n" + "-" * pad + f" {title} " + "-" * pad)
    else:
        print("\n" + "-" * width)
