"""
Build Deprecated/Revoked ATT&CK ID Blocklist
==============================================
The Neo4j graph does not store `revoked` / `x_mitre_deprecated` flags
(ingestion drops them), so deprecated techniques like T1064 (Scripting)
look identical to live ones and leak into sampled kill-chains. This
script derives a blocklist from the newest local STIX bundle of each
domain and writes it to evaluation/data/deprecated_attack_ids.json for
make_incident_dataset.py to filter against.

Usage:
    cd rag_service/app
    python -m RAG.GraphRAG.evaluation.build_deprecated_blocklist
"""

from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

_REPO_ROOT = Path(__file__).resolve().parents[5]
STIX_ROOT = _REPO_ROOT / "Mitre_ATT&CK Doc"
OUTPUT_PATH = Path(__file__).resolve().parent / "data" / "deprecated_attack_ids.json"

_VERSION_RE = re.compile(r"-(\d+)\.(\d+)\.json$")


def latest_bundle(domain_dir: Path) -> Path | None:
    """Newest versioned bundle in a domain folder (e.g. enterprise-attack-17.0.json)."""
    best: tuple[int, int] | None = None
    best_path: Path | None = None
    for p in domain_dir.glob("*.json"):
        m = _VERSION_RE.search(p.name)
        if not m:
            continue
        version = (int(m.group(1)), int(m.group(2)))
        if best is None or version > best:
            best, best_path = version, p
    return best_path


def attack_id_of(obj: dict) -> str | None:
    for ref in obj.get("external_references", []):
        if ref.get("source_name", "").startswith("mitre") and ref.get("external_id"):
            return ref["external_id"]
    return None


def main() -> None:
    deprecated: dict[str, str] = {}  # attack_id -> reason
    bundles_used: list[str] = []

    for domain_dir in sorted(STIX_ROOT.iterdir()):
        if not domain_dir.is_dir():
            continue
        bundle_path = latest_bundle(domain_dir)
        if bundle_path is None:
            continue
        bundles_used.append(bundle_path.name)

        with open(bundle_path, "r", encoding="utf-8") as f:
            bundle = json.load(f)

        for obj in bundle.get("objects", []):
            if obj.get("type") != "attack-pattern":
                continue
            revoked = bool(obj.get("revoked"))
            depr = bool(obj.get("x_mitre_deprecated"))
            if not (revoked or depr):
                continue
            aid = attack_id_of(obj)
            if aid:
                deprecated[aid] = "revoked" if revoked else "deprecated"

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {"source_bundles": bundles_used, "deprecated_ids": deprecated},
            f, indent=2, ensure_ascii=False,
        )

    print(f"[BLOCKLIST] Bundles: {', '.join(bundles_used)}")
    print(f"[BLOCKLIST] {len(deprecated)} deprecated/revoked ATT&CK IDs")
    print(f"[BLOCKLIST] T1064 included: {'T1064' in deprecated}")
    print(f"[BLOCKLIST] Saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
