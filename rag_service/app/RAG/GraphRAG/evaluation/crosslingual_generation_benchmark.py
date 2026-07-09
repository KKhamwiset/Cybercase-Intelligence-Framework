"""
Cross-Lingual Generation Benchmark
====================================
Compares 5 generation-path variants over FROZEN retrieval contexts, so
score differences are attributable to the generation stage only.

Production truth (agent_graph.py, the path the API serves): the Thai
query is NEVER translated — _node_prepare sets english_query = original
("no input translation") and _node_retrieve decomposes the Thai incident
into native-language sub-queries for quota retrieval. (chain.py still
translates, but it is the legacy non-agent path.)

Variants (all consume the same cached context per sample):

  A  baseline   production agent shape: prompt shows the Thai question
                only, reason in English -> translate to Thai (2 calls).
  B  +MT query  as A but the prompt also shows a machine translation of
                the question (production would need +1 call for it, so
                B is costed at 3 calls; the MT is cached from the
                retrieve phase).
  C  single     one call with the production fast-mode prompt
                (get_fast_system_prompt): reason internally, write Thai
                directly (1 call — candidate for halving cost/latency).
  D  cheap-xl8  as A but the EN->TH translation stage uses the cheap
                model (skipped automatically when it equals the
                reasoning model).
  E  ceiling    English question (dataset query_en), English answer,
                no Thai stage (1 call). Diagnostic reference only —
                never a deployment candidate. Scored with
                language-independent metrics.

Phases (run separately; every phase is resumable/cached):

  retrieve  translate query once + hybrid retrieval once per sample
            -> data/gen_bench/contexts.json   (the frozen contexts)
  generate  run variants over cached contexts
            -> data/gen_bench/generations.jsonl (append; resume skips
            existing sample x variant pairs)
  score     deterministic metrics only (free): technique ID P/R/F1,
            tactic F1, per-step answer coverage by cue_type,
            thai_char_ratio, 4-section structure, id_survival;
            paired bootstrap CI + Wilcoxon vs baseline A
            -> results/crosslingual_generation_report.md

Usage:
    cd rag_service/app
    python -m RAG.GraphRAG.evaluation.crosslingual_generation_benchmark --phase retrieve [--max-samples 8]
    python -m RAG.GraphRAG.evaluation.crosslingual_generation_benchmark --phase generate [--variants A,B,C,D,E]
    python -m RAG.GraphRAG.evaluation.crosslingual_generation_benchmark --phase score
"""

from __future__ import annotations

import argparse
import io
import json
import random
import sys
import time
from pathlib import Path

# Fix relative imports when run directly
if __package__ is None or __package__ == "evaluation":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    __package__ = "GraphRAG.evaluation"

# UTF-8 fix for Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from .attack_id_metrics import (
    extract_all_techniques,
    extract_technique_ids,
    id_survival,
    structure_compliance,
    tactic_level_score,
    technique_set_score,
    thai_char_ratio,
)

DATA_DIR = Path(__file__).resolve().parent / "data"
BENCH_DIR = DATA_DIR / "gen_bench"
RESULTS_DIR = Path(__file__).resolve().parent / "results"

CONTEXTS_PATH = BENCH_DIR / "contexts.json"
GENERATIONS_PATH = BENCH_DIR / "generations.jsonl"
REPORT_PATH = RESULTS_DIR / "crosslingual_generation_report.md"
LOOKUP_PATH = DATA_DIR / "attack_lookup.json"

DEFAULT_DATASET = DATA_DIR / "incident_draft.json"

VARIANTS = ["A", "B", "C", "D", "E"]

# Required section headings per output language (from the production
# translation prompt in pipeline/cross_lingual.py).
HEADINGS_TH = ["สรุปเหตุการณ์", "ลำดับการโจมตี", "เทคนิคการโจมตีที่ตรวจพบ", "ผลกระทบที่เกิดขึ้น"]
HEADINGS_EN = ["INCIDENT SUMMARY", "ATTACK SEQUENCE",
               "MITRE ATT&CK TECHNIQUES IDENTIFIED", "IMPACT ASSESSMENT"]


# ══════════════════════════════════════════════════════════════════════════════
# DATASET
# ══════════════════════════════════════════════════════════════════════════════


