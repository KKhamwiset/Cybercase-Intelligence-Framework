"""Strict construction validator for the synthetic JSONL fixture."""

import json
from pathlib import Path
import re

from .constants import CORRUPTION_TYPES, DEFAULT_CASE_COUNT, FORBIDDEN_TERMS, LEAK_MARKERS, LIMITATIONS, SCHEMA_VERSION
from .rendering import fact_edge, normalized_claim, render_corruption, render_fact, render_proposition, semantic_signature


class _DuplicateKeyError(ValueError):
    pass


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError("duplicate JSON key: %s" % key)
        result[key] = value
    return result


def _reject_non_finite(value):
    raise ValueError("non-finite JSON value: %s" % value)


def _record(failures, message):
    if message not in failures:
        failures.append(message)


def _sentence_count(narrative):
    return len(re.findall(r"[.!?。！？](?=\s|$)", narrative))


def _parse_dataset(path, failures):
    cases = []
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        _record(failures, "unable to read dataset: %s" % exc)
        return cases
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            _record(failures, "line %d is blank" % line_number)
            continue
        try:
            value = json.loads(line, object_pairs_hook=_reject_duplicate_keys, parse_constant=_reject_non_finite)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            _record(failures, "line %d is malformed JSON: %s" % (line_number, exc))
            continue
        if not isinstance(value, dict):
            _record(failures, "line %d is not a JSON object" % line_number)
        else:
            cases.append(value)
    return cases


def _fact_entities(fact):
    if fact.get("fact_kind") == "relationship":
        return fact.get("subject_entity_id"), fact.get("object_entity_id")
    return fact.get("actor_entity_id"), fact.get("target_entity_id")


