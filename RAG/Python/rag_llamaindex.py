"""
RAG Pipeline -- LlamaIndex + FAISS + Sentence-Transformers
===========================================================
Documents   : Thai law PDFs in d:/Doc/TSR_Mitre/
Embeddings  : HuggingFaceEmbedding (all-MiniLM-L6-v2) -- fully local
Vector store: FAISS via llama-index-vector-stores-faiss
LLM         : Anthropic claude-haiku-4-5  (ANTHROPIC_API_KEY required)
              Falls back to no-LLM retrieval-only mode if key absent.

Usage:
    python rag_llamaindex.py                # interactive query loop
    python rag_llamaindex.py --ingest       # (re-)build index
    python rag_llamaindex.py --test         # built-in test queries
    python rag_llamaindex.py --compare      # side-by-side vs LangChain
"""

# Force UTF-8 on Windows cp874 terminal
import sys, io
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import os
import argparse
import time
from pathlib import Path

# -- LlamaIndex ---------------------------------------------------------------
from llama_index.core import (
    SimpleDirectoryReader,
    VectorStoreIndex,
    StorageContext,
    Settings,
    load_index_from_storage,
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.faiss import FaissVectorStore
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.response_synthesizers import get_response_synthesizer
import faiss

# -- Optional Anthropic LLM ---------------------------------------------------
try:
    import anthropic as _anthropic_sdk
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False

# =============================================================================
# CONFIGURATION
# =============================================================================
_SCRIPT_DIR   = Path(__file__).resolve().parent          # RAG/Python/
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent                # TSR_Mitre/
DOCS_DIR      = _PROJECT_ROOT / "Documents"
INDEX_DIR     = _SCRIPT_DIR.parent / "llamaindex_faiss"  # RAG/llamaindex_faiss/
EMBED_MODEL   = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_DIM     = 384          # all-MiniLM-L6-v2 output dimension
CHUNK_SIZE    = 800
CHUNK_OVERLAP = 150
TOP_K         = 5

TEST_QUERIES = [
    "PDPA คืออะไร และมีหลักการสำคัญอย่างไร",
    "บทลงโทษสำหรับการละเมิดความเป็นส่วนตัวของข้อมูลในกฎหมาย PDPA คืออะไร",
    "การกระทำความผิดเกี่ยวกับคอมพิวเตอร์มีโทษอย่างไร",
    "ธุรกรรมทางอิเล็กทรอนิกส์ตามกฎหมายไทยหมายความว่าอะไร",
    "มาตรการความมั่นคงปลอดภัยทางไซเบอร์ของประเทศไทยมีอะไรบ้าง",
    "What are the key provisions of the Thai Cybersecurity Act?",
    "What penalties exist under the Computer Crime Act?",
]

# =============================================================================
# HELPERS
# =============================================================================

def _sep(title: str = "") -> None:
    w = 72
    if title:
        pad = (w - len(title) - 2) // 2
        print("\n" + "-" * pad + f" {title} " + "-" * pad)
    else:
        print("\n" + "-" * w)


def _configure_settings(use_llm: bool = True) -> None:
    """Set global LlamaIndex Settings (replaces ServiceContext)."""
    print(f"[EMBED] Loading model: {EMBED_MODEL}")
    Settings.embed_model = HuggingFaceEmbedding(
        model_name=EMBED_MODEL,
        embed_batch_size=32,
    )
    Settings.chunk_size    = CHUNK_SIZE
    Settings.chunk_overlap = CHUNK_OVERLAP

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if use_llm and _ANTHROPIC_AVAILABLE and api_key:
        # Use a custom Anthropic LLM wrapper via llama-index-llms-anthropic if
        # available, otherwise fall back to MockLLM / retrieval-only.
        try:
            from llama_index.llms.anthropic import Anthropic
            Settings.llm = Anthropic(
                model="claude-haiku-4-5",
                api_key=api_key,
                max_tokens=1024,
            )
            print("[LLM]  Anthropic claude-haiku-4-5 configured.")
            return
        except ImportError:
            pass

    # No LLM -- retrieval-only (synthesiser will echo context)
    from llama_index.core.llms import MockLLM
    Settings.llm = MockLLM(max_tokens=256)
    print("[LLM]  No Anthropic LLM -- using retrieval-only mode.")


# =============================================================================
# INGESTION
# =============================================================================

def ingest() -> VectorStoreIndex:
    """Load PDFs, chunk, embed and persist a FAISS index via LlamaIndex."""
    pdf_files = sorted(DOCS_DIR.glob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError(f"No PDFs found in {DOCS_DIR}")

    print(f"[LOAD] Found {len(pdf_files)} PDF(s)")
    for p in pdf_files:
        print(f"       {p.name}")

    # SimpleDirectoryReader handles Thai PDFs via PyMuPDF automatically
    documents = SimpleDirectoryReader(
        input_files=[str(p) for p in pdf_files],
        filename_as_id=True,
    ).load_data()
    print(f"[LOAD] {len(documents)} page-documents loaded")

    # Chunk with SentenceSplitter
    parser = SentenceSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    nodes = parser.get_nodes_from_documents(documents, show_progress=False)
    print(f"[CHUNK] {len(nodes)} nodes created")

    # FAISS index (flat L2)
    faiss_index = faiss.IndexFlatL2(EMBED_DIM)
    vector_store = FaissVectorStore(faiss_index=faiss_index)
    storage_ctx  = StorageContext.from_defaults(vector_store=vector_store)

    print(f"[INDEX] Building FAISS index ({EMBED_DIM}-dim L2) ...")
    index = VectorStoreIndex(
        nodes,
        storage_context=storage_ctx,
        show_progress=False,
    )

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    index.storage_context.persist(persist_dir=str(INDEX_DIR))
    print(f"[INDEX] Saved to {INDEX_DIR}")
    return index


def load_index() -> VectorStoreIndex:
    """Load persisted LlamaIndex FAISS index."""
    if not INDEX_DIR.exists():
        raise FileNotFoundError(
            f"Index not found at {INDEX_DIR}. Run --ingest first."
        )
    print(f"[INDEX] Loading from {INDEX_DIR} ...")
    vector_store = FaissVectorStore.from_persist_dir(str(INDEX_DIR))
    storage_ctx  = StorageContext.from_defaults(
        vector_store=vector_store,
        persist_dir=str(INDEX_DIR),
    )
    index = load_index_from_storage(storage_ctx)
    print("[INDEX] Loaded OK.")
    return index


# =============================================================================
# RETRIEVAL + QUERY
# =============================================================================

def make_query_engine(index: VectorStoreIndex, top_k: int = TOP_K):
    retriever = VectorIndexRetriever(index=index, similarity_top_k=top_k)
    synth     = get_response_synthesizer(response_mode="compact")
    return RetrieverQueryEngine(retriever=retriever,
                                response_synthesizer=synth)


def retrieve_nodes(index: VectorStoreIndex, query: str, top_k: int = TOP_K):
    """Return raw retrieved nodes (no synthesis)."""
    retriever = VectorIndexRetriever(index=index, similarity_top_k=top_k)
    return retriever.retrieve(query)


def format_nodes(nodes) -> str:
    lines = []
    for i, n in enumerate(nodes, 1):
        src  = n.metadata.get("file_name", n.metadata.get("source", "?"))
        page = n.metadata.get("page_label", n.metadata.get("page", "?"))
        snippet = n.get_content()[:350].replace("\n", " ")
        lines.append(
            f"  [{i}] {src}  (page {page})  score={n.score:.4f}\n"
            f"      {snippet} ..."
        )
    return "\n\n".join(lines)


def rag_query(index: VectorStoreIndex, query: str) -> dict:
    """Retrieve + synthesise and pretty-print result."""
    _sep("QUERY")
    print(f"  {query}\n")

    t0    = time.perf_counter()
    nodes = retrieve_nodes(index, query)
    t_ret = time.perf_counter() - t0

    _sep("RETRIEVED NODES")
    print(format_nodes(nodes))

    # Try full query engine for synthesis
    _sep("SYNTHESISED ANSWER")
    try:
        engine   = make_query_engine(index)
        t1       = time.perf_counter()
        response = engine.query(query)
        t_gen    = time.perf_counter() - t1
        answer   = str(response)
        print(answer)
        print(f"\n  [timing] retrieval={t_ret:.2f}s  synthesis={t_gen:.2f}s")
    except Exception as exc:
        answer = f"[SYNTHESIS ERROR] {exc}"
        print(answer)

    _sep()
    return {"query": query, "nodes": nodes, "answer": answer}


# =============================================================================
# TEST SUITE
# =============================================================================

def run_tests(index: VectorStoreIndex) -> list[dict]:
    print("\n" + "=" * 72)
    print("  LLAMAINDEX RAG TEST SUITE")
    print("=" * 72)
    summary = []

    for i, q in enumerate(TEST_QUERIES, 1):
        print(f"\n{'='*72}")
        print(f"  TEST {i}/{len(TEST_QUERIES)}")
        r = rag_query(index, q)
        top = r["nodes"][0] if r["nodes"] else None
        summary.append({
            "query"  : q[:55],
            "src"    : (top.metadata.get("file_name", "?") if top else "-"),
            "score"  : (top.score if top else 0.0),
        })

    _sep("TEST SUMMARY")
    hdr = f"{'#':<4} {'Query':<57} {'Top Source':<42} {'Score':>7}"
    print(hdr)
    print("-" * len(hdr))
    for i, row in enumerate(summary, 1):
        print(f"{i:<4} {row['query']:<57} {row['src']:<42} {row['score']:>7.4f}")
    print()
    return summary


# =============================================================================
# SIDE-BY-SIDE COMPARISON WITH LANGCHAIN PIPELINE
# =============================================================================

def run_compare(lli_index: VectorStoreIndex) -> None:
    """Run same queries through both pipelines and compare top-1 source/score."""
    # Import LangChain pipeline
    try:
        from rag_pipeline import (
            build_embeddings as lc_embed,
            load_index as lc_load,
            retrieve as lc_retrieve,
        )
    except ImportError as e:
        print(f"[COMPARE] Cannot import rag_pipeline.py: {e}")
        return

    print("\n" + "=" * 100)
    print("  SIDE-BY-SIDE COMPARISON: LangChain vs LlamaIndex")
    print("=" * 100)

    lc_vs = lc_load(lc_embed())

    hdr = (f"{'#':<3} {'Query':<45} "
           f"{'LC Source':<36} {'LC Dist':>7}    "
           f"{'LLI Source':<36} {'LLI Score':>9}")
    print(hdr)
    print("-" * len(hdr))

    for i, q in enumerate(TEST_QUERIES, 1):
        # LangChain
        lc_res  = lc_retrieve(lc_vs, q, k=1)
        lc_src  = lc_res[0][0].metadata.get("source", "?") if lc_res else "-"
        lc_dist = lc_res[0][1] if lc_res else 0.0

        # LlamaIndex
        lli_nodes = retrieve_nodes(lli_index, q, top_k=1)
        lli_src   = (lli_nodes[0].metadata.get("file_name", "?")
                     if lli_nodes else "-")
        lli_score = lli_nodes[0].score if lli_nodes else 0.0

        q_short = q[:43]
        print(f"{i:<3} {q_short:<45} "
              f"{lc_src:<36} {lc_dist:>7.4f}    "
              f"{lli_src:<36} {lli_score:>9.4f}")

    print()


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="LlamaIndex + FAISS RAG pipeline for Thai legal PDFs"
    )
    parser.add_argument("--ingest",  action="store_true",
                        help="(Re-)build the FAISS index from PDFs")
    parser.add_argument("--test",    action="store_true",
                        help="Run the built-in test query suite")
    parser.add_argument("--compare", action="store_true",
                        help="Side-by-side vs LangChain pipeline")
    args = parser.parse_args()

    _configure_settings()

    if args.ingest or not INDEX_DIR.exists():
        _sep("INGESTION")
        index = ingest()
    else:
        index = load_index()

    if args.test and args.compare:
        run_tests(index)
        run_compare(index)
        return

    if args.test:
        run_tests(index)
        return

    if args.compare:
        run_compare(index)
        return

    # -- Interactive loop --------------------------------------------------
    print("\n" + "=" * 72)
    print("  LLAMAINDEX RAG INTERACTIVE MODE  (type 'exit' to quit)")
    print("=" * 72)
    print("  Indexed documents:")
    for pdf in sorted(DOCS_DIR.glob("*.pdf")):
        print(f"    * {pdf.name}")
    print()

    while True:
        try:
            query = input("Query> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye!")
            break
        if not query or query.lower() in ("exit", "quit", "q"):
            print("Bye!")
            break
        rag_query(index, query)


if __name__ == "__main__":
    main()
