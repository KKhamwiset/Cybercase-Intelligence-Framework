"""
RAG Pipeline -- FAISS + LangChain + Sentence-Transformers
==========================================================
Documents   : Thai law PDFs in d:/Doc/TSR_Mitre/
Embeddings  : sentence-transformers (all-MiniLM-L6-v2) -- local, no API key
Vector store: FAISS (persisted to faiss_index/)
LLM         : Anthropic Claude claude-3-haiku  (needs ANTHROPIC_API_KEY)
              Falls back to retrieval-only if key is not set.

Usage:
    python rag_pipeline.py                # interactive query loop
    python rag_pipeline.py --ingest       # (re-)build FAISS index from PDFs
    python rag_pipeline.py --test         # run built-in test queries
"""

# ── Force UTF-8 output so Thai + box-drawing chars render on Windows ──────
import sys, io
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import os
import argparse
import textwrap
from pathlib import Path

# ── LangChain ──────────────────────────────────────────────────────────────
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

# ── Optional Anthropic LLM ─────────────────────────────────────────────────
try:
    import anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False

# =============================================================================
# CONFIGURATION
# =============================================================================
DOCS_DIR      = Path(r"d:\Doc\TSR_Mitre")
INDEX_DIR     = DOCS_DIR / "faiss_index"
EMBED_MODEL   = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE    = 800
CHUNK_OVERLAP = 150
TOP_K         = 5

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


# =============================================================================
# INGESTION
# =============================================================================

