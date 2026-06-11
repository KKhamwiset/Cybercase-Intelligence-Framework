"""
Dataset Builder — MITRE ATT&CK STIX → SFT instruction pairs
===========================================================
Reuses the existing ``StixParser`` (ingestion/stix_parser.py) to turn the MITRE
ATT&CK STIX bundles into chat-format training examples for fine-tuning the local
generation model into a MITRE specialist.

Generates two flavours of examples:
  • closed-book  — bake ATT&CK knowledge into the weights (Q → A)
  • grounded     — context + Q → A, mirroring the RAG pipeline's inference shape

Entities that appear in the evaluation datasets are HELD OUT (never trained on)
so the A/B comparison stays honest.

Run (from the finetune/ directory or anywhere):
    python data/build_dataset.py
    python data/build_dataset.py --max-per-category 600 --grounded-ratio 0.3
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

# ── make ``ft_config``, ``templates`` and ``GraphRAG.*`` importable ──────────
sys.path.insert(0, str(Path(__file__).resolve().parent))      # data/  (templates)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # finetune/ (ft_config)
import ft_config as C  # noqa: E402

C.add_rag_to_path()
from GraphRAG.ingestion.stix_parser import StixParser  # noqa: E402

import templates as T  # noqa: E402  (data/templates.py)

TECH_LABELS = {"Technique", "Subtechnique"}


# ──────────────────────────────────────────────────────────────────────────────
# STIX loading
# ──────────────────────────────────────────────────────────────────────────────
def _latest_bundle(folder: Path) -> Path | None:
    """Return the newest versioned STIX json in a folder (e.g. *-19.0.json)."""
    files = list(folder.glob("*.json"))
    if not files:
        return None

    def version_key(p: Path):
        m = re.search(r"(\d+)\.(\d+)\.json$", p.name)
        return (int(m.group(1)), int(m.group(2))) if m else (0, 0)

    return max(files, key=version_key)


def load_parser(domains: list[str], all_versions: bool) -> StixParser:
    parser = StixParser()
    for domain in domains:
        folder = C.STIX_DOMAIN_DIRS.get(domain)
        if not folder or not folder.is_dir():
            print(f"[WARN] STIX folder missing for '{domain}': {folder}")
            continue
        if all_versions:
            parser.parse_folder(folder, domain=domain)
        else:
            bundle = _latest_bundle(folder)
            if bundle:
                print(f"[PARSE] {domain}: latest bundle -> {bundle.name}")
                parser.parse_file(bundle, domain=domain)

    # Deduplicate (mirrors parse_all_domains)
    parser.entities = list({e.stix_id: e for e in parser.entities}.values())
    parser.relationships = list({r.stix_id: r for r in parser.relationships}.values())
    print(f"\n[PARSE] Total: {len(parser.entities)} entities, "
          f"{len(parser.relationships)} relationships")
    return parser


# ──────────────────────────────────────────────────────────────────────────────
# Held-out entities (eval leakage guard)
# ──────────────────────────────────────────────────────────────────────────────
def load_heldout_ids() -> set[str]:
    held: set[str] = set()
    for path in C.HELDOUT_EVAL_FILES:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[WARN] could not read {path.name}: {e}")
            continue
        for row in data:
            for sid in row.get("relevant_stix_ids", []):
                held.add(sid)
    print(f"[HOLDOUT] {len(held)} eval stix_ids held out from training")
    return held


# ──────────────────────────────────────────────────────────────────────────────
# Relationship indices
# ──────────────────────────────────────────────────────────────────────────────
def build_indices(parser: StixParser):
    by_id = {e.stix_id: e for e in parser.entities}

    idx = {
        "tech_mitigations": defaultdict(list),   # tech_id -> [Mitigation]
        "tech_groups": defaultdict(list),        # tech_id -> [Group]
        "tech_components": defaultdict(list),     # tech_id -> [component name]
        "tactic_techs": defaultdict(list),        # tactic_id -> [Technique]
        "group_techs": defaultdict(list),         # group_id -> [Technique]
        "group_software": defaultdict(list),      # group_id -> [Software]
        "software_techs": defaultdict(list),      # sw_id -> [Technique]
        "campaign_groups": defaultdict(list),     # campaign_id -> [Group]
    }

    def label(stix_id):
        e = by_id.get(stix_id)
        return e.node_label if e else None

    for r in parser.relationships:
        s, t = r.source_ref, r.target_ref
        sl, tl = label(s), label(t)
        se, te = by_id.get(s), by_id.get(t)
        if not se or not te:
            continue

        if r.edge_label == "MITIGATES" and sl == "Mitigation" and tl in TECH_LABELS:
            idx["tech_mitigations"][t].append(se)
        elif r.edge_label == "DETECTS" and sl == "DataComponent" and tl in TECH_LABELS:
            idx["tech_components"][t].append(se.name)
        elif r.edge_label == "IN_TACTIC" and sl in TECH_LABELS and tl == "Tactic":
            idx["tactic_techs"][t].append(se)
        elif r.edge_label == "USES":
            if sl == "Group" and tl in TECH_LABELS:
                idx["group_techs"][s].append(te)
                idx["tech_groups"][t].append(se)
            elif sl == "Group" and tl == "Software":
                idx["group_software"][s].append(te)
            elif sl == "Software" and tl in TECH_LABELS:
                idx["software_techs"][s].append(te)
        elif r.edge_label == "ATTRIBUTED_TO" and sl == "Campaign" and tl == "Group":
            idx["campaign_groups"][s].append(te)

    return by_id, idx


# ──────────────────────────────────────────────────────────────────────────────
# Example assembly
# ──────────────────────────────────────────────────────────────────────────────
def _record(system, user, assistant, category, subject_id, style, lang="en"):
    return {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ],
        "category": category,
        "subject_id": subject_id,
        "style": style,
        "language": lang,
    }


def generate_examples(parser, by_id, idx, held, rng, grounded_ratio, holdout=False):
    out = []
    SP = C.SPECIALIST_SYSTEM_PROMPT
    GP = C.GROUNDED_SYSTEM_PROMPT

    def ok(stix_id):
        # With holdout disabled (default) we train on the full KB so the model
        # becomes a real MITRE specialist. The eval datasets enumerate huge id
        # lists (e.g. all software a group uses), so id-level holdout would wipe
        # out entire entity classes — opt in with --holdout ids only when you
        # specifically want a leak-reduced generalization test.
        return True if not holdout else (stix_id not in held)

    techniques = [e for e in parser.entities if e.node_label in TECH_LABELS]
    groups = [e for e in parser.entities if e.node_label == "Group"]
    software = [e for e in parser.entities if e.node_label == "Software"]
    tactics = [e for e in parser.entities if e.node_label == "Tactic"]
    campaigns = [e for e in parser.entities if e.node_label == "Campaign"]
    tac_by_short = {getattr(t, "shortname", ""): t for t in tactics}

    # ── TECHNIQUES ────────────────────────────────────────────────────────────
    for tech in techniques:
        if not tech.attack_id or not ok(tech.stix_id):
            continue
        desc = T.clean_text(tech.description, C.MAX_DESC_CHARS)
        if not desc:
            continue

        # Precompute relationships (shared by single-fact + compound templates)
        mit_tuples = [
            (m.name, m.attack_id, T.clean_text(m.description, C.MAX_MIT_DESC_CHARS))
            for m in idx["tech_mitigations"].get(tech.stix_id, []) if m.attack_id
        ]
        gt = [(g.name, g.attack_id)
              for g in idx["tech_groups"].get(tech.stix_id, []) if g.attack_id]
        tac_tuples = [
            (tac_by_short[s].name, tac_by_short[s].attack_id)
            for s in getattr(tech, "tactics", [])
            if s in tac_by_short and tac_by_short[s].attack_id
        ]

        # technique_lookup (closed-book)
        q, a = T.technique_lookup(tech.name, tech.attack_id, desc, rng)
        out.append(_record(SP, q, a, "technique_lookup", tech.stix_id, "closed"))

        # grounded variant (sampled)
        if rng.random() < grounded_ratio:
            ctx = T.build_entity_context("Entity", tech.node_label, tech.name,
                                         tech.attack_id, desc)
            gq = f"What is {tech.name} ({tech.attack_id}) and what does it involve?"
            out.append(_record(GP, T.grounded_user_prompt(ctx, gq), a,
                               "technique_lookup", tech.stix_id, "grounded"))

        # mitigation_lookup — pass the FULL technique description so the answer
        # matches the richer reference-answer style (more facts → better recall).
        if mit_tuples:
            q, a = T.mitigation_lookup(tech.name, tech.attack_id, desc, mit_tuples, rng)
            out.append(_record(SP, q, a, "mitigation_lookup", tech.stix_id, "closed"))

        # technique_groups
        if gt:
            q, a = T.technique_groups(tech.name, tech.attack_id, gt, rng)
            out.append(_record(SP, q, a, "technique_groups", tech.stix_id, "closed"))

        # technique_detection
        comps = sorted(set(idx["tech_components"].get(tech.stix_id, [])))
        if comps:
            q, a = T.technique_detection(tech.name, tech.attack_id, comps, rng)
            out.append(_record(SP, q, a, "technique_detection", tech.stix_id, "closed"))

        # technique_profile (COMPOUND — desc + tactic(s) + mitigations + groups in
        # one complete answer; teaches the model NOT to stop after the lookup part)
        if mit_tuples or gt:
            q, a = T.technique_profile(tech.name, tech.attack_id, desc,
                                       mit_tuples, gt, tac_tuples, rng)
            out.append(_record(SP, q, a, "technique_profile", tech.stix_id, "closed"))
            if rng.random() < grounded_ratio:
                ctx = T.build_entity_context("Entity", tech.node_label, tech.name,
                                             tech.attack_id, desc)
                out.append(_record(GP, T.grounded_user_prompt(ctx, q), a,
                                   "technique_profile", tech.stix_id, "grounded"))

    # ── TACTICS ───────────────────────────────────────────────────────────────
    for tac in tactics:
        if not tac.attack_id or not ok(tac.stix_id):
            continue
        techs = idx["tactic_techs"].get(tac.stix_id, [])
        tt = [(t.name, t.attack_id) for t in techs if t.attack_id]
        if tt:
            q, a = T.tactic_techniques(tac.name, tac.attack_id, tt, rng)
            out.append(_record(SP, q, a, "tactic_techniques", tac.stix_id, "closed"))

    # ── GROUPS ────────────────────────────────────────────────────────────────
    for grp in groups:
        if not grp.attack_id or not ok(grp.stix_id):
            continue
        techs = idx["group_techs"].get(grp.stix_id, [])
        tt = [(t.name, t.attack_id) for t in techs if t.attack_id]
        if tt:
            q, a = T.group_techniques(grp.name, grp.attack_id, tt, rng)
            out.append(_record(SP, q, a, "group_techniques", grp.stix_id, "closed"))

        sws = idx["group_software"].get(grp.stix_id, [])
        ss = [(s.name, s.attack_id) for s in sws if s.attack_id]
        if ss:
            q, a = T.group_software(grp.name, grp.attack_id, ss, rng)
            out.append(_record(SP, q, a, "group_software", grp.stix_id, "closed"))

    # ── SOFTWARE ──────────────────────────────────────────────────────────────
    for sw in software:
        if not sw.attack_id or not ok(sw.stix_id):
            continue
        sw_type = getattr(sw, "software_type", "")

        techs = idx["software_techs"].get(sw.stix_id, [])
        tt = [(t.name, t.attack_id) for t in techs if t.attack_id]
        if tt:
            q, a = T.software_techniques(sw.name, sw.attack_id, sw_type, tt, rng)
            out.append(_record(SP, q, a, "software_techniques", sw.stix_id, "closed"))

        desc = T.clean_text(sw.description, 300)
        if desc:
            q, a = T.software_type_query(sw.name, sw.attack_id, sw_type, desc, rng)
            out.append(_record(SP, q, a, "software_type_query", sw.stix_id, "closed"))

    # ── CAMPAIGNS ─────────────────────────────────────────────────────────────
    for camp in campaigns:
        if not camp.attack_id or not ok(camp.stix_id):
            continue
        grps = idx["campaign_groups"].get(camp.stix_id, [])
        gg = [(g.name, g.attack_id) for g in grps if g.attack_id]
        if gg:
            q, a = T.campaign_attribution(camp.name, camp.attack_id, gg, rng)
            out.append(_record(SP, q, a, "campaign_attribution", camp.stix_id, "closed"))

    return out


# ──────────────────────────────────────────────────────────────────────────────
# Post-processing
# ──────────────────────────────────────────────────────────────────────────────
def dedup(records):
    seen, kept = set(), []
    for r in records:
        key = r["messages"][1]["content"].strip().lower()
        if key in seen:
            continue
        seen.add(key)
        kept.append(r)
    return kept


def cap_per_category(records, max_per_cat, rng):
    if not max_per_cat:
        return records
    buckets = defaultdict(list)
    for r in records:
        buckets[r["category"]].append(r)
    out = []
    for cat, rows in buckets.items():
        rng.shuffle(rows)
        out.extend(rows[:max_per_cat])
    return out


def write_jsonl(path: Path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            # Training only needs "messages"; keep metadata fields too (harmless).
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser(description="Build MITRE SFT dataset from STIX")
    ap.add_argument("--domains", nargs="+", default=C.DOMAINS_TO_BUILD)
    ap.add_argument("--all-versions", action="store_true",
                    help="parse every STIX version (slow) instead of latest only")
    ap.add_argument("--grounded-ratio", type=float, default=0.3,
                    help="fraction of techniques that also get a grounded example")
    ap.add_argument("--max-per-category", type=int, default=0,
                    help="cap examples per category (0 = no cap; ~600 balances it)")
    ap.add_argument("--holdout", choices=["none", "ids"], default="none",
                    help="'ids' excludes every entity referenced in eval_dataset.json "
                         "(leak-reduced test, but much smaller); 'none' trains full KB")
    ap.add_argument("--val-split", type=float, default=C.VAL_SPLIT)
    ap.add_argument("--seed", type=int, default=C.RANDOM_SEED)
    args = ap.parse_args()

    rng = random.Random(args.seed)

    parser = load_parser(args.domains, args.all_versions)
    held = load_heldout_ids() if args.holdout == "ids" else set()
    by_id, idx = build_indices(parser)

    records = generate_examples(parser, by_id, idx, held, rng, args.grounded_ratio,
                                holdout=(args.holdout == "ids"))
    records = dedup(records)
    records = cap_per_category(records, args.max_per_category, rng)
    rng.shuffle(records)

    n_val = int(len(records) * args.val_split)
    val, train = records[:n_val], records[n_val:]

    write_jsonl(C.TRAIN_FILE, train)
    write_jsonl(C.VAL_FILE, val)

    # ── stats ────────────────────────────────────────────────────────────────
    cat_counts, style_counts = defaultdict(int), defaultdict(int)
    for r in records:
        cat_counts[r["category"]] += 1
        style_counts[r["style"]] += 1
    stats = {
        "total": len(records),
        "train": len(train),
        "val": len(val),
        "holdout_mode": args.holdout,
        "held_out_ids": len(held),
        "domains": args.domains,
        "by_category": dict(sorted(cat_counts.items())),
        "by_style": dict(style_counts),
    }
    C.STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    C.STATS_FILE.write_text(json.dumps(stats, indent=2, ensure_ascii=False),
                            encoding="utf-8")

    print("\n" + "=" * 60)
    print("  DATASET BUILT")
    print("=" * 60)
    print(f"  train : {len(train):>6}  -> {C.TRAIN_FILE}")
    print(f"  val   : {len(val):>6}  -> {C.VAL_FILE}")
    print(f"  total : {len(records):>6}")
    print("  by category:")
    for cat, n in sorted(cat_counts.items()):
        print(f"    {cat:<22} {n:>6}")
    print(f"  by style: {dict(style_counts)}")
    print(f"\n  stats -> {C.STATS_FILE}")


if __name__ == "__main__":
    main()
