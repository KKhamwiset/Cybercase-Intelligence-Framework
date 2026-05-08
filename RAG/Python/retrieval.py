from llama_index.core.retrievers import BaseRetriever, QueryFusionRetriever
from llama_index.core.schema import QueryBundle
from llama_index.retrievers.bm25 import BM25Retriever

import config

class SourceFilterRetriever(BaseRetriever):

    def __init__(self, retriever, source_filter=None):
        self._retriever = retriever
        self._source_filter = source_filter
        super().__init__()

    def _retrieve(self, query_bundle: QueryBundle):
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

    return None

def build_retriever(index, query: str = ""):

    print("[RETRIEVER] Building hybrid retriever")

    source_filter = detect_relevant_source(query)

    if source_filter:
        print(f"[FILTER] source = {source_filter}")
    else:
        print("[FILTER] No filter — searching all documents")

    vector_retriever = index.as_retriever(
        similarity_top_k=config.TOP_K
    )

    bm25_retriever = BM25Retriever.from_defaults(
        docstore=index.docstore,
        similarity_top_k=config.TOP_K,
    )

    fusion_retriever = QueryFusionRetriever(
        [vector_retriever, bm25_retriever],
        similarity_top_k=config.TOP_K,
        num_queries=3,
        mode="reciprocal_rerank",
        use_async=True,
        verbose=True,
    )

    retriever = SourceFilterRetriever(
        retriever=fusion_retriever,
        source_filter=source_filter
    )

    return retriever