def load_samples(dataset_path: Path, max_samples: int = 0) -> list[dict]:
    """Thai incident samples with gold IDs (the benchmark's unit of work)."""
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    samples = [
        s for s in data
        if s.get("language") == "th" and s.get("gold_attack_ids") and s.get("query_en")
    ]
    if max_samples:
        samples = samples[:max_samples]

    for i, s in enumerate(samples):
        s.setdefault("id", f"sample_{i:03d}")
    return samples


# ══════════════════════════════════════════════════════════════════════════════
# PHASE R — FREEZE RETRIEVAL
# ══════════════════════════════════════════════════════════════════════════════


def phase_retrieve(samples: list[dict], use_local: bool = False) -> None:
    """Retrieve ONCE per sample, mirroring the production agent path
    (_node_retrieve): Thai incident -> decomposer -> native-language
    sub-queries -> retrieve_multi_quota -> build_context(15/8).

    A machine translation of the query is ALSO cached here — production
    does not need it, only variant B's prompt does (B is costed +1 call
    for it at scoring time).
    """
    from ..config import VECTOR_TOP_K
    from ..pipeline.context_builder import build_context
    from ..pipeline.cross_lingual import CrossLingualLayer
    from ..pipeline.query_decomposer import QueryDecomposer
    from ..retrieval.hybrid_retriever import HybridRetriever

    existing: dict[str, dict] = {}
    if CONTEXTS_PATH.exists():
        with open(CONTEXTS_PATH, "r", encoding="utf-8") as f:
            existing = {e["id"]: e for e in json.load(f)}
        print(f"[RETRIEVE] Resume: {len(existing)} contexts already cached")

    todo = [s for s in samples if s["id"] not in existing]
    if not todo:
        print("[RETRIEVE] Nothing to do")
        return

    translator = CrossLingualLayer(use_local=use_local)
    decomposer = QueryDecomposer(use_local=use_local)
    retriever = HybridRetriever()

    try:
        for i, sample in enumerate(todo):
            t0 = time.perf_counter()
            sub_queries = decomposer.decompose(
                incident=sample["query"], verbose=False
            )
            all_queries: list[str] = []
            for q in [sample["query"], *sub_queries]:
                if q and q.strip() and q not in all_queries:
                    all_queries.append(q)
            result = retriever.retrieve_multi_quota(
                all_queries, per_query_k=3, top_k=VECTOR_TOP_K,
                max_vector=15, max_graph=8,
            )
            context = build_context(result, max_vector=15, max_graph=8)
            english_query = translator.translate_query(sample["query"])
            latency_ms = (time.perf_counter() - t0) * 1000

            # Ordered retrieved ids (vector first, then graph) — enables
            # step-coverage@k retrieval scoring straight from this cache.
            retrieved_ids: list[str] = []
            seen: set[str] = set()
            for vr in result.vector_results:
                if vr.stix_id not in seen:
                    retrieved_ids.append(vr.stix_id)
                    seen.add(vr.stix_id)
            chunks = [vr.document for vr in result.vector_results[:15]]
            for gr in result.graph_results:
                if gr.center_node and gr.center_node.stix_id not in seen:
                    retrieved_ids.append(gr.center_node.stix_id)
                    seen.add(gr.center_node.stix_id)
                for nb in gr.neighbors:
                    if nb.stix_id not in seen:
                        retrieved_ids.append(nb.stix_id)
                        seen.add(nb.stix_id)
                text = gr.to_text()
                if text:
                    chunks.append(text)

            # Raw retrieval pieces the mapping module (build_mitre_table)
            # consumes — cached so the mapping eval can replay the REAL
            # production filter offline against any answer.
            mapping_raw = {
                "vector": [
                    {
                        "stix_id": vr.stix_id,
                        "score": float(vr.score),
                        "document": (vr.document or "")[:300],
                        "metadata": {
                            "entity_type": (vr.metadata or {}).get("entity_type", ""),
                            "name": (vr.metadata or {}).get("name", ""),
                            "node_label": (vr.metadata or {}).get("node_label", ""),
                            "attack_id": (vr.metadata or {}).get("attack_id", ""),
                        },
                    }
                    for vr in result.vector_results
                ],
                "graph_nodes": [
                    [
                        {
                            "stix_id": n.stix_id,
                            "name": n.name,
                            "label": n.label,
                            "attack_id": getattr(n, "attack_id", "") or "",
                            "description": (getattr(n, "description", "") or "")[:300],
                        }
                        for n in filter(None, [gr.center_node, *gr.neighbors])
                    ]
                    for gr in result.graph_results
                ],
                "in_tactic_edges": [
                    {"source_name": e.source_name, "target_name": e.target_name}
                    for gr in result.graph_results
                    for e in gr.edges
                    if e.edge_label == "IN_TACTIC"
                ],
            }

            existing[sample["id"]] = {
                "id": sample["id"],
                "query": sample["query"],
                "query_en_dataset": sample["query_en"],
                "english_query_mt": english_query,
                "sub_queries": sub_queries,
                "context": context,
                "context_chunks": chunks,
                "retrieved_stix_ids": retrieved_ids,
                "retrieval_latency_ms": latency_ms,
                "mapping_raw": mapping_raw,
            }
            print(f"  [{i+1}/{len(todo)}] {sample['id']}: "
                  f"{len(retrieved_ids)} ids, {len(context)} chars, "
                  f"{latency_ms:.0f}ms")

            # Persist incrementally — retrieval is the slow phase.
            BENCH_DIR.mkdir(parents=True, exist_ok=True)
            with open(CONTEXTS_PATH, "w", encoding="utf-8") as f:
                json.dump(list(existing.values()), f, indent=2, ensure_ascii=False)
    finally:
        retriever.close()

    print(f"[RETRIEVE] {len(existing)} contexts cached at {CONTEXTS_PATH}")


