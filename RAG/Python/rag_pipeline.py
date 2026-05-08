"""
Advanced Legal RAG -- LlamaIndex + FAISS + Hybrid Retrieval
===========================================================

Features
--------
✓ Semantic Chunking
✓ FAISS Vector Search
✓ BM25 Sparse Retrieval
✓ Hybrid Fusion Retrieval
✓ Metadata-aware Retrieval
✓ Local Embeddings (Sentence Transformers)
✓ Claude / Ollama / OpenAI compatible
✓ Thai Legal Document Optimized
✓ Ready for MITRE ATT&CK integration later

Usage
-----
python rag_pipeline.py --ingest
python rag_pipeline.py
python rag_pipeline.py --test
"""

# ──────────────────────────────────────────────────────────────────────────────
# UTF-8 FIX
# ──────────────────────────────────────────────────────────────────────────────
import sys
import io

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer,
        encoding="utf-8",
        errors="replace"
    )

# ──────────────────────────────────────────────────────────────────────────────
# IMPORTS
# ──────────────────────────────────────────────────────────────────────────────
import os
import argparse
from pathlib import Path
import faiss

from llama_index.core import (
    VectorStoreIndex,
    StorageContext,
    Settings,
)

from llama_index.core.schema import Document
from llama_index.core.node_parser import SemanticSplitterNodeParser
from llama_index.core.retrievers import QueryFusionRetriever
from llama_index.core.response_synthesizers import get_response_synthesizer
from llama_index.core.query_engine import RetrieverQueryEngine

from llama_index.readers.file import PyMuPDFReader

from llama_index.vector_stores.faiss import FaissVectorStore

from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core.postprocessor import SentenceTransformerRerank
# Claude
from llama_index.llms.anthropic import Anthropic
import re
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.core.retrievers import BaseRetriever
from llama_index.core.schema import NodeWithScore, QueryBundle
RERANKER = None
# Optional reranker
# from llama_index.postprocessor.flag_embedding_reranker import (
#     FlagEmbeddingReranker
# )

# ──────────────────────────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent

DOCS_DIR = _PROJECT_ROOT / "Documents"

INDEX_DIR = _SCRIPT_DIR.parent / "storage"
FAISS_DIR = INDEX_DIR / "faiss"

EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

TOP_K = 5

# embedding dimension
EMBED_DIM = 384

# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────
def sep(title=""):

    width = 72

    if title:
        pad = (width - len(title) - 2) // 2
        print("\n" + "-" * pad + f" {title} " + "-" * pad)

    else:
        print("\n" + "-" * width)


# ──────────────────────────────────────────────────────────────────────────────
# EMBEDDINGS
# ──────────────────────────────────────────────────────────────────────────────
def split_by_articles(text):
    return re.split(r"(มาตรา\s+\d+)", text)


