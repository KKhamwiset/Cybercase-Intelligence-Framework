"""Deterministic bilingual renderers and semantic corruption operators."""

from copy import deepcopy
from datetime import datetime, timedelta
import re


PREDICATES = {
    "owns": ("owned", "เป็นเจ้าของ"), "sent": ("sent", "ส่ง"),
    "forwarded": ("forwarded", "ส่งต่อ"), "received": ("received", "ได้รับ"),
    "included": ("included", "มี"), "contained": ("contained", "บรรจุ"),
    "stored_as": ("was stored as", "ถูกจัดเก็บเป็น"),
    "saved_as": ("was saved as", "ถูกบันทึกเป็น"),
    "executed": ("executed", "เรียกใช้งาน"), "opened": ("opened", "เปิด"),
    "ran_on": ("ran on", "ทำงานบน"),
    "authenticated_on": ("authenticated on", "ยืนยันตัวตนบน"),
    "signed_in_from": ("signed in from", "ลงชื่อเข้าใช้จาก"),
    "submitted_credentials_to": ("submitted credentials to", "ส่งข้อมูลรับรองไปยัง"),
    "connected_to": ("connected to", "เชื่อมต่อไปยัง"),
    "accessed": ("accessed", "เข้าถึง"),
}

NEGATED_BASE = {
    "owns": "own", "sent": "send", "forwarded": "forward", "received": "receive",
    "included": "include", "contained": "contain", "stored_as": "be stored as",
    "saved_as": "be saved as", "executed": "execute", "opened": "open",
    "ran_on": "run on", "authenticated_on": "authenticate on",
    "signed_in_from": "sign in from", "submitted_credentials_to": "submit credentials to",
    "connected_to": "connect to", "accessed": "access",
}


def entity_map(gold_facts):
    return {entity["entity_id"]: entity for entity in gold_facts["entities"]}


def semantic_signature(fact):
    if fact["fact_kind"] == "relationship":
        edge = (fact["subject_entity_id"], fact["predicate"], fact["object_entity_id"])
    else:
        edge = (fact["actor_entity_id"], fact["relationship_predicate"], fact["target_entity_id"])
    return (fact["fact_kind"],) + edge + (
        fact.get("timestamp"), bool(fact.get("negated")), fact.get("certainty", "reported")
    )


def fact_edge(fact):
    if fact["fact_kind"] == "relationship":
        return fact["subject_entity_id"], fact["predicate"], fact["object_entity_id"]
    return fact["actor_entity_id"], fact["relationship_predicate"], fact["target_entity_id"]


def _timestamp_text(timestamp, language):
    if not timestamp:
        return ""
    return (" at " if language == "en" else " เมื่อ ") + timestamp


def render_fact(fact, language, gold_facts, sentence=True):
    entities = entity_map(gold_facts)
    actor_id, predicate, target_id = fact_edge(fact)
    actor, target = entities[actor_id]["name"], entities[target_id]["name"]
    phrase = PREDICATES[predicate][0 if language == "en" else 1]
    uncertain = fact.get("certainty") == "suspected"
    negated = bool(fact.get("negated"))
    timestamp = _timestamp_text(fact.get("timestamp"), language)
    if language == "en":
        if uncertain and negated:
            text = f"{actor} may not have {phrase} {target}{timestamp}"
        elif negated:
            text = f"{actor} did not {NEGATED_BASE[predicate]} {target}{timestamp}"
        else:
            text = f"{actor} {'may have ' if uncertain else ''}{phrase} {target}{timestamp}"
    else:
        text = f"{actor} {'อาจ' if uncertain else ''}{'ไม่ได้' if negated else ''}{phrase} {target}{timestamp}"
    return text + ("." if sentence else "")


