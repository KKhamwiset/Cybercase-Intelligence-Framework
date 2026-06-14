"""
Q&A Templates — STIX → instruction pairs
========================================
Pure formatting helpers that turn parsed MITRE ATT&CK entities/relationships
into (question, answer) pairs. Answer wording deliberately mirrors the style of
the gold ``reference_answer`` fields in evaluation/Thai_dataset.json so the
fine-tuned model is optimised toward the same distribution the comparison
measures (faithfulness / correctness / ROUGE).

All output is English — translation to Thai is a separate downstream stage in
the RAG pipeline (see pipeline/cross_lingual.py), so the reasoning model is
trained English-in / English-out.
"""

from __future__ import annotations

import random
import re

_CITATION_RE = re.compile(r"\(Citation:[^)]*\)")
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_WS_RE = re.compile(r"\s+")
_EMPTY_PARENS_RE = re.compile(r"\(\s*\)")
# list-introducers left dangling after their items (links/citations) were stripped,
# e.g. "such as  and" / "including ." -> drop the orphaned introducer
_DANGLING_RE = re.compile(
    r"\b(?:such as|including|for example|e\.g\.,?)\s*(?=[.,;:]|\band\b|\bor\b)", re.I
)
_SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([,.;:!?])")
_SENTENCE_RE = re.compile(r"\s*(.+?[.!?])(?:\s|$)", re.S)


def clean_text(text: str, max_chars: int | None = None) -> str:
    """Strip MITRE markdown noise (citations, links) and collapse whitespace.

    Truncation NEVER cuts mid-word: it prefers a sentence boundary, then falls
    back to a word boundary. Gaps left by removed citations/links (e.g.
    "such as  and") are cleaned so the model never learns broken fragments —
    the v2 dataset's mid-word cuts taught the model to hallucinate/garble.
    """
    if not text:
        return ""
    text = _CITATION_RE.sub("", text)
    text = _MD_LINK_RE.sub(r"\1", text)        # [ftp](url) -> ftp
    text = text.replace("<code>", "`").replace("</code>", "`")
    text = _EMPTY_PARENS_RE.sub("", text)
    text = _DANGLING_RE.sub("", text)
    text = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", text)
    text = _WS_RE.sub(" ", text).strip()
    if max_chars and len(text) > max_chars:
        cut = text[:max_chars]
        end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
        if end >= max_chars * 0.5:
            text = cut[: end + 1].strip()                  # stop at a full sentence
        else:
            sp = cut.rfind(" ")
            text = (cut[:sp] if sp > 0 else cut).strip()   # at least stop at a word
    return text


def first_sentence(text: str, max_chars: int = 300) -> str:
    """First COMPLETE sentence of a description — used for per-mitigation blurbs
    so list answers never contain a sentence chopped mid-way."""
    text = clean_text(text)
    m = _SENTENCE_RE.match(text)
    s = (m.group(1) if m else text).strip()
    if len(s) > max_chars:                                 # safety cap, word-boundary
        sp = s[:max_chars].rfind(" ")
        s = (s[:sp] if sp > 0 else s[:max_chars]).strip()
    return s


def _pick(rng: random.Random | None, options: list[str]) -> str:
    return rng.choice(options) if rng else options[0]


def _join_list(items: list[str], max_items: int) -> str:
    items = [i for i in items if i]
    if len(items) > max_items:
        items = items[:max_items]
    return "; ".join(items)


# ──────────────────────────────────────────────────────────────────────────────
# TECHNIQUE / SUB-TECHNIQUE
# ──────────────────────────────────────────────────────────────────────────────
def technique_lookup(name, attack_id, desc, rng=None):
    q = _pick(rng, [
        f"What is {name} ({attack_id})?",
        f"Explain the MITRE ATT&CK technique {name} ({attack_id}).",
        f"What does {attack_id} refer to in MITRE ATT&CK?",
    ])
    a = f"{name} ({attack_id}) is a MITRE ATT&CK technique — {desc}"
    if not a.rstrip().endswith("."):
        a = a.rstrip() + "."
    return q, a