def setup_models():
    global RERANKER

    print(f"[EMBED] Loading {EMBED_MODEL}")

    embed_model = HuggingFaceEmbedding(
        model_name=EMBED_MODEL,
        device="cpu",
    )

    Settings.embed_model = embed_model
    RERANKER = SentenceTransformerRerank(
        model="cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
        top_n=TOP_K
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


# ──────────────────────────────────────────────────────────────────────────────
# LOAD PDFS
# ──────────────────────────────────────────────────────────────────────────────
def load_documents():

    pdf_files = sorted(DOCS_DIR.glob("*.pdf"))

    if not pdf_files:
        raise FileNotFoundError(
            f"No PDFs found in {DOCS_DIR}"
        )

    reader = PyMuPDFReader()

    documents = []

    print(f"[LOAD] Found {len(pdf_files)} PDFs")

    for pdf in pdf_files:

        print(f"       Loading: {pdf.name}")

        docs = reader.load_data(
            file_path=str(pdf)
        )

        # inject metadata
        for i, d in enumerate(docs):  # ← เปลี่ยน for d in docs เป็น enumerate

            d.metadata["source"] = pdf.name
            d.metadata["doc_type"] = "law"
            d.metadata["page_label"] = str(d.metadata.get("page_label", i + 1))  # ← เพิ่ม

        documents.extend(docs)

        print(f"       => {len(docs)} pages")

    print(f"\n[LOAD] Total Pages: {len(documents)}")

    return documents


# ──────────────────────────────────────────────────────────────────────────────
# SEMANTIC CHUNKING
# ──────────────────────────────────────────────────────────────────────────────

def build_nodes(documents):

    print("[CHUNK] Article-aware + Semantic chunking...")

    processed_docs = []

    for doc in documents:

        parts = split_by_articles(doc.text)

        for i in range(0, len(parts), 2):

            chunk_text = parts[i]

            if i + 1 < len(parts):
                chunk_text += parts[i + 1]

            if not chunk_text.strip():  # ← skip empty chunks
                continue

            # ✅ copy metadata ทั้งหมดจาก original doc
            preserved_metadata = doc.metadata.copy()

            processed_docs.append(
                Document(
                    text=chunk_text,
                    metadata=preserved_metadata
                )
            )

    # semantic chunk หลัง split มาตรา
    parser = SemanticSplitterNodeParser(
        buffer_size=1,
        breakpoint_percentile_threshold=85,
        embed_model=Settings.embed_model,
    )

    nodes = parser.get_nodes_from_documents(processed_docs)

    print(f"[CHUNK] Created {len(nodes)} nodes")

    return nodes


# ──────────────────────────────────────────────────────────────────────────────
# BUILD INDEX
# ──────────────────────────────────────────────────────────────────────────────
def build_index(nodes):

    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    # FAISS
    print("[FAISS] Building vector store...")

    faiss_index = faiss.IndexFlatL2(
        EMBED_DIM
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
        persist_dir=str(INDEX_DIR)
    )

    print(f"[FAISS] Saved to {INDEX_DIR}")

    return index


# ──────────────────────────────────────────────────────────────────────────────
# LOAD INDEX
# ──────────────────────────────────────────────────────────────────────────────
def load_index():

    from llama_index.core import load_index_from_storage

    print(f"[FAISS] Loading from {INDEX_DIR}")

    vector_store = FaissVectorStore.from_persist_dir(
        str(INDEX_DIR)
    )

    storage_context = StorageContext.from_defaults(
        vector_store=vector_store,
        persist_dir=str(INDEX_DIR)
    )

    index = load_index_from_storage(
        storage_context
    )

    return index


# ──────────────────────────────────────────────────────────────────────────────
# HYBRID RETRIEVAL
# ──────────────────────────────────────────────────────────────────────────────
class SourceFilterRetriever(BaseRetriever):

    def __init__(self, retriever, source_filter=None):
        self._retriever = retriever
        self._source_filter = source_filter
        super().__init__()

    def _retrieve(self, query_bundle: QueryBundle):
        # ✅ เรียก sync ตรงๆ แทน
        nodes = self._retriever._retrieve(query_bundle)

        if not self._source_filter:
            return nodes

        filtered = [
            n for n in nodes
            if n.metadata.get("source") == self._source_filter
        ]

        return filtered if filtered else nodes
def detect_relevant_source(query: str) -> str | None:
    """
    ตรวจ keyword ใน query → return ชื่อ source PDF
    ถ้าไม่รู้ → return None (ค้นทุกไฟล์)
    """
    q = query.lower()

    keyword_map = {
        "คอมพิวเตอร์": "พระราชบัญญัติว่าด้วยการกระทำความผิดเกี่ยวกับคอมพิวเตอร์ พ.ศ. ๒๕๕๐.pdf",
        "computer":    "พระราชบัญญัติว่าด้วยการกระทำความผิดเกี่ยวกับคอมพิวเตอร์ พ.ศ. ๒๕๕๐.pdf",
        "pdpa":        "พระราชบัญญัติคุ้มครองข้อมูลส่วนบุคคล.pdf",
        "ข้อมูลส่วนบุคคล": "พระราชบัญญัติคุ้มครองข้อมูลส่วนบุคคล.pdf",
        "ธุรกรรม":     "พระราชบัญญัติว่าด้วยธุรกรรมทางอิเล็กทรอนิกส์ พ.ศ. 2544.pdf",
        "อิเล็กทรอนิกส์": "พระราชบัญญัติว่าด้วยธุรกรรมทางอิเล็กทรอนิกส์ พ.ศ. 2544.pdf",
        "อาญา":        "ประมวลกฎหมายอาญา.pdf",
        "criminal":    "ประมวลกฎหมายอาญา.pdf",
    }

    for keyword, source in keyword_map.items():
        if keyword in q:
            return source

    return None  # ไม่รู้ → ค้นทั้งหมด

def build_retriever(index, query: str = ""):

    print("[RETRIEVER] Building hybrid retriever")

    source_filter = detect_relevant_source(query)

    if source_filter:
        print(f"[FILTER] source = {source_filter}")
    else:
        print("[FILTER] No filter — searching all documents")

    # ✅ ไม่ใส่ filters ใน FAISS retriever แล้ว
    vector_retriever = index.as_retriever(
        similarity_top_k=TOP_K
    )

    bm25_retriever = BM25Retriever.from_defaults(
        docstore=index.docstore,
        similarity_top_k=TOP_K,
    )

    fusion_retriever = QueryFusionRetriever(
        [vector_retriever, bm25_retriever],
        similarity_top_k=TOP_K,
        num_queries=3,
        mode="reciprocal_rerank",
        use_async=True,
        verbose=True,
    )

    # ✅ wrap ด้วย SourceFilterRetriever
    retriever = SourceFilterRetriever(
        retriever=fusion_retriever,
        source_filter=source_filter
    )

    return retriever


# ──────────────────────────────────────────────────────────────────────────────
# QUERY ENGINE
# ──────────────────────────────────────────────────────────────────────────────


def build_query_engine(retriever):
    response_synthesizer = get_response_synthesizer()
    query_engine = RetrieverQueryEngine(
        retriever=retriever,
        node_postprocessors=[RERANKER],  # ← ใช้ global แทน ✅
        response_synthesizer=response_synthesizer,
    )
    return query_engine


# ──────────────────────────────────────────────────────────────────────────────
# QUERY
# ──────────────────────────────────────────────────────────────────────────────
def rag_query(index, query):  # ✅ รับ index แทน query_engine

    # build retriever + query_engine ใหม่ทุก query
    retriever = build_retriever(index, query)
    query_engine = build_query_engine(retriever)

    sep("QUERY")
    print(query)

    sep("ANSWER")
    response = query_engine.query(query)
    print(response)

    sep("SOURCES")
    for i, node in enumerate(response.source_nodes, 1):

        meta = node.metadata
        source = meta.get("source", "?")
        page = meta.get("page_label", "?")
        score = round(node.score, 4)
        text = node.text[:350].replace("\n", " ")

        print(f"[{i}] {source} | page={page} | score={score}")
        print(f"    {text}...\n")

    sep()


# ──────────────────────────────────────────────────────────────────────────────
# TESTS
# ──────────────────────────────────────────────────────────────────────────────
TEST_QUERIES = [

    "PDPA คืออะไร",

    "บทลงโทษของ พ.ร.บ.คอมพิวเตอร์ คืออะไร",

    "มาตรการด้าน Cybersecurity ของไทยมีอะไรบ้าง",

    "ธุรกรรมอิเล็กทรอนิกส์คืออะไร",

    "What penalties exist under Computer Crime Act?",
]


def run_tests(index):  # ✅ รับ index แทน query_engine

    sep("TEST SUITE")

    for i, q in enumerate(TEST_QUERIES, 1):

        print(f"\nTEST {i}/{len(TEST_QUERIES)}")

        rag_query(index, q)  # ✅ ส่ง index แทน query_engine


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────
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
    if args.ingest or not INDEX_DIR.exists():

        sep("INGESTION")

        documents = load_documents()

        nodes = build_nodes(
            documents
        )

        index = build_index(
            nodes
        )

    else:

        index = load_index()

    # ✅ ลบ build_retriever() และ build_query_engine() ออกจากตรงนี้
    # เพราะต้อง build ใหม่ทุก query เพื่อใส่ filter ตาม query นั้น

    # tests
    if args.test:

        run_tests(index)  # ✅ ส่ง index แทน query_engine

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

        if query.lower() in [
            "exit",
            "quit",
            "q"
        ]:

            print("Bye!")
            break

        if not query:
            continue

        rag_query(index, query)  # ✅ ส่ง index แทน query_engine


if __name__ == "__main__":
    main()