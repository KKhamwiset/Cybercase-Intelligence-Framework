"""
Incident Dataset Builder (semi-automated)
==========================================
Builds chronological Thai case-file incident samples for the eval dataset:

1. KILL-CHAIN SAMPLING (Neo4j) — pick techniques a single Group actually
   USES, one per tactic, ordered by kill-chain phase. Sourcing every chain
   from one real group guarantees the technique combination co-occurred
   in the wild instead of being a random grab-bag.
2. NARRATIVE DRAFTING (Claude) — draft a chronological Thai incident
   narrative in investigator case-file voice: English technical terms
   embedded for `named` cues, behaviour-only description for `described`
   cues, never any ATT&CK ID in the narrative. Plus an English parallel.
3. REVIEW OUTPUT — drafts go to incident_draft.json (GeneratedSample
   dicts) and incident_draft_review.md (human review sheet). Samples
   enter the real dataset ONLY after human review.

Usage:
    cd rag_service/app
    python -m RAG.GraphRAG.evaluation.make_incident_dataset --num 6
    python -m RAG.GraphRAG.evaluation.make_incident_dataset --num 3 --dry-run
"""

from __future__ import annotations

import argparse
import io
import json
import random
import re
import sys
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

from .generate_eval_dataset import GeneratedSample, Neo4jGroundTruthBuilder
from ..config import ANTHROPIC_API_KEY, LLM_MODEL

OUT_DIR = Path(__file__).resolve().parent / "data"
BLOCKLIST_PATH = OUT_DIR / "deprecated_attack_ids.json"


def load_deprecated_blocklist() -> set[str]:
    """Deprecated/revoked ATT&CK IDs to exclude from chains.

    The graph stores no revoked/x_mitre_deprecated flags (ingestion drops
    them), so deprecated techniques like T1064 look live in Neo4j; the
    blocklist is derived from local STIX bundles by
    build_deprecated_blocklist.py.
    """
    try:
        with open(BLOCKLIST_PATH, "r", encoding="utf-8") as f:
            return set(json.load(f)["deprecated_ids"])
    except FileNotFoundError:
        print("[CHAIN] WARNING: no deprecated blocklist — "
              "run build_deprecated_blocklist first; chains may include "
              "deprecated techniques")
        return set()

# Observable phases only: reconnaissance / resource-development happen
# outside the victim's visibility, so they cannot appear as evidence in a
# case-file narrative (a "described" cue for them would be unfalsifiable).
KILL_CHAIN_ORDER = [
    "initial-access", "execution",
    "persistence", "privilege-escalation", "defense-evasion",
    "credential-access", "discovery", "lateral-movement", "collection",
    "command-and-control", "exfiltration", "impact",
]

# Group source: techniques a threat GROUP has ever used (broad).
CHAIN_CYPHER = """
MATCH (g:Group)-[:USES]->(t:Technique)-[:IN_TACTIC]->(tac:Tactic)
WHERE t.attack_id IS NOT NULL
  AND (t.is_subtechnique IS NULL OR t.is_subtechnique = false)
WITH g, coalesce(tac.shortname, tac.name) AS tactic,
     collect(DISTINCT {stix_id: t.stix_id, name: t.name,
                       attack_id: t.attack_id}) AS techniques
WITH g, collect({tactic: tactic, techniques: techniques}) AS by_tactic
WHERE size(by_tactic) >= $min_tactics
RETURN g.name AS source_name, g.attack_id AS source_id, by_tactic
ORDER BY size(by_tactic) DESC
LIMIT $limit_sources
"""

# Campaign source: techniques OBSERVED IN ONE REAL documented intrusion
# (e.g. C0024 SolarWinds, C0022 Operation Dream Job). More realistic
# co-occurrence than a group's full arsenal, and carries real provenance.
CAMPAIGN_CYPHER = """
MATCH (c:Campaign)-[:USES]->(t:Technique)-[:IN_TACTIC]->(tac:Tactic)
WHERE t.attack_id IS NOT NULL
  AND (t.is_subtechnique IS NULL OR t.is_subtechnique = false)
  AND coalesce(t.domain, 'enterprise') = 'enterprise'
WITH c, coalesce(tac.shortname, tac.name) AS tactic,
     collect(DISTINCT {stix_id: t.stix_id, name: t.name,
                       attack_id: t.attack_id}) AS techniques
WITH c, collect({tactic: tactic, techniques: techniques}) AS by_tactic
WHERE size(by_tactic) >= $min_tactics
RETURN c.name AS source_name, c.attack_id AS source_id, by_tactic
ORDER BY size(by_tactic) DESC
LIMIT $limit_sources
"""