def render_proposition(proposition, facts_by_id, language, gold_facts):
    rendered, seen_edges = [], set()
    for fact_id in proposition["fact_ids"]:
        fact = facts_by_id[fact_id]
        edge_key = (fact_edge(fact), fact.get("timestamp"), fact.get("negated"), fact.get("certainty"))
        if edge_key in seen_edges:
            continue
        seen_edges.add(edge_key)
        rendered.append(render_fact(fact, language, gold_facts, sentence=False))
    if not rendered:
        raise ValueError("proposition contains no renderable facts")
    if proposition["style"] == "coreference" and len(rendered) > 1:
        first_target = entity_map(gold_facts)[fact_edge(facts_by_id[proposition["fact_ids"][0]])[2]]["name"]
        pronoun = "it" if language == "en" else "สิ่งดังกล่าว"
        rendered[1] = re.sub(r"^" + re.escape(first_target) + r"\b", pronoun, rendered[1])
    connector = "; " if proposition["style"] == "combined" else (", and " if language == "en" else " และ")
    return connector.join(rendered) + "."


def normalized_claim(text):
    return re.sub(r"[^\wก-๙]+", " ", text.casefold(), flags=re.UNICODE).strip()


def _alternate_entity(entity_id, gold_facts):
    entities = entity_map(gold_facts)
    entity_type = entities[entity_id]["entity_type"]
    choices = sorted(e["entity_id"] for e in gold_facts["entities"] if e["entity_type"] == entity_type and e["entity_id"] != entity_id)
    if not choices:
        raise ValueError("no same-type alternate entity")
    return choices[0]


def _shift_timestamp(value):
    if not value:
        raise ValueError("timestamp_shift requires a timestamp")
    shifted = datetime.fromisoformat(value.replace("Z", "+00:00")) + timedelta(hours=3)
    return shifted.isoformat(timespec="minutes").replace("+00:00", "Z")


def corrupt_fact(source_fact, error_type, gold_facts):
    corrupted = deepcopy(source_fact)
    if error_type == "actor_swap":
        key = "subject_entity_id" if corrupted["fact_kind"] == "relationship" else "actor_entity_id"
        corrupted[key] = _alternate_entity(corrupted[key], gold_facts)
    elif error_type == "target_swap":
        key = "object_entity_id" if corrupted["fact_kind"] == "relationship" else "target_entity_id"
        corrupted[key] = _alternate_entity(corrupted[key], gold_facts)
    elif error_type == "predicate_swap":
        if corrupted["fact_kind"] != "relationship":
            raise ValueError("predicate_swap requires a relationship")
        corrupted["predicate"] = "accessed" if corrupted["predicate"] != "accessed" else "connected_to"
    elif error_type == "timestamp_shift":
        corrupted["timestamp"] = _shift_timestamp(corrupted.get("timestamp"))
    elif error_type == "negation_flip":
        corrupted["negated"] = not bool(corrupted.get("negated"))
    elif error_type == "certainty_strengthening":
        if corrupted.get("certainty") != "suspected":
            raise ValueError("certainty_strengthening requires suspected source")
        corrupted["certainty"] = "reported"
    else:
        raise ValueError("multi-fact corruption requires render_corruption")
    return corrupted


def render_corruption(source_facts, error_type, language, gold_facts):
    if error_type not in {"causality_insertion", "attribution_insertion"}:
        corrupted = corrupt_fact(source_facts[0], error_type, gold_facts)
        return render_fact(corrupted, language, gold_facts), semantic_signature(corrupted)
    entities = entity_map(gold_facts)
    if error_type == "causality_insertion":
        if len(source_facts) != 2:
            raise ValueError("causality_insertion requires two source facts")
        first = render_fact(source_facts[0], language, gold_facts, sentence=False)
        second = render_fact(source_facts[1], language, gold_facts, sentence=False)
        claim = (f"The event in which {first} caused the later event in which {second}." if language == "en"
                 else f"เหตุการณ์ที่{first}เป็นสาเหตุให้เกิดเหตุการณ์ภายหลังที่{second}.")
        return claim, ("causes", semantic_signature(source_facts[0]), semantic_signature(source_facts[1]))
    event = source_facts[0]
    actor_id = sorted(e["entity_id"] for e in gold_facts["entities"] if e["entity_type"] == "user")[0]
    event_text = render_fact(event, language, gold_facts, sentence=False)
    claim = (f"{entities[actor_id]['name']} initiated the event in which {event_text}." if language == "en"
             else f"{entities[actor_id]['name']}เป็นผู้เริ่มเหตุการณ์ที่{event_text}.")
    return claim, ("attributed", actor_id, semantic_signature(event))
