import re
from llama_index.core.schema import Document
from llama_index.core.node_parser import SemanticSplitterNodeParser
from llama_index.core import Settings
from llama_index.readers.file import PyMuPDFReader

import config

def split_by_articles(text):
    return re.split(r"(มาตรา\s+\d+)", text)

def load_documents():
    pdf_files = sorted(config.DOCS_DIR.glob("*.pdf"))

    if not pdf_files:
        raise FileNotFoundError(
            f"No PDFs found in {config.DOCS_DIR}"
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
        for i, d in enumerate(docs):
            d.metadata["source"] = pdf.name
            d.metadata["doc_type"] = "law"
            d.metadata["page_label"] = str(d.metadata.get("page_label", i + 1))

        documents.extend(docs)

        print(f"       => {len(docs)} pages")

    print(f"\n[LOAD] Total Pages: {len(documents)}")

    return documents

def build_nodes(documents):
    print("[CHUNK] Article-aware + Semantic chunking...")

    processed_docs = []

    for doc in documents:
        parts = split_by_articles(doc.text)

        for i in range(0, len(parts), 2):
            chunk_text = parts[i]

            if i + 1 < len(parts):
                chunk_text += parts[i + 1]

            if not chunk_text.strip():  # skip empty chunks
                continue

            # copy metadata
            preserved_metadata = doc.metadata.copy()

            processed_docs.append(
                Document(
                    text=chunk_text,
                    metadata=preserved_metadata
                )
            )

    parser = SemanticSplitterNodeParser(
        buffer_size=1,
        breakpoint_percentile_threshold=85,
        embed_model=Settings.embed_model,
    )

    nodes = parser.get_nodes_from_documents(processed_docs)

    print(f"[CHUNK] Created {len(nodes)} nodes")

    return nodes
