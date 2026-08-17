"""Gold-first deterministic construction of the bilingual benchmark."""

import json
from pathlib import Path

from .constants import CORRUPTION_TYPES, DEFAULT_CASE_COUNT, DEFAULT_SEED, SCHEMA_VERSION
from .rendering import fact_edge, render_corruption, render_fact, render_proposition


SCENARIOS = (
    ("email_execution", "sent", "included", "stored_as", "executed"),
    ("forwarded_attachment", "forwarded", "contained", "saved_as", "opened"),
    ("received_document", "received", "included", "saved_as", "executed"),
    ("mail_endpoint_review", "sent", "contained", "stored_as", "opened"),
)


def _entity(case_id, suffix, entity_type, name):
    return {"entity_id": f"{case_id}-{suffix}", "entity_type": entity_type, "name": name}


def _relationship(case_id, number, subject, predicate, target, timestamp=None, certainty="reported", negated=False):
    return {
        "fact_id": f"{case_id}-rel-{number:03d}", "slot": f"rel-{number:03d}",
        "fact_kind": "relationship", "subject_entity_id": subject, "predicate": predicate,
        "object_entity_id": target, "timestamp": timestamp, "certainty": certainty,
        "negated": negated, "source_proposition_ids": [],
    }


def _timeline(case_id, number, event_type, actor, predicate, target, timestamp, certainty="reported"):
    return {
        "fact_id": f"{case_id}-time-{number:03d}", "slot": f"time-{number:03d}",
        "fact_kind": "timeline", "event_type": event_type, "actor_entity_id": actor,
        "relationship_predicate": predicate, "target_entity_id": target,
        "timestamp": timestamp, "certainty": certainty, "negated": False,
        "source_proposition_ids": [],
    }


def _timestamps(case_number):
    day = 1 + ((case_number - 1) % 20)
    prefix = f"2025-04-{day:02d}T"
    values = [prefix + value + "Z" for value in ("08:00", "08:30", "08:50", "09:10")]
    if case_number % 3 == 0:
        values[0] = None
    if case_number % 4 == 0:
        values[1] = None
    return values


def _gold(case_id, case_number, language, scenario):
    suffix = case_id.split("-")[-1]
    names = {
        "user-a": f"Analyst-{suffix}-A", "user-b": f"Employee-{suffix}-B",
        "account-a": f"account-{suffix}-primary", "account-b": f"account-{suffix}-secondary",
        "email": f"email-{suffix}", "attachment": f"attachment-{suffix}.zip",
        "file": f"document-{suffix}.exe", "process": f"process-{suffix}",
        "endpoint-a": f"endpoint-{suffix}-A", "endpoint-b": f"endpoint-{suffix}-B",
        "ip-a": f"192.0.2.{(case_number % 200) + 1}", "ip-b": f"198.51.100.{(case_number % 200) + 1}",
    }
    types = {
        "user-a": "user", "user-b": "user", "account-a": "account", "account-b": "account",
        "email": "email", "attachment": "attachment", "file": "file", "process": "process",
        "endpoint-a": "endpoint", "endpoint-b": "endpoint", "ip-a": "ip_address", "ip-b": "ip_address",
    }
    entities = [_entity(case_id, key, types[key], value) for key, value in names.items()]
    ids = {key: f"{case_id}-{key}" for key in names}
    _, mail_predicate, container_predicate, storage_predicate, execution_predicate = scenario
    auth_time, credential_time, login_time, endpoint_time = _timestamps(case_number)
    relationships = [
        _relationship(case_id, 1, ids["user-a"], "owns", ids["account-a"]),
        _relationship(case_id, 2, ids["account-a"], mail_predicate, ids["email"], auth_time),
        _relationship(case_id, 3, ids["email"], container_predicate, ids["attachment"]),
        _relationship(case_id, 4, ids["attachment"], storage_predicate, ids["file"]),
        _relationship(case_id, 5, ids["file"], execution_predicate, ids["process"]),
        _relationship(case_id, 6, ids["process"], "ran_on", ids["endpoint-a"], endpoint_time),
        _relationship(case_id, 7, ids["account-b"], "authenticated_on", ids["endpoint-b"], auth_time),
        _relationship(case_id, 8, ids["account-b"], "signed_in_from", ids["ip-b"], login_time, "suspected"),
        _relationship(case_id, 9, ids["user-b"], "submitted_credentials_to", ids["email"], credential_time),
        _relationship(case_id, 10, ids["endpoint-b"], "connected_to", ids["ip-a"], None, "suspected", True),
    ]
    timeline = [
        _timeline(case_id, 1, "authentication", ids["account-b"], "authenticated_on", ids["endpoint-b"], auth_time),
        _timeline(case_id, 2, "suspicious_login", ids["account-b"], "signed_in_from", ids["ip-b"], login_time, "suspected"),
        _timeline(case_id, 3, "credential_submission", ids["user-b"], "submitted_credentials_to", ids["email"], credential_time),
        _timeline(case_id, 4, "endpoint_activity", ids["process"], "ran_on", ids["endpoint-a"], endpoint_time),
    ]
    return {"entities": entities, "relationships": relationships, "timeline": timeline}