def mitigation_lookup(name, attack_id, desc, mitigations, rng=None):
    """mitigations: list of (m_name, m_id, m_desc_short)."""
    q = _pick(rng, [
        f"What mitigations exist for {name} ({attack_id})?",
        f"How can an organisation defend against {name} ({attack_id})?",
        f"What are the recommended mitigations for {attack_id}?",
    ])
    mit_strs = [f"{m_name} ({m_id}): {m_desc.rstrip('.!?')}"
                for m_name, m_id, m_desc in mitigations]
    mit_list = _join_list(mit_strs, 8)
    a = (
        f"{name} ({attack_id}) is a MITRE ATT&CK technique — {desc} "
        f"Recommended mitigations include: {mit_list}. "
        f"Implementing these controls reduces the risk of adversaries "
        f"successfully executing {name} against your environment."
    )
    return q, a


def technique_profile(name, attack_id, desc, mitigations, groups, tactics, rng=None):
    """Compound 'full overview' answer — description + tactic(s) + mitigations +
    groups in one reply. Teaches the model to give COMPLETE multi-part answers
    (lifts answer-correctness/completeness) instead of stopping after the lookup.
    mitigations: [(m_name, m_id, m_desc)]; groups: [(g_name, g_id)];
    tactics: [(tac_name, tac_id)].
    """
    q = _pick(rng, [
        f"Give a complete overview of {name} ({attack_id}).",
        f"Provide a full MITRE ATT&CK profile for {name} ({attack_id}).",
        f"Tell me about {name} ({attack_id}) — what it is, how to mitigate it, "
        f"and which groups use it.",
    ])
    intro = f"{name} ({attack_id}) is a MITRE ATT&CK technique — {desc}"
    if not intro.rstrip().endswith("."):
        intro = intro.rstrip() + "."
    parts = [intro]
    if tactics:
        parts.append(
            "It falls under the "
            f"{_join_list([f'{tn} ({ti})' for tn, ti in tactics], 6)} tactic(s)."
        )
    if mitigations:
        mit_str = _join_list(
            [f"{mn} ({mi}): {md.rstrip('.!?')}" for mn, mi, md in mitigations], 8)
        parts.append(f"Recommended mitigations include: {mit_str}.")
    if groups:
        grp_str = _join_list([f"{gn} ({gi})" for gn, gi in groups], 12)
        parts.append(f"Threat groups known to use it include: {grp_str}.")
    return q, " ".join(parts)


def technique_groups(name, attack_id, groups, rng=None):
    """groups: list of (g_name, g_id)."""
    q = _pick(rng, [
        f"Which threat groups use {name} ({attack_id})?",
        f"What adversary groups are known to employ {name} ({attack_id})?",
    ])
    glist = _join_list([f"{g_name} ({g_id})" for g_name, g_id in groups], 12)
    a = (
        f"The following MITRE ATT&CK groups are known to use "
        f"{name} ({attack_id}): {glist}."
    )
    return q, a


def technique_detection(name, attack_id, components, rng=None):
    """components: list of data source/component name strings."""
    q = _pick(rng, [
        f"How can {name} ({attack_id}) be detected?",
        f"What data sources help detect {name} ({attack_id})?",
    ])
    clist = _join_list(components, 10)
    a = (
        f"{name} ({attack_id}) can be detected by monitoring the following "
        f"data sources/components: {clist}."
    )
    return q, a


def tactic_techniques(tactic_name, tactic_id, techniques, rng=None):
    """techniques: list of (t_name, t_id)."""
    q = _pick(rng, [
        f"Which techniques belong to the {tactic_name} tactic ({tactic_id})?",
        f"What MITRE ATT&CK techniques fall under {tactic_name} ({tactic_id})?",
    ])
    tlist = _join_list([f"{t_name} ({t_id})" for t_name, t_id in techniques], 15)
    a = (
        f"The {tactic_name} tactic ({tactic_id}) in MITRE ATT&CK includes "
        f"techniques such as: {tlist}."
    )
    return q, a