_SOURCE_CYPHER = {"group": CHAIN_CYPHER, "campaign": CAMPAIGN_CYPHER}


# ══════════════════════════════════════════════════════════════════════════════
# 1. KILL-CHAIN SAMPLING
# ══════════════════════════════════════════════════════════════════════════════


def _tactic_order(tactic: str) -> int:
    try:
        return KILL_CHAIN_ORDER.index(tactic)
    except ValueError:
        return len(KILL_CHAIN_ORDER)


def sample_kill_chains(
    neo4j: Neo4jGroundTruthBuilder,
    num_chains: int,
    rng: random.Random,
    min_steps: int = 3,
    max_steps: int = 6,
    blocked_ids: set[str] | None = None,
    source: str = "group",
) -> list[dict]:
    """Sample up to num_chains kill-chains from a Group or a real Campaign."""
    blocked_ids = blocked_ids or set()
    cypher = _SOURCE_CYPHER[source]
    rows = neo4j.run_query(cypher, {"min_tactics": min_steps, "limit_sources": 80})
    print(f"[CHAIN] {len(rows)} {source}s with >= {min_steps} observable tactics")

    chains: list[dict] = []
    seen: set[tuple] = set()
    round_no = 0

    while len(chains) < num_chains and round_no < 5:
        round_no += 1
        rng.shuffle(rows)
        for row in rows:
            if len(chains) >= num_chains:
                break
            by_tactic = {
                bt["tactic"]: [
                    t for t in bt["techniques"]
                    if t["attack_id"] not in blocked_ids
                ]
                for bt in row["by_tactic"]
                if bt["tactic"] in KILL_CHAIN_ORDER
            }
            by_tactic = {k: v for k, v in by_tactic.items() if v}
            if len(by_tactic) < min_steps:
                continue

            n_steps = rng.randint(min_steps, min(max_steps, len(by_tactic)))
            chosen_tactics = sorted(
                rng.sample(sorted(by_tactic), n_steps), key=_tactic_order
            )

            # One technique per tactic, no repeats within the chain (the same
            # technique can sit in several tactics, e.g. T1078).
            steps = []
            used_ids: set[str] = set()
            for tactic in chosen_tactics:
                candidates = [
                    t for t in by_tactic[tactic] if t["attack_id"] not in used_ids
                ]
                if not candidates:
                    continue
                tech = rng.choice(candidates)
                used_ids.add(tech["attack_id"])
                steps.append({
                    "order": len(steps) + 1,
                    "tactic": tactic,
                    "attack_id": tech["attack_id"],
                    "name": tech["name"],
                    "stix_id": tech["stix_id"],
                })
            if len(steps) < min_steps:
                continue

            key = (row["source_id"], tuple(s["attack_id"] for s in steps))
            if key in seen:
                continue
            seen.add(key)

            # Cue-type mix: at least one described step per chain (the part
            # that tests behaviour->technique mapping), rest ~40% described.
            described_idx = rng.randrange(len(steps))
            for i, step in enumerate(steps):
                step["cue_type"] = (
                    "described" if i == described_idx or rng.random() < 0.4
                    else "named"
                )

            chains.append({
                "source": source,
                "source_name": row["source_name"],
                "source_id": row["source_id"],
                "steps": steps,
            })

    return chains


# ══════════════════════════════════════════════════════════════════════════════
# 2. NARRATIVE DRAFTING (Claude)
# ══════════════════════════════════════════════════════════════════════════════

# Style references — real Thai cybercrime case reporting used to calibrate
# the narrative voice (investigator officialese, chronological, victim
# report -> forensic findings):
#   - บช.สอท. hotel-database hack case (Pattaya), Bangkok Biz News:
#     https://www.bangkokbiznews.com/news/news-update/1231874
#   - insider "CIO Get Out" retail hack, Daily News:
#     https://www.dailynews.co.th/news/5765921/
#   - ThaiCERT / NCSA threat write-ups (Thai technical register):
#     https://www.thaicert.or.th
#   - Chronological TTP narrative structure (English exemplar):
#     https://thedfirreport.com
SYSTEM_PROMPT = """\
You draft realistic Thai cybercrime case-file summaries (สำนวนคดีไซเบอร์) \
for building an evaluation dataset. You write exactly like a Thai \
investigator: chronological Thai prose with English technical terms \
embedded naturally, factual and dry, no analysis or conclusions."""