def validate_dataset(path, strict=True):
    failures = []
    cases = _parse_dataset(path, failures)
    seen_ids = {"case": set(), "entity": set(), "fact": set(), "claim": set(), "proposition": set()}
    languages = {"en": 0, "th": 0}
    pair_counts = {"total": 0, "positive": 0, "negative": 0}
    label_counts = {"SUPPORTED": 0, "UNSUPPORTED": 0}
    corruption_counts = {error_type: 0 for error_type in CORRUPTION_TYPES}
    positive_slots = set()
    gold_slots = set()
    scenario_counts, template_counts = {}, {}
    seed_values, schema_versions = set(), set()

    for case_number, case in enumerate(cases, start=1):
        location = "case[%d]" % case_number
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            _record(failures, "%s.case_id must be a non-empty string" % location)
            continue
        if case_id in seen_ids["case"]:
            _record(failures, "duplicate case_id: %s" % case_id)
        seen_ids["case"].add(case_id)
        language = case.get("language")
        if language not in languages:
            _record(failures, "%s.language must be en or th" % location)
            continue
        languages[language] += 1
        seed_values.add(case.get("seed"))
        schema_versions.add(case.get("schema_version"))
        scenario = case.get("scenario_id")
        template = case.get("narrative_template_id")
        scenario_counts[scenario] = scenario_counts.get(scenario, 0) + 1
        template_counts[template] = template_counts.get(template, 0) + 1

        narrative = case.get("narrative")
        if not isinstance(narrative, str):
            _record(failures, "%s.narrative must be a string" % location)
            narrative = ""
        if not 3 <= _sentence_count(narrative) <= 8:
            _record(failures, "%s narrative must contain 3-8 sentences" % location)
        lowered = narrative.casefold()
        for term in FORBIDDEN_TERMS:
            if re.search(r"(?<![a-z])" + re.escape(term) + r"(?![a-z])", lowered):
                _record(failures, "%s narrative contains forbidden term: %s" % (location, term))

        gold_facts = case.get("gold_facts")
        if not isinstance(gold_facts, dict):
            _record(failures, "%s.gold_facts must be an object" % location)
            continue
        entities = gold_facts.get("entities", [])
        facts = gold_facts.get("relationships", []) + gold_facts.get("timeline", [])
        entities_by_id, facts_by_id = {}, {}
        for entity in entities:
            entity_id = entity.get("entity_id") if isinstance(entity, dict) else None
            if not entity_id or entity_id in seen_ids["entity"]:
                _record(failures, "%s has missing or duplicate entity ID: %s" % (location, entity_id))
            else:
                seen_ids["entity"].add(entity_id)
                entities_by_id[entity_id] = entity
        for fact in facts:
            fact_id = fact.get("fact_id") if isinstance(fact, dict) else None
            if not fact_id or fact_id in seen_ids["fact"]:
                _record(failures, "%s has missing or duplicate fact ID: %s" % (location, fact_id))
                continue
            seen_ids["fact"].add(fact_id)
            facts_by_id[fact_id] = fact
            gold_slots.add(fact.get("slot"))
            for entity_id in _fact_entities(fact):
                if entity_id not in entities_by_id:
                    _record(failures, "%s fact %s references unknown entity %s" % (location, fact_id, entity_id))

        propositions = case.get("narrative_propositions")
        if not isinstance(propositions, list) or not propositions:
            _record(failures, "%s must contain narrative_propositions" % location)
            propositions = []
        proposition_by_id = {}
        for proposition in propositions:
            proposition_id = proposition.get("proposition_id") if isinstance(proposition, dict) else None
            if not proposition_id or proposition_id in seen_ids["proposition"]:
                _record(failures, "%s has missing or duplicate proposition ID: %s" % (location, proposition_id))
                continue
            seen_ids["proposition"].add(proposition_id)
            proposition_by_id[proposition_id] = proposition
            fact_ids = proposition.get("fact_ids")
            if not isinstance(fact_ids, list) or not fact_ids or any(fid not in facts_by_id for fid in fact_ids):
                _record(failures, "%s proposition %s references unknown facts" % (location, proposition_id))
                continue
            try:
                expected_text = render_proposition(proposition, facts_by_id, language, gold_facts)
            except (KeyError, TypeError, ValueError) as exc:
                _record(failures, "%s proposition %s cannot be rendered: %s" % (location, proposition_id, exc))
                continue
            if proposition.get("text") != expected_text:
                _record(failures, "%s proposition %s text is not entailed by its gold facts" % (location, proposition_id))
            for fact_id in fact_ids:
                fact = facts_by_id[fact_id]
                proposition_text = proposition.get("text", "")
                for entity_id in _fact_entities(fact):
                    entity = entities_by_id.get(entity_id, {})
                    if entity.get("name") not in proposition_text:
                        _record(failures, "%s fact %s entity %s is absent from source proposition" % (location, fact_id, entity_id))
                if fact.get("timestamp") and fact["timestamp"] not in proposition_text:
                    _record(failures, "%s fact %s timestamp is absent from source proposition" % (location, fact_id))
        expected_narrative = " ".join(proposition.get("text", "") for proposition in propositions)
        if narrative != expected_narrative:
            _record(failures, "%s narrative does not equal its deterministic propositions" % location)

        for fact in facts:
            fact_id = fact.get("fact_id")
            source_ids = fact.get("source_proposition_ids")
            if not isinstance(source_ids, list) or not source_ids:
                _record(failures, "%s fact %s has no source proposition" % (location, fact_id))
                continue
            for proposition_id in source_ids:
                proposition = proposition_by_id.get(proposition_id)
                if proposition is None or fact_id not in proposition.get("fact_ids", []):
                    _record(failures, "%s fact %s source proposition mapping is invalid" % (location, fact_id))

        relationship_signatures = {
            (fact_edge(fact), fact.get("timestamp"), fact.get("certainty"), fact.get("negated"))
            for fact in gold_facts.get("relationships", [])
        }
        for event in gold_facts.get("timeline", []):
            signature = (fact_edge(event), event.get("timestamp"), event.get("certainty"), event.get("negated"))
            if signature not in relationship_signatures:
                _record(failures, "%s timeline fact %s lacks its explicit gold relationship" % (location, event.get("fact_id")))

        gold_renderings = set()
        for fact in facts:
            try:
                gold_renderings.add(normalized_claim(render_fact(fact, language, gold_facts)))
            except (KeyError, TypeError, ValueError) as exc:
                _record(failures, "%s fact %s cannot be rendered: %s" % (location, fact.get("fact_id"), exc))

        case_positive = case_negative = 0
        pairs = case.get("verification_pairs")
        if not isinstance(pairs, list) or len(pairs) != 8:
            _record(failures, "%s must contain eight verification pairs" % location)
            pairs = pairs if isinstance(pairs, list) else []
        for pair_index, pair in enumerate(pairs, start=1):
            pair_location = "%s.verification_pairs[%d]" % (location, pair_index)
            claim_id = pair.get("claim_id") if isinstance(pair, dict) else None
            if not claim_id or claim_id in seen_ids["claim"]:
                _record(failures, "%s has missing or duplicate claim ID" % pair_location)
                continue
            seen_ids["claim"].add(claim_id)
            claim, label, error_type = pair.get("claim"), pair.get("label"), pair.get("error_type")
            source_ids = pair.get("source_fact_ids")
            if not isinstance(claim, str):
                _record(failures, "%s.claim must be a string" % pair_location)
                continue
            for marker in LEAK_MARKERS:
                if marker in claim.casefold():
                    _record(failures, "%s contains a label-leaking marker" % pair_location)
            if not isinstance(source_ids, list) or not source_ids or any(fid not in facts_by_id for fid in source_ids):
                _record(failures, "%s references unknown source facts" % pair_location)
                continue
            sources = [facts_by_id[fid] for fid in source_ids]
            pair_counts["total"] += 1
            if label == "SUPPORTED" and error_type == "none":
                case_positive += 1
                pair_counts["positive"] += 1
                label_counts["SUPPORTED"] += 1
                if len(sources) != 1:
                    _record(failures, "%s supported claim requires one source fact" % pair_location)
                    continue
                expected = render_fact(sources[0], language, gold_facts)
                if claim != expected:
                    _record(failures, "%s positive claim is not entailed by its source fact and narrative" % pair_location)
                if not sources[0].get("source_proposition_ids"):
                    _record(failures, "%s positive source fact is absent from narrative" % pair_location)
                positive_slots.add(sources[0].get("slot"))
            elif label == "UNSUPPORTED" and error_type in CORRUPTION_TYPES:
                case_negative += 1
                pair_counts["negative"] += 1
                label_counts["UNSUPPORTED"] += 1
                corruption_counts[error_type] += 1
                try:
                    expected, corrupted_signature = render_corruption(sources, error_type, language, gold_facts)
                except (KeyError, TypeError, ValueError) as exc:
                    _record(failures, "%s corruption cannot be rendered: %s" % (pair_location, exc))
                    continue
                source_signatures = {semantic_signature(source) for source in sources}
                source_claims = {normalized_claim(render_fact(source, language, gold_facts)) for source in sources}
                if claim != expected:
                    _record(failures, "%s negative claim is not the deterministic semantic corruption" % pair_location)
                if corrupted_signature in source_signatures or normalized_claim(claim) in source_claims:
                    _record(failures, "%s negative corruption is identical or trivially equivalent to its source" % pair_location)
                if normalized_claim(claim) in gold_renderings:
                    _record(failures, "%s negative corruption equals a gold fact" % pair_location)
            else:
                _record(failures, "%s has inconsistent label and error_type" % pair_location)
        if case_positive != 4 or case_negative != 4:
            _record(failures, "%s must contain four supported and four unsupported pairs" % location)

    if strict and len(cases) != DEFAULT_CASE_COUNT:
        _record(failures, "strict mode requires exactly %d cases" % DEFAULT_CASE_COUNT)
    if strict and languages != {"en": 50, "th": 50}:
        _record(failures, "strict mode requires exactly 50 en and 50 th cases")
    if strict and positive_slots != gold_slots:
        _record(failures, "positive claims do not cover every supported gold-fact slot")
    if strict and (len(scenario_counts) < 4 or len(template_counts) < 8):
        _record(failures, "strict mode requires at least four scenarios and eight bilingual templates")
    for error_type, count in corruption_counts.items():
        if count == 0:
            _record(failures, "corruption type has zero cases: %s" % error_type)
    if len(seed_values) > 1:
        _record(failures, "multiple seed values found")
    if schema_versions and schema_versions != {SCHEMA_VERSION}:
        _record(failures, "unexpected schema version")

    return {
        "valid": not failures, "schema_version": next(iter(schema_versions), SCHEMA_VERSION),
        "seed": next(iter(seed_values), None), "case_count": len(cases), "language_counts": languages,
        "pair_counts": pair_counts, "label_counts": label_counts, "corruption_counts": corruption_counts,
        "scenario_counts": dict(sorted(scenario_counts.items())), "template_counts": dict(sorted(template_counts.items())),
        "positive_fact_slots_covered": sorted(slot for slot in positive_slots if slot),
        "gold_fact_slots": sorted(slot for slot in gold_slots if slot),
        "positive_slot_coverage": (len(positive_slots) / len(gold_slots)) if gold_slots else 0.0,
        "integrity_failures": failures, "limitations": list(LIMITATIONS),
    }