# ══════════════════════════════════════════════════════════════════════════════
# PHASE G — GENERATION VARIANTS
# ══════════════════════════════════════════════════════════════════════════════


def _invoke(llm, system: str, user: str) -> tuple[str, dict]:
    """One LLM call -> (text, {input_tokens, output_tokens})."""
    from langchain_core.messages import HumanMessage, SystemMessage

    response = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    content = response.content
    if isinstance(content, list):
        content = "".join(
            b.get("text", "") if isinstance(b, dict) else str(b) for b in content
        )
    usage = getattr(response, "usage_metadata", None) or {}
    return str(content), {
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
    }


def _sum_usage(*usages: dict) -> dict:
    return {
        "input_tokens": sum(u.get("input_tokens", 0) for u in usages),
        "output_tokens": sum(u.get("output_tokens", 0) for u in usages),
    }


def run_variant(variant: str, ctx: dict, reasoning_llm, cheap_llm) -> dict:
    """Execute one variant over a cached context. Returns the result row body."""
    from ..pipeline.context_builder import build_generation_prompt
    from ..pipeline.cross_lingual import CrossLingualLayer

    context = ctx["context"]
    thai_q = ctx["query"]
    en_q_mt = ctx["english_query_mt"]
    en_q_dataset = ctx["query_en_dataset"]

    t0 = time.perf_counter()

    if variant in ("A", "B", "D"):
        # Two-stage: EN reasoning -> Thai translation.
        # A/D mirror the production agent: english_query == original, so
        # build_generation_prompt renders a single Thai "Question:" line.
        # B additionally shows the machine-translated EN question — in
        # production that would cost one extra LLM call, so B reports 3.
        english_shown = en_q_mt if variant == "B" else thai_q
        user_prompt = build_generation_prompt(
            context=context, original_query=thai_q,
            english_query=english_shown, respond_in_thai=False,
        )
        intermediate_en, usage1 = _invoke(
            reasoning_llm, CrossLingualLayer.get_reasoning_system_prompt(), user_prompt
        )
        translator = cheap_llm if variant == "D" else reasoning_llm
        answer, usage2 = _invoke(
            translator, CrossLingualLayer.get_translation_system_prompt(),
            intermediate_en,
        )
        usage = _sum_usage(usage1, usage2)
        calls = 3 if variant == "B" else 2

    elif variant == "C":
        # Single call: production fast-mode fold (reason internally, write
        # Thai). english_query == original, mirroring agent query_fast.
        user_prompt = build_generation_prompt(
            context=context, original_query=thai_q,
            english_query=thai_q, respond_in_thai=True,
        )
        answer, usage = _invoke(
            reasoning_llm,
            CrossLingualLayer.get_fast_system_prompt(respond_in_thai=True),
            user_prompt,
        )
        intermediate_en, calls = "", 1

    elif variant == "E":
        # Ceiling: dataset English question, English answer, stop.
        user_prompt = build_generation_prompt(
            context=context, original_query=en_q_dataset,
            english_query=en_q_dataset, respond_in_thai=False,
        )
        answer, usage = _invoke(
            reasoning_llm, CrossLingualLayer.get_reasoning_system_prompt(), user_prompt
        )
        intermediate_en, calls = "", 1

    else:
        raise ValueError(f"Unknown variant {variant}")

    return {
        "answer": answer,
        "intermediate_en": intermediate_en,
        "llm_calls": calls,
        "usage": usage,
        "latency_ms": (time.perf_counter() - t0) * 1000,
    }