USER_PROMPT_TEMPLATE = """\
Write one Thai incident narrative from this attack chain (chronological order):

{steps_json}

Rules:
1. Chronological Thai prose, 3-6 sentences, investigator case-file voice \
(ผู้เสียหายรายงานว่า... / จากการตรวจสอบพบว่า... / ต่อมา... / จากนั้น...). \
Invent plausible victim context (org type, system names) but keep it generic — \
no real company names.
2. For steps with "cue_type": "named" — embed the technique's common English \
term naturally in the Thai sentence (e.g. "ใช้ SQL injection", "ทำ Credential \
Dumping ด้วยเครื่องมือพิเศษ"). Use the everyday term for the technique name given.
3. For steps with "cue_type": "described" — describe only the observable \
behaviour in Thai; do NOT write the technique's name (or a near-verbatim \
English paraphrase of it) anywhere in the sentence. Describe what an \
investigator would see in logs or on the machine instead.
4. NEVER write any MITRE ATT&CK ID (T####, TA####) anywhere in the narratives.
5. Do not mention the threat group name.
6. Every step must be traceable to a contiguous phrase in the Thai narrative.

Style example (for voice only):
"ผู้โจมตีใช้ SQL injection เข้าสู่ระบบ และทำการ Privilege escalation ผ่าน \
Credential dumping จากนั้นทำการลบข้อมูลทิ้งทั้งหมด"

Openers/connectors drawn from real Thai police case reporting — vary them \
naturally, do not use all in one narrative:
- "ผู้เสียหายแจ้งความว่า..." / "ได้รับแจ้งเบาะแสจากผู้เสียหายว่า..."
- "ถูกเข้าถึงข้อมูลโดยไม่ได้รับอนุญาต"
- "จากการตรวจสอบพยานหลักฐานดิจิทัลพบว่า..." / "จากการตรวจสอบ log พบว่า..."
- "ต่อมา..." / "จากนั้น..." / "สุดท้าย..."
- State date/organization type formally (e.g. "เมื่อวันที่ 15 มีนาคม 2569 \
บริษัทเอกชนแห่งหนึ่งในจังหวัดชลบุรี...")

Return STRICT JSON only (no markdown fences):
{{
  "narrative_th": "...",
  "narrative_en": "English parallel of the same narrative",
  "cues": [
    {{"order": 1, "cue": "exact contiguous substring copied from narrative_th evidencing step 1"}},
    ...one entry per step...
  ]
}}"""


