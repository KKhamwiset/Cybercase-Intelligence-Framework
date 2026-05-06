"""
Advanced RAG Pipeline -- Hybrid (FAISS + BM25) + Cross-Encoder Reranking
========================================================================
Documents   : Thai law PDFs in d:/Doc/TSR_Mitre/
Embeddings  : intfloat/multilingual-e5-large (with query/passage prefixes)
Vector store: FAISS (Dense)
Keyword store: BM25 (Sparse)
Reranker    : BAAI/bge-reranker-m3 (Multilingual Cross-Encoder)
LLM         : Anthropic claude-haiku-4-5

Usage:
    python rag_advanced.py                # interactive query loop
    python rag_advanced.py --ingest       # (re-)build FAISS & BM25 indices
    python rag_advanced.py --test         # run built-in test queries
"""

import sys, io
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import os
import argparse
import textwrap
import pickle
from pathlib import Path

# -- LangChain ----------------------------------------------------------------
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.retrievers import BM25Retriever
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain_core.documents import Document
import torch

try:
    import anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False

# =============================================================================
# CONFIGURATION
# =============================================================================
DOCS_DIR      = Path(r"d:\Doc\TSR_Mitre")
INDEX_DIR     = DOCS_DIR / "advanced_index"
BM25_PATH     = INDEX_DIR / "bm25_retriever.pkl"
EMBED_MODEL   = "intfloat/multilingual-e5-large"
RERANK_MODEL  = "BAAI/bge-reranker-m3" # Excellent multilingual reranker
CHUNK_SIZE    = 800
CHUNK_OVERLAP = 150
RETRIEVE_K    = 10   # Fetch top 10 from each (FAISS / BM25)
RERANK_K      = 5    # Final top 5 after reranking

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

def load_and_chunk() -> list[Document]:
    pdf_files = sorted(DOCS_DIR.glob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError(f"No PDFs found in {DOCS_DIR}")

    all_docs = []
    print(f"[LOAD] Found {len(pdf_files)} PDF(s)")
    for pdf in pdf_files:
        loader = PyMuPDFLoader(str(pdf))
        docs = loader.load()
        for d in docs:
            d.metadata["source"] = pdf.name
        all_docs.extend(docs)
    
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ".", " ", ""],
    )
    chunks = splitter.split_documents(all_docs)
    print(f"[CHUNK] Split into {len(chunks)} chunks")
    
    # E5 models require "passage: " prefix for documents
    for chunk in chunks:
        chunk.page_content = f"passage: {chunk.page_content}"
        
    return chunks

def build_embeddings() -> HuggingFaceEmbeddings:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[EMBED] Loading embedding model: {EMBED_MODEL} on {device.upper()}")
    return HuggingFaceEmbeddings(
        model_name=EMBED_MODEL,
        model_kwargs={"device": device},
        encode_kwargs={"normalize_embeddings": True},
    )

def build_indices(chunks: list[Document], embeddings: HuggingFaceEmbeddings):
    print(f"[INDEX] Building FAISS index for {len(chunks)} chunks ...")
    faiss_vs = FAISS.from_documents(chunks, embeddings)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    faiss_vs.save_local(str(INDEX_DIR))
    
    print("[INDEX] Building BM25 index ...")
    bm25_retriever = BM25Retriever.from_documents(chunks)
    bm25_retriever.k = RETRIEVE_K
    with open(BM25_PATH, "wb") as f:
        pickle.dump(bm25_retriever, f)
        
    print(f"[INDEX] Saved FAISS & BM25 to {INDEX_DIR}")
    return faiss_vs, bm25_retriever

def load_indices(embeddings: HuggingFaceEmbeddings):
    if not INDEX_DIR.exists() or not BM25_PATH.exists():
        raise FileNotFoundError("Indices not found. Run --ingest first.")
    
    print(f"[INDEX] Loading from {INDEX_DIR} ...")
    faiss_vs = FAISS.load_local(str(INDEX_DIR), embeddings, allow_dangerous_deserialization=True)
    with open(BM25_PATH, "rb") as f:
        bm25_retriever = pickle.load(f)
    print("[INDEX] Loaded OK.")
    return faiss_vs, bm25_retriever

# =============================================================================
# RETRIEVAL (Hybrid + Reranking)
# =============================================================================

def build_retriever(faiss_vs: FAISS, bm25_retriever: BM25Retriever):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[RERANK] Loading reranker: {RERANK_MODEL} on {device.upper()}")
    cross_encoder = HuggingFaceCrossEncoder(model_name=RERANK_MODEL, model_kwargs={"device": device})
    
    return faiss_vs, bm25_retriever, cross_encoder

def retrieve_and_rerank(query: str, faiss_vs, bm25_retriever, cross_encoder) -> list[Document]:
    # E5 models require "query: " prefix for dense retrieval
    e5_query = f"query: {query}"
    
    faiss_docs = faiss_vs.similarity_search(e5_query, k=RETRIEVE_K)
    bm25_docs = bm25_retriever.invoke(query)  # BM25 uses raw query
    
    # Combine and deduplicate by content
    unique_docs = {}
    for d in faiss_docs + bm25_docs:
        unique_docs[d.page_content] = d
        
    docs = list(unique_docs.values())
    if not docs:
        return []
        
    # Rerank
    pairs = [[query, doc.page_content] for doc in docs]
    scores = cross_encoder.predict(pairs)
    
    # Sort by score descending
    scored_docs = list(zip(docs, scores))
    scored_docs.sort(key=lambda x: x[1], reverse=True)
    
    # Take top K and inject score into metadata
    top_docs = []
    for doc, score in scored_docs[:RERANK_K]:
        doc.metadata["rerank_score"] = float(score)
        top_docs.append(doc)
        
    return top_docs