def phase_generate(
    variants: list[str],
    reasoning_model: str,
    cheap_model: str,
    max_samples: int = 0,
) -> None:
    from langchain_anthropic import ChatAnthropic

    from ..config import ANTHROPIC_API_KEY

    with open(CONTEXTS_PATH, "r", encoding="utf-8") as f:
        contexts = json.load(f)
    if max_samples:
        contexts = contexts[:max_samples]

    # D is meaningless when the cheap model IS the reasoning model.
    if "D" in variants and cheap_model == reasoning_model:
        print(f"[GENERATE] Skipping D: cheap model == reasoning model ({cheap_model})")
        variants = [v for v in variants if v != "D"]

    done: set[tuple[str, str]] = set()
    if GENERATIONS_PATH.exists():
        with open(GENERATIONS_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    done.add((row["sample_id"], row["variant"]))
        print(f"[GENERATE] Resume: {len(done)} rows already generated")

    def make_llm(model: str):
        return ChatAnthropic(  # type: ignore[call-arg]
            model=model, api_key=ANTHROPIC_API_KEY, temperature=0, max_tokens=4096,
        )

    reasoning_llm = make_llm(reasoning_model)
    cheap_llm = make_llm(cheap_model) if cheap_model != reasoning_model else reasoning_llm
    print(f"[GENERATE] reasoning={reasoning_model}  cheap={cheap_model}")
    print(f"[GENERATE] {len(contexts)} samples x {variants}")

    BENCH_DIR.mkdir(parents=True, exist_ok=True)
    n_new = n_fail = 0
    with open(GENERATIONS_PATH, "a", encoding="utf-8") as out:
        for ctx in contexts:
            for variant in variants:
                key = (ctx["id"], variant)
                if key in done:
                    continue
                try:
                    body = run_variant(variant, ctx, reasoning_llm, cheap_llm)
                except Exception as e:  # noqa: BLE001 — keep going, resume later
                    n_fail += 1
                    print(f"  {ctx['id']} {variant}: FAILED — {e}")
                    continue
                row = {
                    "sample_id": ctx["id"],
                    "variant": variant,
                    "models": {
                        "reasoning": reasoning_model,
                        "translation": cheap_model if variant == "D" else reasoning_model,
                    },
                    **body,
                }
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                out.flush()
                n_new += 1
                print(f"  {ctx['id']} {variant}: {body['llm_calls']} calls, "
                      f"{body['latency_ms']:.0f}ms, "
                      f"out={body['usage']['output_tokens']}tok")

    print(f"[GENERATE] {n_new} new rows, {n_fail} failed "
          f"(rerun with same args to resume)")


# ══════════════════════════════════════════════════════════════════════════════
# PHASE S — DETERMINISTIC SCORING + PAIRED STATS
# ══════════════════════════════════════════════════════════════════════════════


def _bootstrap_ci(deltas: list[float], n_boot: int = 10000, seed: int = 42) -> tuple[float, float]:
    """95% bootstrap CI of the mean of paired deltas."""
    if not deltas:
        return (0.0, 0.0)
    rng = random.Random(seed)
    means = []
    for _ in range(n_boot):
        resample = [deltas[rng.randrange(len(deltas))] for _ in deltas]
        means.append(sum(resample) / len(resample))
    means.sort()
    return (means[int(0.025 * n_boot)], means[int(0.975 * n_boot)])


def _wilcoxon_p(deltas: list[float]) -> float | None:
    """Two-sided Wilcoxon signed-rank p-value (scipy if available)."""
    nonzero = [d for d in deltas if d != 0]
    if len(nonzero) < 6:
        return None
    try:
        from scipy.stats import wilcoxon
        return float(wilcoxon(nonzero).pvalue)
    except ImportError:
        return None


def score_row(row: dict, sample: dict, lookup: dict) -> dict:
    """All deterministic metrics for one (sample, variant) generation."""
    answer = row["answer"]
    gold = set(sample["gold_attack_ids"])
    predicted = extract_all_techniques(answer, lookup["alias_map"])

    tech = technique_set_score(predicted, gold)
    tactic = tactic_level_score(predicted, gold, lookup["technique_to_tactics"])

    # Answer-side step coverage: does the answer cite each chronological
    # step's technique? Split by cue_type — described steps are where the
    # pipeline earns its keep.
    per_type: dict[str, list[float]] = {}
    for step in sample.get("attack_steps", []):
        step_ids = set(step.get("gold_attack_ids", []))
        hit = 1.0 if predicted & step_ids else 0.0
        per_type.setdefault(step.get("cue_type", "unspecified"), []).append(hit)
    step_cov = {
        f"step_cov_{ct}": sum(v) / len(v) for ct, v in per_type.items() if v
    }

    is_english_variant = row["variant"] == "E"
    headings = HEADINGS_EN if is_english_variant else HEADINGS_TH
    structure = structure_compliance(answer, headings)

    scores = {
        "id_precision": tech["precision"],
        "id_recall": tech["recall"],
        "id_f1": tech["f1"],
        "tactic_f1": tactic["f1"],
        "thai_ratio": thai_char_ratio(answer),
        "structure": structure["score"],
        "latency_ms": row["latency_ms"],
        "output_tokens": row["usage"]["output_tokens"],
        "llm_calls": row["llm_calls"],
        **step_cov,
    }
    if row.get("intermediate_en"):
        surv = id_survival(row["intermediate_en"], answer)
        scores["id_survival"] = surv["survival_rate"]
        scores["ids_gained_in_translation"] = len(surv["gained"])
    return scores


def phase_score(dataset_path: Path) -> None:
    samples = {s["id"]: s for s in load_samples(dataset_path)}
    with open(LOOKUP_PATH, "r", encoding="utf-8") as f:
        lookup = json.load(f)

    rows = []
    with open(GENERATIONS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))

    scored: dict[str, dict[str, dict]] = {}  # variant -> sample_id -> scores
    for row in rows:
        sample = samples.get(row["sample_id"])
        if sample is None:
            continue
        scored.setdefault(row["variant"], {})[row["sample_id"]] = score_row(
            row, sample, lookup
        )

    if not scored:
        print("[SCORE] No generations to score")
        return

    variants = [v for v in VARIANTS if v in scored]
    metric_names = sorted({m for by_id in scored.values() for s in by_id.values() for m in s})

    # ── Aggregate table ────────────────────────────────────────────────────
    lines = [
        "# Cross-Lingual Generation Benchmark — Deterministic Metrics",
        "",
        f"Samples per variant: " + ", ".join(
            f"{v}={len(scored[v])}" for v in variants
        ),
        "",
        "| Metric | " + " | ".join(variants) + " |",
        "|--------|" + "|".join(["-------"] * len(variants)) + "|",
    ]
    for metric in metric_names:
        cells = []
        for v in variants:
            vals = [s[metric] for s in scored[v].values() if metric in s]
            cells.append(f"{sum(vals) / len(vals):.3f}" if vals else "—")
        lines.append(f"| {metric} | " + " | ".join(cells) + " |")

    # ── Paired stats vs baseline A ─────────────────────────────────────────
    if "A" in scored:
        lines += ["", "## Paired deltas vs baseline A (id_f1)", "",
                  "| Variant | mean Δ | 95% CI | Wilcoxon p | n pairs |",
                  "|---------|--------|--------|------------|---------|"]
        base = scored["A"]
        for v in variants:
            if v == "A":
                continue
            common = sorted(set(base) & set(scored[v]))
            deltas = [scored[v][sid]["id_f1"] - base[sid]["id_f1"] for sid in common]
            if not deltas:
                continue
            mean_d = sum(deltas) / len(deltas)
            lo, hi = _bootstrap_ci(deltas)
            p = _wilcoxon_p(deltas)
            p_str = f"{p:.4f}" if p is not None else "n/a"
            lines.append(
                f"| {v} | {mean_d:+.3f} | [{lo:+.3f}, {hi:+.3f}] | {p_str} | {len(deltas)} |"
            )

    report = "\n".join(lines) + "\n"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(report)
    print(f"[SCORE] Report saved to {REPORT_PATH}")


