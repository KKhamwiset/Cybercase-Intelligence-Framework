"""
Throwaway perf probe for the GraphRAG agentic pipeline.
Wraps each LangGraph node + each retrieval sub-step (vector / rerank / graph)
with timers and runs ONE query end-to-end to find the bottleneck.

Run from rag_service/app:
    PYTHONUTF8=1 python _perf_probe.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from functools import wraps

# ── UTF-8 console (Windows) ─────────────────────────────────────────────
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# ── Load backend/.env so ANTHROPIC_API_KEY is available ─────────────────
from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[2]  # rag_service/app -> repo root
load_dotenv(_REPO_ROOT / "backend" / ".env")

# ── Timing accumulators ─────────────────────────────────────────────────
TIMINGS: dict[str, dict] = {}


def _record(label: str, dt: float) -> None:
    e = TIMINGS.setdefault(label, {"total": 0.0, "calls": 0})
    e["total"] += dt
    e["calls"] += 1


def timed(label: str):
    """Decorator factory that records wall time per call (summed across calls)."""

    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            t0 = time.perf_counter()
            try:
                return fn(*args, **kwargs)
            finally:
                _record(label, time.perf_counter() - t0)

        return wrapper

    return deco


def main() -> None:
    from RAG.GraphRAG.pipeline.agent_graph import GraphRAGAgent

    # ── 1. Build the agent (model load + DB connect) ────────────────────
    t_build0 = time.perf_counter()
    agent = GraphRAGAgent(use_local=False)
    build_s = time.perf_counter() - t_build0
    print(f"\n[PROBE] Agent build (model load + connect): {build_s:.2f}s\n")

    # ── 2. Instrument graph nodes (high-level breakdown) ────────────────
    node_methods = [
        "_node_route_query",
        "_node_prepare",
        "_node_retrieve",
        "_node_evaluate_context",
        "_node_broaden_search",
        "_node_reasoning",
        "_node_translate_output",
    ]
    for name in node_methods:
        orig = getattr(agent, name)
        setattr(agent, name, timed(f"node:{name}")(orig))
    # Rebuild graph so it picks up the wrapped bound methods
    agent.graph = agent._build_graph()

    # ── 3. Instrument retrieval sub-steps (tests graph hypothesis) ──────
    r = agent.retriever
    r.vector_retriever.search_all = timed("  ├─ vector.search_all")(
        r.vector_retriever.search_all
    )
    r.reranker.rerank = timed("  ├─ reranker.rerank")(r.reranker.rerank)
    r.graph_retriever.expand = timed("  └─ graph.expand")(r.graph_retriever.expand)
    r.graph_retriever._expand_single = timed("       graph._expand_single (per seed)")(
        r.graph_retriever._expand_single
    )

    # ── 4. Run ONE realistic Thai incident query end-to-end ─────────────
    query = (
        "ผู้โจมตีส่งอีเมลฟิชชิ่งที่มีไฟล์แนบอันตรายไปยังพนักงาน "
        "จากนั้นติดตั้ง backdoor เพื่อคงการเข้าถึง และยกระดับสิทธิ์เป็น admin "
        "ก่อนขโมยฐานข้อมูลลูกค้าออกไปยังเซิร์ฟเวอร์ภายนอก"
    )
    print(f"[PROBE] Query: {query}\n")

    t_q0 = time.perf_counter()
    resp = agent.query(query, verbose=False)
    total_s = time.perf_counter() - t_q0

    print(f"\n[PROBE] status = {resp.status}")
    print(f"[PROBE] answer length = {len(resp.answer)} chars")

    # ── 5. Report ───────────────────────────────────────────────────────
    print("\n" + "=" * 64)
    print(f"END-TO-END query() wall time: {total_s:.2f}s")
    print("=" * 64)
    print(f"{'stage':<42}{'total(s)':>10}{'calls':>6}{'%':>6}")
    print("-" * 64)
    # Print nodes in graph order first, then sub-steps grouped under retrieve
    order = [
        "node:_node_route_query",
        "node:_node_prepare",
        "node:_node_retrieve",
        "  ├─ vector.search_all",
        "  ├─ reranker.rerank",
        "  └─ graph.expand",
        "       graph._expand_single (per seed)",
        "node:_node_evaluate_context",
        "node:_node_broaden_search",
        "node:_node_reasoning",
        "node:_node_translate_output",
    ]
    for label in order:
        if label not in TIMINGS:
            continue
        e = TIMINGS[label]
        pct = 100.0 * e["total"] / total_s if total_s else 0.0
        disp = label.replace("node:_node_", "")
        print(f"{disp:<42}{e['total']:>10.2f}{e['calls']:>6}{pct:>6.1f}")
    print("-" * 64)

    agent.close()


if __name__ == "__main__":
    main()
