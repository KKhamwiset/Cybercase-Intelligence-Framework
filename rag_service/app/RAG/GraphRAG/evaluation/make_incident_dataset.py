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

# Observable phases only: reconnaissance / resource-development happen
# outside the victim's visibility, so they cannot appear as evidence in a
# case-file narrative (a "described" cue for them would be unfalsifiable).
KILL_CHAIN_ORDER = [
    "initial-access", "execution",
    "persistence", "privilege-escalation", "defense-evasion",
    "credential-access", "discovery", "lateral-movement", "collection",
    "command-and-control", "exfiltration", "impact",
]

CHAIN_CYPHER = """
MATCH (g:Group)-[:USES]->(t:Technique)-[:IN_TACTIC]->(tac:Tactic)
WHERE t.attack_id IS NOT NULL
  AND (t.is_subtechnique IS NULL OR t.is_subtechnique = false)
WITH g, coalesce(tac.shortname, tac.name) AS tactic,
     collect(DISTINCT {stix_id: t.stix_id, name: t.name,
                       attack_id: t.attack_id}) AS techniques
WITH g, collect({tactic: tactic, techniques: techniques}) AS by_tactic
WHERE size(by_tactic) >= $min_tactics
RETURN g.name AS group_name, g.attack_id AS group_id, by_tactic
ORDER BY size(by_tactic) DESC
LIMIT $limit_groups
"""


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
) -> list[dict]:
    """Sample up to num_chains kill-chains, cycling through groups."""
    rows = neo4j.run_query(CHAIN_CYPHER, {"min_tactics": min_steps, "limit_groups": 60})
    print(f"[CHAIN] {len(rows)} groups with >= {min_steps} tactics")

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
                bt["tactic"]: bt["techniques"]
                for bt in row["by_tactic"]
                if bt["tactic"] in KILL_CHAIN_ORDER
            }
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

            key = (row["group_id"], tuple(s["attack_id"] for s in steps))
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
                "group_name": row["group_name"],
                "group_id": row["group_id"],
                "steps": steps,
            })

    return chains


# ══════════════════════════════════════════════════════════════════════════════
# 2. NARRATIVE DRAFTING (Claude)
# ══════════════════════════════════════════════════════════════════════════════

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
        lines.append(f"## {e['id']}  (source group: {e['group_name']} {e['group_id']})")
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
    args = parser.parse_args()

    rng = random.Random(args.seed)
    neo4j = Neo4jGroundTruthBuilder()

    try:
        chains = sample_kill_chains(neo4j, args.num, rng)
    finally:
        neo4j.close()
    print(f"[CHAIN] Sampled {len(chains)} chains")

    if args.dry_run:
        for c in chains:
            steps = " -> ".join(
                f"{s['attack_id']}({s['cue_type'][:4]})" for s in c["steps"]
            )
            print(f"  {c['group_name']:<20} {steps}")
        return

    from langchain_anthropic import ChatAnthropic
    llm = ChatAnthropic(  # type: ignore[call-arg]
        model=LLM_MODEL, api_key=ANTHROPIC_API_KEY,
        temperature=0.7, max_tokens=2000,
    )
    print(f"[DRAFT] Drafting with {LLM_MODEL}")

    entries: list[dict] = []
    failed = 0
    for i, chain in enumerate(chains):
        draft = draft_narrative(llm, chain)
        if draft is None:
            failed += 1
            print(f"  [{i+1}/{len(chains)}] FAILED (JSON) — skipped")
            continue
        sample, flags = build_sample(i, chain, draft)
        entries.append({
            "id": f"inc_auto_{i+1:03d}",
            "group_name": chain["group_name"],
            "group_id": chain["group_id"],
            "chain_steps": chain["steps"],
            "flags": flags,
            "sample": sample.to_dict(),
        })
        flag_note = f"  FLAGS: {len(flags)}" if flags else ""
        print(f"  [{i+1}/{len(chains)}] {chain['group_name']}: "
              f"{len(chain['steps'])} steps{flag_note}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    draft_path = OUT_DIR / "incident_draft.json"
    with open(draft_path, "w", encoding="utf-8") as f:
        json.dump(
            [{"id": e["id"], **e["sample"]} for e in entries],
            f, indent=2, ensure_ascii=False,
        )
    review_path = OUT_DIR / "incident_draft_review.md"
    write_review_md(review_path, entries)

    flagged = sum(1 for e in entries if e["flags"])
    print(f"\n[DRAFT] {len(entries)} drafted, {failed} failed, {flagged} auto-flagged")
    print(f"[DRAFT] Samples : {draft_path}")
    print(f"[DRAFT] Review  : {review_path}")


if __name__ == "__main__":
    main()