def format_retrieved(docs: list[Document]) -> str:
    lines = []
    for i, doc in enumerate(docs, 1):
        src = doc.metadata.get("source", "unknown")
        page = doc.metadata.get("page", "?")
        score = doc.metadata.get("rerank_score", 0.0)
        # Remove the "passage: " prefix for display
        content = doc.page_content.replace("passage: ", "", 1)
        snippet = content[:350].replace("\n", " ")
        lines.append(f"  [{i}] {src} (page {page}) [score={score:.4f}]\n      {snippet} ...")
    return "\n\n".join(lines)

# =============================================================================
# GENERATION
# =============================================================================

def generate_answer(query: str, context_docs: list[Document]) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not _ANTHROPIC_AVAILABLE or not api_key:
        return "[INFO] No ANTHROPIC_API_KEY. Fallback to raw retrieval."

    client = anthropic.Anthropic(api_key=api_key)
    ctx_parts = []
    for i, doc in enumerate(context_docs, 1):
        src = doc.metadata.get("source", "?")
        page = doc.metadata.get("page", "?")
        content = doc.page_content.replace("passage: ", "", 1)
        ctx_parts.append(f"[Source {i}: {src}, page {page}]\n{content}")
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
            messages=[{"role": "user", "content": f"Context:\n{context_str}\n\nQuestion: {query}"}],
        )
        return response.content[0].text
    except Exception as exc:
        return f"[LLM ERROR] {exc}"

# =============================================================================
# RUN RAG
# =============================================================================

def rag_query(faiss_vs, bm25_retriever, cross_encoder, query: str) -> dict:
    _sep("QUERY")
    print(f"  {query}\n")

    docs = retrieve_and_rerank(query, faiss_vs, bm25_retriever, cross_encoder)
    
    _sep("RETRIEVED & RERANKED CHUNKS")
    print(format_retrieved(docs))

    _sep("GENERATED ANSWER")
    answer = generate_answer(query, docs)
    print(answer)
    _sep()
    
    return {"query": query, "docs": docs, "answer": answer}

TEST_QUERIES = [
    "PDPA คืออะไร และมีหลักการสำคัญอย่างไร",
    "บทลงโทษสำหรับการละเมิดความเป็นส่วนตัวของข้อมูลในกฎหมาย PDPA คืออะไร",
    "การกระทำความผิดเกี่ยวกับคอมพิวเตอร์มีโทษอย่างไร",
    "ธุรกรรมทางอิเล็กทรอนิกส์ตามกฎหมายไทยหมายความว่าอะไร",
    "มาตรการความมั่นคงปลอดภัยทางไซเบอร์ของประเทศไทยมีอะไรบ้าง",
    "What are the key provisions of the Thai Cybersecurity Act?",
    "What penalties exist under the Computer Crime Act?",
]

def run_tests(faiss_vs, bm25_retriever, cross_encoder) -> None:
    print("\n" + "=" * 72)
    print("  ADVANCED RAG RETRIEVAL TEST SUITE")
    print("=" * 72)
    
    summary = []
    for i, q in enumerate(TEST_QUERIES, 1):
        print(f"\n{'='*72}")
        print(f"  TEST {i}/{len(TEST_QUERIES)}")
        res = rag_query(faiss_vs, bm25_retriever, cross_encoder, q)
        top_src = res["docs"][0].metadata.get("source", "?") if res["docs"] else "-"
        summary.append({"query": q[:55], "src": top_src})
        
    _sep("TEST SUMMARY")
    hdr = f"{'#':<4} {'Query':<57} {'Top Source':<48}"
    print(hdr)
    print("-" * len(hdr))
    for i, row in enumerate(summary, 1):
        print(f"{i:<4} {row['query']:<57} {row['src']:<48}")
    print()

def main():
    parser = argparse.ArgumentParser(description="Advanced RAG Pipeline")
    parser.add_argument("--ingest", action="store_true", help="Build indices")
    parser.add_argument("--test", action="store_true", help="Run tests")
    args = parser.parse_args()

    embeddings = build_embeddings()

    if args.ingest or not INDEX_DIR.exists() or not BM25_PATH.exists():
        _sep("INGESTION")
        chunks = load_and_chunk()
        faiss_vs, bm25_retriever = build_indices(chunks, embeddings)
    else:
        faiss_vs, bm25_retriever = load_indices(embeddings)

    faiss_vs, bm25_retriever, cross_encoder = build_retriever(faiss_vs, bm25_retriever)

    if args.test:
        run_tests(faiss_vs, bm25_retriever, cross_encoder)
        return

    print("\n" + "=" * 72)
    print("  ADVANCED RAG INTERACTIVE MODE  (type 'exit' to quit)")
    print("=" * 72)
    while True:
        try:
            query = input("Query> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye!")
            break
        if not query or query.lower() in ("exit", "quit", "q"):
            print("Bye!")
            break
        rag_query(faiss_vs, bm25_retriever, cross_encoder, query)

if __name__ == "__main__":
    main()
