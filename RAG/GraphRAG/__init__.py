"""
MITRE ATT&CK GraphRAG Pipeline
================================
Hybrid Graph + Vector DB RAG with Cross-Lingual (Thai ↔ English) support.

Architecture:
    1. Neo4j (Graph DB)  → Structured relationships & multi-hop traversal
    2. ChromaDB (Vector)  → Semantic search over entity/relationship descriptions
    3. LangChain (LCEL)   → Orchestration pipeline
    4. Claude (LLM)       → Cross-lingual generation (Thai I/O)
"""

__version__ = "1.0.0"