# ══════════════════════════════════════════════════════════════════════════════
# PHASE M — MAPPING MODULE EVAL (build_mitre_table output vs gold)
# ══════════════════════════════════════════════════════════════════════════════
#
# The "mapping" half of the Knowledge Retrieval & Mapping module: the
# structured MITRE table sent to the backend (pipeline/mitre_table.py,
# answer-grounding + score-threshold noise filter). Scored against the
# same per-sample gold_attack_ids, with the raw-retrieval ID set as the
# no-filter baseline — quantifying exactly how much noise the filter
# removes and what it costs in recall.

MAPPING_REPORT_PATH = RESULTS_DIR / "mapping_eval_report.md"


def _shim_rag_result(raw: dict):
    """Rebuild a GraphRAGResult look-alike from cached mapping_raw so the
    REAL production build_mitre_table runs offline — no logic duplication."""
    from types import SimpleNamespace

    vector_results = [SimpleNamespace(**v) for v in raw.get("vector", [])]
    graph_results = []
    for nodes in raw.get("graph_nodes", []):
        ns = [SimpleNamespace(**n) for n in nodes]
        graph_results.append(
            SimpleNamespace(center_node=ns[0] if ns else None,
                            neighbors=ns[1:], edges=[])
        )
    edges = [
        SimpleNamespace(edge_label="IN_TACTIC", **e)
        for e in raw.get("in_tactic_edges", [])
    ]
    if graph_results:
        graph_results[0].edges = edges
    elif edges:
        graph_results.append(
            SimpleNamespace(center_node=None, neighbors=[], edges=edges)
        )
    return SimpleNamespace(vector_results=vector_results, graph_results=graph_results)


