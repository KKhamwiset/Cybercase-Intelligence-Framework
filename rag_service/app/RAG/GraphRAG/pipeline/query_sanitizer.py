"""
Retrieval Query Sanitizer
=========================
Cleans LLM-written retrieval queries before they are embedded.

Used by the BROADEN_SEARCH path in ``agent_graph._node_broaden_search``: the
evaluator writes a rewritten query as free text, which routinely comes back
with markdown emphasis and bare ATT&CK ID tokens. Both pull the embedding
towards ID/metadata matches instead of the technique descriptions we want.
"""

from __future__ import annotations

import re

_ATTACK_ID_RE = re.compile(r"\b(?:TA|DS|T|S|G|M|C)\d{4}(?:\.\d{3})?\b")
_MARKDOWN_RE = re.compile(r"[*_`#>]+")


def sanitize_retrieval_query(text: str) -> str:
    """Strip markdown and bare ATT&CK ID tokens from a rewritten query.

    Rewrites go straight into embedding + rerank; bold markers and ID tokens
    (seen live: ``**Brute Force T1110 Credential Access, …``) pull in
    ID/metadata matches instead of technique descriptions.
    """
    t = _MARKDOWN_RE.sub(" ", text)
    t = _ATTACK_ID_RE.sub(" ", t)
    t = re.sub(r"\(\s*\)", " ", t)  # empty parens left by removed IDs
    t = re.sub(r"\s+", " ", t)  # also collapses newlines — queries are one line
    return t.strip(" .,;:-–—")
