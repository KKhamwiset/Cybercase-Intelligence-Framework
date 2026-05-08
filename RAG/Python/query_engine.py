from llama_index.core.response_synthesizers import get_response_synthesizer
from llama_index.core.query_engine import RetrieverQueryEngine

import config
from retrieval import build_retriever

def build_query_engine(retriever):
    response_synthesizer = get_response_synthesizer()
    query_engine = RetrieverQueryEngine(
        retriever=retriever,
        node_postprocessors=[config.RERANKER],
        response_synthesizer=response_synthesizer,
    )
    return query_engine

def rag_query(index, query):
    retriever = build_retriever(index, query)
    query_engine = build_query_engine(retriever)

    config.sep("QUERY")
    print(query)

    config.sep("ANSWER")
    response = query_engine.query(query)
    print(response)

    config.sep("SOURCES")
    for i, node in enumerate(response.source_nodes, 1):
        meta = node.metadata
        source = meta.get("source", "?")
        page = meta.get("page_label", "?")
        score = round(node.score, 4)
        text = node.text[:350].replace("\n", " ")

        print(f"[{i}] {source} | page={page} | score={score}")
        print(f"    {text}...\n")

    config.sep()
