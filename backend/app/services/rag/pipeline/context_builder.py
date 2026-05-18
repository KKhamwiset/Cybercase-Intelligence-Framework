"""
Context Builder
================
Assembles the final context from Vector + Graph retrieval results
into a structured prompt for the LLM.
"""

from app.services.rag.retrieval.hybrid_retriever import GraphRAGResult
from app.services.rag.config import FINAL_TOP_K


def build_context(result: GraphRAGResult, max_context_length: int = 10000) -> str:
    """Build a structured context string from GraphRAG results.

    The context is formatted for optimal LLM consumption:
    1. Semantic matches with scores (most relevant first)
    2. Graph context showing structured relationships

    Args:
        result: The GraphRAGResult from hybrid retrieval.
        max_context_length: Maximum character length of context.

    Returns:
        Formatted context string.
    """
    sections = []

    # ── Section 1: Top Semantic Matches ───────────────────────────────────
    sections.append("=" * 60)
    sections.append("RETRIEVED CONTEXT FROM MITRE ATT&CK KNOWLEDGE BASE")
    sections.append("=" * 60)

    sections.append("\n--- Semantic Search Results ---")

    for i, vr in enumerate(result.vector_results[:FINAL_TOP_K], 1):
        entity_type = vr.metadata.get("entity_type", "Unknown")
        node_label = vr.metadata.get("node_label", vr.metadata.get("edge_label", ""))
        name = vr.metadata.get("name", vr.metadata.get("source_name", ""))
        attack_id = vr.metadata.get("attack_id", "")

        header = f"[{i}] {entity_type}: {node_label}"
        if name:
            header += f" — {name}"
        if attack_id:
            header += f" ({attack_id})"
        header += f" | relevance: {vr.score:.3f}"

        sections.append(f"\n{header}")

        # Include document text (truncated)
        doc_text = vr.document[:600].replace("\n", " ").strip()
        sections.append(f"  {doc_text}")

    # ── Section 2: Graph Context ──────────────────────────────────────────
    if result.graph_results:
        sections.append("\n\n--- Graph Context (Structured Relationships) ---")

        for sg in result.graph_results:
            text = sg.to_text()
            if text:
                sections.append(f"\n{text}")

    # ── Combine ───────────────────────────────────────────────────────────
    context = "\n".join(sections)

    if len(context) > max_context_length:
        context = context[:max_context_length] + "\n\n... [context truncated for length]"

    return context


def build_generation_prompt(
    context: str,
    original_query: str,
    english_query: str,
    respond_in_thai: bool = True,
) -> str:
    """Build the final prompt for LLM generation.

    Args:
        context: The assembled context from build_context().
        original_query: The user's original query (may be Thai).
        english_query: The translated English query (for reference).
        respond_in_thai: Whether to respond in Thai.

    Returns:
        The complete user prompt for the LLM.
    """
    parts = []

    parts.append(context)

    parts.append("\n" + "=" * 60)
    parts.append("USER QUESTION")
    parts.append("=" * 60)

    if original_query != english_query:
        parts.append(f"Original (Thai): {original_query}")
        parts.append(f"Translated (English): {english_query}")
    else:
        parts.append(f"Question: {original_query}")

    parts.append("\n" + "=" * 60)
    parts.append("INSTRUCTIONS")
    parts.append("=" * 60)

    if respond_in_thai:
        parts.append(
            "ตอบคำถามข้างต้นเป็นภาษาไทย โดยอ้างอิงจากข้อมูล Context ที่ให้มาเท่านั้น\n"
            "คงศัพท์เทคนิคเป็นภาษาอังกฤษ ระบุ ATT&CK ID กำกับทุกครั้ง"
        )
    else:
        parts.append(
            "Answer the question above using ONLY the provided context.\n"
            "Cite ATT&CK IDs where applicable."
        )

    return "\n".join(parts)