def _is_technique_label(label: str) -> bool:
    return label in ("Technique", "Subtechnique")


def _technique_ids_from_rows(rows) -> set[str]:
    return {
        r.technique_id.upper() for r in rows
        if r.technique_id and _is_technique_label(r.entity_type)
    }


def _raw_retrieval_technique_ids(raw: dict) -> set[str]:
    """The no-filter baseline: every technique ID retrieval dragged in."""
    ids: set[str] = set()
    for v in raw.get("vector", []):
        md = v.get("metadata", {})
        if _is_technique_label(md.get("node_label", "")) and md.get("attack_id"):
            ids.add(md["attack_id"].upper())
    for nodes in raw.get("graph_nodes", []):
        for n in nodes:
            if _is_technique_label(n.get("label", "")) and n.get("attack_id"):
                ids.add(n["attack_id"].upper())
    return ids


def phase_score_mapping(dataset_path: Path, thresholds: list[float]) -> None:
    from ..config import MITRE_TABLE_SCORE_THRESHOLD
    from ..pipeline.mitre_table import build_mitre_table

    samples = {s["id"]: s for s in load_samples(dataset_path)}
    with open(CONTEXTS_PATH, "r", encoding="utf-8") as f:
        contexts = {c["id"]: c for c in json.load(f)}

    rows = []
    with open(GENERATIONS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))

    skipped_no_raw = 0
    # variant -> sample_id -> scores ; raw baseline is variant-independent
    mapped: dict[str, dict[str, dict]] = {}
    raw_scores: dict[str, dict] = {}

    for row in rows:
        sample = samples.get(row["sample_id"])
        ctx = contexts.get(row["sample_id"])
        if sample is None or ctx is None:
            continue
        raw = ctx.get("mapping_raw")
        if not raw:
            skipped_no_raw += 1
            continue
        gold = set(sample["gold_attack_ids"])

        if row["sample_id"] not in raw_scores:
            raw_ids = _raw_retrieval_technique_ids(raw)
            s = technique_set_score(raw_ids, gold)
            s["n_ids"] = len(raw_ids)
            raw_scores[row["sample_id"]] = s

        table = build_mitre_table(_shim_rag_result(raw), row["answer"])
        pred = _technique_ids_from_rows(table)
        s = technique_set_score(pred, gold)
        s["n_ids"] = len(pred)
        mapped.setdefault(row["variant"], {})[row["sample_id"]] = s

    if not mapped:
        print("[MAP] Nothing to score — contexts lack mapping_raw "
              "(re-run --phase retrieve with the current harness)")
        return

    def _mean(dicts: list[dict], key: str) -> float:
        vals = [d[key] for d in dicts]
        return sum(vals) / len(vals) if vals else 0.0

    variants = [v for v in VARIANTS if v in mapped]
    lines = [
        "# Mapping Module Evaluation — build_mitre_table vs gold",
        "",
        f"Config threshold: {MITRE_TABLE_SCORE_THRESHOLD}  |  "
        f"Samples: {len(raw_scores)}",
        "",
        "| Source | precision | recall | F1 | avg IDs/sample |",
        "|--------|-----------|--------|----|----------------|",
    ]
    raw_list = list(raw_scores.values())
    lines.append(
        f"| raw retrieval (no filter) | {_mean(raw_list, 'precision'):.3f} "
        f"| {_mean(raw_list, 'recall'):.3f} | {_mean(raw_list, 'f1'):.3f} "
        f"| {_mean(raw_list, 'n_ids'):.1f} |"
    )
    for v in variants:
        vl = list(mapped[v].values())
        lines.append(
            f"| mapped table (answer {v}) | {_mean(vl, 'precision'):.3f} "
            f"| {_mean(vl, 'recall'):.3f} | {_mean(vl, 'f1'):.3f} "
            f"| {_mean(vl, 'n_ids'):.1f} |"
        )

    # ── Threshold sweep on baseline-A answers ──────────────────────────────
    a_rows = {r["sample_id"]: r for r in rows if r["variant"] == "A"}
    if a_rows and thresholds:
        lines += ["", "## Threshold sweep (variant A answers)", "",
                  "| threshold | precision | recall | F1 | avg IDs |",
                  "|-----------|-----------|--------|----|---------|"]
        for t in thresholds:
            per = []
            for sid, row in a_rows.items():
                ctx = contexts.get(sid)
                sample = samples.get(sid)
                if not ctx or not ctx.get("mapping_raw") or not sample:
                    continue
                table = build_mitre_table(
                    _shim_rag_result(ctx["mapping_raw"]), row["answer"],
                    score_threshold=t,
                )
                pred = _technique_ids_from_rows(table)
                s = technique_set_score(pred, set(sample["gold_attack_ids"]))
                s["n_ids"] = len(pred)
                per.append(s)
            marker = " ←config" if abs(t - MITRE_TABLE_SCORE_THRESHOLD) < 1e-9 else ""
            lines.append(
                f"| {t:.2f}{marker} | {_mean(per, 'precision'):.3f} "
                f"| {_mean(per, 'recall'):.3f} | {_mean(per, 'f1'):.3f} "
                f"| {_mean(per, 'n_ids'):.1f} |"
            )

    if skipped_no_raw:
        lines += ["", f"_{skipped_no_raw} generation rows skipped (no mapping_raw in cache)_"]

    report = "\n".join(lines) + "\n"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    MAPPING_REPORT_PATH.write_text(report, encoding="utf-8")
    print(report)
    print(f"[MAP] Report saved to {MAPPING_REPORT_PATH}")


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════