# ──────────────────────────────────────────────────────────────────────────────
# GROUP
# ──────────────────────────────────────────────────────────────────────────────
def group_techniques(group_name, group_id, techniques, rng=None):
    q = _pick(rng, [
        f"Which techniques does the group {group_name} ({group_id}) use?",
        f"What MITRE ATT&CK techniques are attributed to {group_name} ({group_id})?",
    ])
    tlist = _join_list([f"{t_name} ({t_id})" for t_name, t_id in techniques], 15)
    a = (
        f"{group_name} ({group_id}) is a MITRE ATT&CK group. It is known to use "
        f"techniques including: {tlist}."
    )
    return q, a


def group_software(group_name, group_id, software, rng=None):
    q = _pick(rng, [
        f"What software or tools does {group_name} ({group_id}) use?",
        f"Which malware and tools are associated with {group_name} ({group_id})?",
    ])
    slist = _join_list([f"{s_name} ({s_id})" for s_name, s_id in software], 15)
    a = (
        f"{group_name} ({group_id}) is associated with the following "
        f"software/tools in MITRE ATT&CK: {slist}."
    )
    return q, a


# ──────────────────────────────────────────────────────────────────────────────
# SOFTWARE
# ──────────────────────────────────────────────────────────────────────────────
def software_techniques(sw_name, sw_id, sw_type, techniques, rng=None):
    kind = "malware" if sw_type == "malware" else "a tool"
    q = _pick(rng, [
        f"What techniques does {sw_name} ({sw_id}) implement?",
        f"Which MITRE ATT&CK techniques are used by {sw_name} ({sw_id})?",
    ])
    tlist = _join_list([f"{t_name} ({t_id})" for t_name, t_id in techniques], 15)
    a = (
        f"{sw_name} ({sw_id}) is {kind} tracked in MITRE ATT&CK. It implements "
        f"techniques including: {tlist}."
    )
    return q, a


def software_type_query(sw_name, sw_id, sw_type, desc, rng=None):
    kind = "malware" if sw_type == "malware" else "a tool"
    q = _pick(rng, [
        f"Is {sw_name} ({sw_id}) malware or a tool?",
        f"How is {sw_name} ({sw_id}) classified in MITRE ATT&CK?",
    ])
    a = f"{sw_name} ({sw_id}) is classified as {kind} in MITRE ATT&CK — {desc}"
    if not a.rstrip().endswith("."):
        a = a.rstrip() + "."
    return q, a


# ──────────────────────────────────────────────────────────────────────────────
# CAMPAIGN
# ──────────────────────────────────────────────────────────────────────────────
def campaign_attribution(camp_name, camp_id, groups, rng=None):
    q = _pick(rng, [
        f"Which group is the campaign {camp_name} ({camp_id}) attributed to?",
        f"Who is behind the {camp_name} ({camp_id}) campaign?",
    ])
    glist = _join_list([f"{g_name} ({g_id})" for g_name, g_id in groups], 6)
    a = f"The campaign {camp_name} ({camp_id}) is attributed to {glist}."
    return q, a


# ──────────────────────────────────────────────────────────────────────────────
# GROUNDED (RAG-style) — wraps a question with a retrieved-context block so the
# model learns the pipeline's "answer only from context" behaviour.
# ──────────────────────────────────────────────────────────────────────────────
def build_entity_context(entity_type, node_label, name, attack_id, desc):
    """Format one entity like context_builder.build_context's semantic block."""
    bar = "=" * 60
    header = f"[1] {entity_type}: {node_label}"
    if name:
        header += f" — {name}"
    if attack_id:
        header += f" ({attack_id})"
    return (
        f"{bar}\n"
        "RETRIEVED CONTEXT FROM MITRE ATT&CK KNOWLEDGE BASE\n"
        f"{bar}\n\n"
        "--- Semantic Search Results ---\n\n"
        f"{header} | relevance: 0.950\n"
        f"  {desc}"
    )


def grounded_user_prompt(context: str, question: str) -> str:
    """User turn for a grounded example (context + question)."""
    return f"{context}\n\n{'=' * 60}\nQUESTION\n{'=' * 60}\n{question}"