LAYOUTS = (
    (("basic", ("rel-001",)), ("coreference", ("rel-002", "rel-003")),
     ("coreference", ("rel-004", "rel-005")), ("basic", ("rel-006", "time-004")),
     ("combined", ("rel-007", "time-001", "rel-008", "time-002")),
     ("combined", ("rel-009", "time-003", "rel-010"))),
    (("basic", ("rel-002",)), ("coreference", ("rel-003", "rel-004")),
     ("coreference", ("rel-005", "rel-006", "time-004")), ("combined", ("rel-001", "rel-007", "time-001")),
     ("combined", ("rel-009", "time-003", "rel-008", "time-002")), ("basic", ("rel-010",))),
    (("combined", ("rel-008", "time-002", "rel-010")), ("basic", ("rel-001",)),
     ("combined", ("rel-007", "time-001", "rel-002")), ("coreference", ("rel-003", "rel-004")),
     ("coreference", ("rel-005", "rel-006", "time-004")), ("basic", ("rel-009", "time-003"))),
    (("basic", ("rel-009", "time-003")), ("combined", ("rel-007", "time-001", "rel-010")),
     ("basic", ("rel-002",)), ("coreference", ("rel-003", "rel-004")),
     ("coreference", ("rel-005", "rel-006", "time-004")), ("combined", ("rel-001", "rel-008", "time-002"))),
)


def _propositions(case_id, layout_index, facts_by_slot, language, gold_facts):
    propositions = []
    for number, (style, slots) in enumerate(LAYOUTS[layout_index], start=1):
        fact_ids = [facts_by_slot[slot]["fact_id"] for slot in slots]
        proposition = {"proposition_id": f"{case_id}-prop-{number:03d}", "style": style, "fact_ids": fact_ids}
        proposition["text"] = render_proposition(proposition, {f["fact_id"]: f for f in facts_by_slot.values()}, language, gold_facts)
        propositions.append(proposition)
        for slot in slots:
            facts_by_slot[slot]["source_proposition_ids"].append(proposition["proposition_id"])
    return propositions


def _negative_sources(error_type, facts_by_slot):
    mapping = {
        "actor_swap": ("rel-001",), "target_swap": ("rel-001",),
        "predicate_swap": ("rel-002",), "timestamp_shift": ("rel-006",),
        "negation_flip": ("rel-010",), "certainty_strengthening": ("rel-008",),
        "causality_insertion": ("time-003", "time-002"), "attribution_insertion": ("time-004",),
    }
    return [facts_by_slot[slot] for slot in mapping[error_type]]


def _pairs(case_id, case_number, language, gold_facts, facts):
    pairs = []
    start = ((case_number - 1) * 4) % len(facts)
    for offset in range(4):
        fact = facts[(start + offset) % len(facts)]
        pairs.append({
            "claim_id": f"{case_id}-claim-{offset + 1:03d}", "claim": render_fact(fact, language, gold_facts),
            "label": "SUPPORTED", "error_type": "none", "source_fact_ids": [fact["fact_id"]],
        })
    by_slot = {fact["slot"]: fact for fact in facts}
    for offset in range(4):
        error_type = CORRUPTION_TYPES[((case_number - 1) * 4 + offset) % len(CORRUPTION_TYPES)]
        sources = _negative_sources(error_type, by_slot)
        claim, _ = render_corruption(sources, error_type, language, gold_facts)
        pairs.append({
            "claim_id": f"{case_id}-claim-{offset + 5:03d}", "claim": claim,
            "label": "UNSUPPORTED", "error_type": error_type,
            "source_fact_ids": [fact["fact_id"] for fact in sources],
        })
    return pairs


def generate_cases(case_count=DEFAULT_CASE_COUNT, seed=DEFAULT_SEED):
    cases = []
    for zero_index in range(case_count):
        case_number = zero_index + 1
        language = "en" if zero_index < (case_count + 1) // 2 else "th"
        case_id = f"sv-{language}-{case_number:03d}"
        scenario = SCENARIOS[zero_index % len(SCENARIOS)]
        gold_facts = _gold(case_id, case_number, language, scenario)
        facts = gold_facts["relationships"] + gold_facts["timeline"]
        facts_by_slot = {fact["slot"]: fact for fact in facts}
        layout_index = zero_index % len(LAYOUTS)
        propositions = _propositions(case_id, layout_index, facts_by_slot, language, gold_facts)
        narrative = " ".join(proposition["text"] for proposition in propositions)
        cases.append({
            "case_id": case_id, "language": language, "schema_version": SCHEMA_VERSION, "seed": seed,
            "scenario_id": scenario[0], "narrative_template_id": f"{language}-layout-{layout_index + 1}",
            "narrative": narrative, "narrative_propositions": propositions, "gold_facts": gold_facts,
            "verification_pairs": _pairs(case_id, case_number, language, gold_facts, facts),
        })
    return cases


def write_jsonl(cases, path):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(json.dumps(case, ensure_ascii=False, sort_keys=True) for case in cases) + "\n", encoding="utf-8", newline="\n")