def main() -> None:
    from ..config import LLM_MODEL

    parser = argparse.ArgumentParser(description="Cross-lingual generation benchmark")
    parser.add_argument("--phase",
                        choices=["retrieve", "generate", "score",
                                 "score-mapping", "all"],
                        required=True)
    parser.add_argument("--thresholds", type=str,
                        default="0.0,0.3,0.4,0.5,0.55,0.6,0.7",
                        help="Threshold sweep values for score-mapping")
    parser.add_argument("--dataset", type=str, default=str(DEFAULT_DATASET))
    parser.add_argument("--max-samples", type=int, default=0)
    parser.add_argument("--variants", type=str, default=",".join(VARIANTS))
    parser.add_argument("--reasoning-model", type=str, default=LLM_MODEL,
                        help="Model for reasoning + default translation stage")
    parser.add_argument("--cheap-model", type=str, default="claude-haiku-4-5",
                        help="Cheap translation model for variant D")
    parser.add_argument("--local", action="store_true",
                        help="Use local Ollama for the query-translation step "
                             "of the retrieve phase")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    variants = [v.strip().upper() for v in args.variants.split(",") if v.strip()]

    if args.phase in ("retrieve", "all"):
        samples = load_samples(dataset_path, args.max_samples)
        print(f"[BENCH] {len(samples)} Thai incident samples loaded")
        phase_retrieve(samples, use_local=args.local)
    if args.phase in ("generate", "all"):
        phase_generate(variants, args.reasoning_model, args.cheap_model,
                       args.max_samples)
    if args.phase in ("score", "all"):
        phase_score(dataset_path)
    if args.phase in ("score-mapping", "all"):
        thresholds = [float(t) for t in args.thresholds.split(",") if t.strip()]
        phase_score_mapping(dataset_path, thresholds)


if __name__ == "__main__":
    main()