def load_pdfs(docs_dir: Path) -> list[Document]:
    """Load all PDFs in docs_dir using PyMuPDF (handles Thai text well)."""
    pdf_files = sorted(docs_dir.glob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError(f"No PDF files found in {docs_dir}")

    all_docs: list[Document] = []
    print(f"[LOAD] Found {len(pdf_files)} PDF(s) in {docs_dir}")
    for pdf in pdf_files:
        print(f"       Loading: {pdf.name}")
        loader = PyMuPDFLoader(str(pdf))
        docs = loader.load()
        for d in docs:
            d.metadata["source"] = pdf.name
        all_docs.extend(docs)
        print(f"       => {len(docs)} page(s)")

    print(f"\n[LOAD] Total pages: {len(all_docs)}")
    return all_docs


def chunk_documents(docs: list[Document]) -> list[Document]:
    """Split pages into smaller chunks for dense retrieval."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ".", " ", ""],
    )
    chunks = splitter.split_documents(docs)
    print(f"[CHUNK] Split into {len(chunks)} chunks "
          f"(size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    return chunks


def build_embeddings() -> HuggingFaceEmbeddings:
    """Load sentence-transformer embedding model (CPU, local)."""
    print(f"[EMBED] Loading model: {EMBED_MODEL}")
    return HuggingFaceEmbeddings(
        model_name=EMBED_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def build_index(chunks: list[Document],
                embeddings: HuggingFaceEmbeddings) -> FAISS:
    """Create & persist FAISS vector store."""
    print(f"[INDEX] Building FAISS index for {len(chunks)} chunks ...")
    vectorstore = FAISS.from_documents(chunks, embeddings)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(INDEX_DIR))
    print(f"[INDEX] Saved to {INDEX_DIR}")
    return vectorstore


def load_index(embeddings: HuggingFaceEmbeddings) -> FAISS:
    """Load persisted FAISS index from disk."""
    if not INDEX_DIR.exists():
        raise FileNotFoundError(
            f"Index not found at {INDEX_DIR}. Run --ingest first."
        )
    print(f"[INDEX] Loading from {INDEX_DIR} ...")
    vs = FAISS.load_local(
        str(INDEX_DIR),
        embeddings,
        allow_dangerous_deserialization=True,
    )
    print("[INDEX] Loaded OK.")
    return vs


# =============================================================================
# RETRIEVAL
# =============================================================================

def retrieve(vectorstore: FAISS, query: str,
             k: int = TOP_K) -> list[tuple[Document, float]]:
    """Semantic similarity search -- returns (Document, L2-distance) pairs."""
    return vectorstore.similarity_search_with_score(query, k=k)


def format_retrieved(results: list[tuple[Document, float]]) -> str:
    lines = []
    for i, (doc, score) in enumerate(results, 1):
        src     = doc.metadata.get("source", "unknown")
        page    = doc.metadata.get("page", "?")
        snippet = doc.page_content[:350].replace("\n", " ")
        lines.append(
            f"  [{i}] {src}  (page {page})  dist={score:.4f}\n"
            f"      {snippet} ..."
        )
    return "\n\n".join(lines)


# =============================================================================
# GENERATION  (Anthropic Claude claude-3-haiku)
# =============================================================================

def generate_answer(query: str,
                    context_docs: list[tuple[Document, float]]) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not _ANTHROPIC_AVAILABLE or not api_key:
        return (
            "[INFO] No ANTHROPIC_API_KEY -- showing raw retrieved context:\n\n"
            + format_retrieved(context_docs)
        )

    client = anthropic.Anthropic(api_key=api_key)

    ctx_parts = []
    for i, (doc, _score) in enumerate(context_docs, 1):
        src  = doc.metadata.get("source", "?")
        page = doc.metadata.get("page", "?")
        ctx_parts.append(f"[Source {i}: {src}, page {page}]\n{doc.page_content}")
    context_str = "\n\n---\n\n".join(ctx_parts)

    system_prompt = textwrap.dedent("""
        You are a helpful legal assistant specialising in Thai law.
        Answer the user's question using ONLY the provided context.
        If the answer is not clearly in the context, say so explicitly.
        Cite the source document and page number for every key claim.
        Respond in the same language as the question.
    """).strip()

    try:
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1024,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": f"Context:\n{context_str}\n\nQuestion: {query}"
            }],
        )
        return response.content[0].text
    except Exception as exc:
        return (
            f"[LLM ERROR] {exc}\n\n"
            "Falling back to raw retrieved context:\n\n"
            + format_retrieved(context_docs)
        )


# =============================================================================
# END-TO-END RAG QUERY
# =============================================================================

def rag_query(vectorstore: FAISS, query: str) -> dict:
    _sep("QUERY")
    print(f"  {query}\n")

    retrieved = retrieve(vectorstore, query, k=TOP_K)

    _sep("RETRIEVED CHUNKS")
    print(format_retrieved(retrieved))

    _sep("GENERATED ANSWER")
    answer = generate_answer(query, retrieved)
    print(answer)

    _sep()
    return {"query": query, "retrieved": retrieved, "answer": answer}


# =============================================================================
# BUILT-IN TEST SUITE
# =============================================================================

TEST_QUERIES = [
    # Thai questions (matching the loaded PDFs)
    "PDPA คืออะไร และมีหลักการสำคัญอย่างไร",
    "บทลงโทษสำหรับการละเมิดความเป็นส่วนตัวของข้อมูลในกฎหมาย PDPA คืออะไร",
    "การกระทำความผิดเกี่ยวกับคอมพิวเตอร์มีโทษอย่างไร",
    "ธุรกรรมทางอิเล็กทรอนิกส์ตามกฎหมายไทยหมายความว่าอะไร",
    "มาตรการความมั่นคงปลอดภัยทางไซเบอร์ของประเทศไทยมีอะไรบ้าง",
    # English questions
    "What are the key provisions of the Thai Cybersecurity Act?",
    "What penalties exist under the Computer Crime Act?",
]


def run_tests(vectorstore: FAISS) -> None:
    print("\n" + "=" * 72)
    print("  RAG RETRIEVAL TEST SUITE")
    print("=" * 72)
    summary = []

    for i, q in enumerate(TEST_QUERIES, 1):
        print(f"\n{'='*72}")
        print(f"  TEST {i}/{len(TEST_QUERIES)}")
        r = rag_query(vectorstore, q)
        top_src   = (r["retrieved"][0][0].metadata.get("source", "?")
                     if r["retrieved"] else "-")
        top_score = r["retrieved"][0][1] if r["retrieved"] else 0.0
        summary.append({"query": q[:55], "src": top_src, "score": top_score})

    _sep("TEST SUMMARY")
    hdr = f"{'#':<4} {'Query':<57} {'Top Source':<48} {'Dist':>7}"
    print(hdr)
    print("-" * len(hdr))
    for i, row in enumerate(summary, 1):
        print(f"{i:<4} {row['query']:<57} {row['src']:<48} {row['score']:>7.4f}")
    print()


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="FAISS + LangChain RAG pipeline for Thai legal PDFs"
    )
    parser.add_argument("--ingest", action="store_true",
                        help="(Re-)build the FAISS index from PDFs")
    parser.add_argument("--test", action="store_true",
                        help="Run the built-in test query suite")
    args = parser.parse_args()

    embeddings = build_embeddings()

    # -- Ingest or load -------------------------------------------------------
    if args.ingest or not INDEX_DIR.exists():
        _sep("INGESTION")
        docs        = load_pdfs(DOCS_DIR)
        chunks      = chunk_documents(docs)
        vectorstore = build_index(chunks, embeddings)
    else:
        vectorstore = load_index(embeddings)

    # -- Test mode ------------------------------------------------------------
    if args.test:
        run_tests(vectorstore)
        return

    # -- Interactive loop -----------------------------------------------------
    print("\n" + "=" * 72)
    print("  RAG INTERACTIVE MODE  (type 'exit' to quit)")
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

        rag_query(vectorstore, query)


if __name__ == "__main__":
    main()