def _parse_json_reply(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    return json.loads(text)


def draft_narrative(llm, chain: dict) -> dict | None:
    """One LLM call -> {narrative_th, narrative_en, cues}. None on failure."""
    steps_for_prompt = [
        {
            "order": s["order"],
            "technique_name": s["name"],
            "tactic": s["tactic"],
            "cue_type": s["cue_type"],
        }
        for s in chain["steps"]
    ]
    prompt = USER_PROMPT_TEMPLATE.format(
        steps_json=json.dumps(steps_for_prompt, indent=2, ensure_ascii=False)
    )

    last_err = ""
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            reply = llm.invoke([
                ("system", SYSTEM_PROMPT),
                ("user", prompt + last_err),
            ])
            content = reply.content
            if isinstance(content, list):
                # langchain may return content blocks instead of a plain str
                content = "".join(
                    b.get("text", "") if isinstance(b, dict) else str(b)
                    for b in content
                )
            data = _parse_json_reply(content)
            if not data.get("narrative_th") or len(data.get("cues", [])) != len(chain["steps"]):
                raise ValueError("missing narrative_th or wrong cue count")
            return data
        except Exception as e:  # noqa: BLE001 — retry once with the error fed back
            last_exc = e
            last_err = f"\n\nYour previous reply failed ({e}). Return STRICT JSON only."
    print(f"    error: {type(last_exc).__name__}: {last_exc}")
    return None


# ══════════════════════════════════════════════════════════════════════════════
# 3. SAMPLE ASSEMBLY + REVIEW OUTPUT
# ══════════════════════════════════════════════════════════════════════════════


def _entry_from_stored(sid: str, stored: dict, id_to_name: dict[str, str]) -> dict:
    """Rebuild a review entry from a previously drafted sample (--resume).

    Deliberately independent of chain re-sampling: everything is derived
    from the stored sample itself, so resume never re-spends LLM credits
    on chains that already have drafts.
    """
    narrative = stored.get("query", "")
    flags: list[str] = []
    chain_steps: list[dict] = []
    for step in stored.get("attack_steps", []):
        aid = (step.get("gold_attack_ids") or [""])[0]
        name = id_to_name.get(aid, "?")
        cue = step.get("cue", "")
        if not cue or cue not in narrative:
            flags.append(f"step {step.get('order')}: cue not found verbatim in narrative")
        if step.get("cue_type") == "described" and name != "?" and name.lower() in cue.lower():
            flags.append(f"step {step.get('order')}: described cue names the technique ({name})")
        chain_steps.append({"attack_id": aid, "name": name})
    return {
        "id": sid,
        "source_name": stored.get("source_prov", "(previous run)"),
        "source_id": "",
        "chain_steps": chain_steps,
        "flags": flags,
        "sample": {k: v for k, v in stored.items() if k not in ("id", "source_prov")},
    }


def build_sample(idx: int, chain: dict, draft: dict) -> tuple[GeneratedSample, list[str]]:
    """Assemble a GeneratedSample; returns (sample, review_flags)."""
    flags: list[str] = []
    narrative_th = draft["narrative_th"].strip()

    if re.search(r"(?<![A-Za-z0-9])(?:TA|T)\d{4}", narrative_th):
        flags.append("ATT&CK ID leaked into narrative")

    cue_by_order = {c["order"]: (c.get("cue") or "").strip() for c in draft["cues"]}

    attack_steps = []
    for s in chain["steps"]:
        cue = cue_by_order.get(s["order"], "")
        if not cue or cue not in narrative_th:
            flags.append(f"step {s['order']}: cue not found verbatim in narrative")
        if s["cue_type"] == "described" and s["name"].lower() in cue.lower():
            flags.append(
                f"step {s['order']}: described cue names the technique "
                f"({s['name']})"
            )
        attack_steps.append({
            "order": s["order"],
            "cue": cue,
            "cue_type": s["cue_type"],
            "gold_attack_ids": [s["attack_id"]],
            "gold_stix_ids": [s["stix_id"]],
        })

    gold_ids = list(dict.fromkeys(s["attack_id"] for s in chain["steps"]))
    stix_ids = list(dict.fromkeys(s["stix_id"] for s in chain["steps"]))

    sample = GeneratedSample(
        query=narrative_th,
        relevant_stix_ids=stix_ids,
        language="th",
        category="incident_analysis",
        query_en=(draft.get("narrative_en") or "").strip(),
        gold_attack_ids=gold_ids,
        attack_steps=attack_steps,
    )
    return sample, flags


def write_review_md(path: Path, entries: list[dict]) -> None:
    lines = [
        "# Incident Draft Review Sheet",
        "",
        "ตรวจแต่ละข้อ: (1) สำนวนเหมือนสำนวนคดีจริงไหม (2) cue ตรงกับ technique จริงไหม",
        "(3) step แบบ described ไม่เผลอบอกชื่อเทคนิค — แก้ไขในไฟล์ incident_draft.json",
        "แล้วลบข้อที่ใช้ไม่ได้ทิ้ง",
        "",
    ]
    for e in entries:
        s = e["sample"]
        lines.append(f"## {e['id']}  (source: {e['source_name']} {e['source_id']})")
        if e["flags"]:
            lines.append("")
            lines.append("**AUTO-FLAGS: " + "; ".join(e["flags"]) + "**")
        lines.append("")
        lines.append(f"> {s['query']}")
        lines.append("")
        lines.append(f"*EN:* {s['query_en']}")
        lines.append("")
        lines.append("| # | cue_type | technique | cue |")
        lines.append("|---|----------|-----------|-----|")
        for step, chain_step in zip(s["attack_steps"], e["chain_steps"]):
            lines.append(
                f"| {step['order']} | {step['cue_type']} "
                f"| {chain_step['attack_id']} {chain_step['name']} "
                f"| {step['cue']} |"
            )
        lines.append("")
        lines.append("- [ ] ผ่าน / แก้แล้ว")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build incident eval samples")
    parser.add_argument("--num", type=int, default=6, help="Chains to draft")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dry-run", action="store_true",
                        help="Sample chains only, no LLM drafting")
    parser.add_argument("--resume", action="store_true",
                        help="Keep existing drafts in the output file; "
                             "only draft chain indices that have none")
    parser.add_argument("--source", choices=["group", "campaign"], default="group",
                        help="Seed chains from a threat Group's arsenal, or "
                             "from a real documented Campaign (grounded incident)")
    parser.add_argument("--out", type=str, default="incident_draft.json",
                        help="Output filename under data/ (use a distinct name "
                             "per source so runs don't overwrite each other)")
    parser.add_argument("--id-prefix", type=str, default="inc_auto",
                        help="Sample id prefix (use a distinct one per source "
                             "to avoid id collisions when merging datasets)")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    blocked = load_deprecated_blocklist()
    print(f"[CHAIN] Blocklist: {len(blocked)} deprecated/revoked IDs excluded")
    print(f"[CHAIN] Source: {args.source}")
    neo4j = Neo4jGroundTruthBuilder()

    try:
        chains = sample_kill_chains(
            neo4j, args.num, rng, blocked_ids=blocked, source=args.source
        )
    finally:
        neo4j.close()
    print(f"[CHAIN] Sampled {len(chains)} chains")

    if args.dry_run:
        for c in chains:
            steps = " -> ".join(
                f"{s['attack_id']}({s['cue_type'][:4]})" for s in c["steps"]
            )
            print(f"  {c['source_id'] or '-':7} {c['source_name'][:22]:24} {steps}")
        return

    draft_path = OUT_DIR / args.out

    existing: dict[str, dict] = {}
    id_to_name: dict[str, str] = {}
    if args.resume and draft_path.exists():
        with open(draft_path, "r", encoding="utf-8") as f:
            existing = {e["id"]: e for e in json.load(f)}
        try:
            with open(OUT_DIR / "attack_lookup.json", "r", encoding="utf-8") as f:
                id_to_name = {
                    aid: name for name, aid in json.load(f)["alias_map"].items()
                }
        except FileNotFoundError:
            pass
        print(f"[DRAFT] Resume: keeping {len(existing)} existing drafts")

    from langchain_anthropic import ChatAnthropic
    llm = ChatAnthropic(  # type: ignore[call-arg]
        model=LLM_MODEL, api_key=ANTHROPIC_API_KEY,
        temperature=0.7, max_tokens=2000,
    )
    print(f"[DRAFT] Drafting with {LLM_MODEL}")

    entries: list[dict] = []
    failed = 0
    for i, chain in enumerate(chains):
        sid = f"{args.id_prefix}_{i+1:03d}"
        if sid in existing:
            entries.append(_entry_from_stored(sid, existing[sid], id_to_name))
            continue
        draft = draft_narrative(llm, chain)
        if draft is None:
            failed += 1
            print(f"  [{i+1}/{len(chains)}] FAILED (JSON) — skipped")
            continue
        sample, flags = build_sample(i, chain, draft)
        entries.append({
            "id": sid,
            "source_name": chain["source_name"],
            "source_id": chain["source_id"],
            "chain_steps": chain["steps"],
            "flags": flags,
            "sample": sample.to_dict(),
        })
        flag_note = f"  FLAGS: {len(flags)}" if flags else ""
        print(f"  [{i+1}/{len(chains)}] {chain['source_id'] or ''} "
              f"{chain['source_name']}: {len(chain['steps'])} steps{flag_note}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(draft_path, "w", encoding="utf-8") as f:
        json.dump(
            [
                {
                    "id": e["id"],
                    # readable provenance: "SolarWinds Compromise (C0024, campaign)"
                    "source_prov": f"{e['source_name']}"
                    + (f" ({e['source_id']}, {args.source})" if e["source_id"]
                       else f" ({args.source})"),
                    **e["sample"],
                }
                for e in entries
            ],
            f, indent=2, ensure_ascii=False,
        )
    review_path = OUT_DIR / (Path(args.out).stem + "_review.md")
    write_review_md(review_path, entries)

    flagged = sum(1 for e in entries if e["flags"])
    print(f"\n[DRAFT] {len(entries)} drafted, {failed} failed, {flagged} auto-flagged")
    print(f"[DRAFT] Samples : {draft_path}")
    print(f"[DRAFT] Review  : {review_path}")


if __name__ == "__main__":
    main()
