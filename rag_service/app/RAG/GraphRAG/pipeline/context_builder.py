"""
Context Builder
================
Assembles the final context from Vector + Graph retrieval results
into a structured prompt for the LLM.

Functions
---------
build_context()           — format raw GraphRAGResult into a context string
build_reasoning_prompt()  — QA prompt for the Reasoning LLM (Stage 2)
build_generation_prompt() — legacy prompt kept for chain.py compatibility
"""

from ..config import FINAL_TOP_K
from ..retrieval.hybrid_retriever import GraphRAGResult


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
        context = (
            context[:max_context_length] + "\n\n... [context truncated for length]"
        )

    return context


# ──────────────────────────────────────────────────────────────────────────────
# Reasoning prompt (Stage 2)
# Used by: agent_graph._node_reasoning
# ──────────────────────────────────────────────────────────────────────────────
_REASONING_PROMPT_TEMPLATE = """\
You are a MITRE ATT&CK incident analysis assistant with short-term conversational memory.

════════════════════════════════════════
MEMORY MANAGEMENT
════════════════════════════════════════

You maintain a short-term memory of the current analysis session.
Memory is stored as a structured incident context and is carried across turns.

CURRENT SESSION MEMORY:
{session_memory}

────────────────────────────────────────
MEMORY UPDATE RULES:
────────────────────────────────────────
After every turn, extract and update the following fields if new information is provided:

{
  "incident_summary": "<one-line summary of the incident so far>",
  "filled_slots": {
    "initial_access":        "<value or null>",
    "credential_theft":      "<value or null>",
    "privilege_escalation":  "<value or null>",
    "lateral_movement":      "<value or null>",
    "impact":                "<value or null>"
  },
  "confirmed_techniques": ["<T-ID: name>", ...],
  "open_questions":        ["<anything still unclear>"],
  "turn_count":            <int>
}

Rules:
- Never overwrite a filled slot unless the user explicitly corrects it
- If the user provides conflicting info, add it to open_questions instead
- Increment turn_count every response
- Keep incident_summary under 30 words

════════════════════════════════════════
CONVERSATION HISTORY (last {max_turns} turns):
════════════════════════════════════════
{conversation_history}

════════════════════════════════════════
CURRENT QUERY:
════════════════════════════════════════
{user_query}

════════════════════════════════════════
RETRIEVED MITRE ATT&CK CONTEXT:
════════════════════════════════════════
{retrieved_context}

{gap_warning}

════════════════════════════════════════
RESPONSE INSTRUCTIONS:
════════════════════════════════════════
1. Answer based on retrieved context + session memory combined
2. Reference previous turns naturally when relevant
   Example: "จากที่คุณบอกก่อนหน้าว่าใช้ SQL Injection..."
3. If a slot was filled in a previous turn, do not ask for it again
4. End your response with an updated MEMORY BLOCK in this exact format:

<memory_update>
{
  "incident_summary": "...",
  "filled_slots": { ... },
  "confirmed_techniques": [...],
  "open_questions": [...],
  "turn_count": ...
}
</memory_update>
"""


import json

def build_reasoning_prompt(
    session_memory: dict,
    max_turns: int,
    conversation_history: list,
    user_query: str,
    retrieved_context: str,
    gap_warning: str,
) -> str:
    """Build the user prompt for the Reasoning LLM (Stage 2)."""
    
    # Format history
    history_str = ""
    if conversation_history:
        history_str = "\n".join(
            [f"USER: {turn['user']}\nAGENT: {turn['agent']}" for turn in conversation_history[-max_turns:]]
        )
    else:
        history_str = "No prior history."

    # Format memory
    memory_str = json.dumps(session_memory, ensure_ascii=False, indent=2) if session_memory else "{}"

    prompt = _REASONING_PROMPT_TEMPLATE.replace("{session_memory}", memory_str)
    prompt = prompt.replace("{max_turns}", str(max_turns))
    prompt = prompt.replace("{conversation_history}", history_str)
    prompt = prompt.replace("{user_query}", user_query)
    prompt = prompt.replace("{retrieved_context}", retrieved_context)
    prompt = prompt.replace("{gap_warning}", gap_warning)
    
    return prompt


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
            "อธิบายเหตุการณ์ข้างต้นโดยอ้างอิงจากข้อมูล Context ที่ให้มาเท่านั้น\n"
            "ใช้ภาษาที่เข้าใจง่ายสำหรับผู้ที่ไม่มีพื้นฐานเทคนิค\n"
            "คงศัพท์เทคนิคและ ATT&CK ID ไว้เป็นภาษาอังกฤษ"
        )
    else:
        parts.append(
            "Using ONLY the provided context, explain the incident in plain language for a non-technical reader.\n"
            "Follow the four-section format from your instructions exactly.\n"
            "Cite ATT&CK IDs for every technique mentioned."
        )

    return "\n".join(parts)
