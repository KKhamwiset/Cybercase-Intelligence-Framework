# Offline semantic verification benchmark

This directory is an isolated, deterministic research fixture for relationship and timeline claim verification in English and Thai. It does not import or exercise the application extractor.

## Construction methodology

Labels come from construction, never from a language-model judgment:

1. Build authoritative structured entities, relationships, and timeline facts.
2. Assign every gold fact to a machine-readable narrative proposition.
3. Render each proposition and the final narrative deterministically from those facts.
4. Render supported claims from mapped gold facts.
5. Render unsupported claims after a controlled structured corruption.

Timeline events with an explicit actor-target edge also have a matching gold relationship. Every fact records `source_proposition_ids`; every proposition records `fact_ids` and its deterministic text. This allows the validator to reject ghost entities, targets, relationships, and timestamps without asking a model to decide entailment.

## Default fixture

- 100 cases: 50 English and 50 Thai
- 3-8 sentences per narrative (six in the generated fixture)
- 8 pairs per case: 4 supported and 4 unsupported
- 400 supported and 400 unsupported claims
- 50 uses of each corruption type
- four incident scenarios and four layouts per language
- complete positive coverage of all ten relationship and four timeline fact slots

The layouts vary sentence order and combined versus split facts. Coreference is used in both languages. Cases contain optional timestamps plus explicit uncertainty and negation.

## JSONL record shape

```text
case_id, language, schema_version, seed
scenario_id, narrative_template_id
narrative
narrative_propositions: [{proposition_id, style, fact_ids, text}]
gold_facts:
  entities: [{entity_id, entity_type, name}]
  relationships: [{fact_id, slot, subject_entity_id, predicate,
                   object_entity_id, timestamp, certainty, negated,
                   source_proposition_ids}]
  timeline: [{fact_id, slot, event_type, actor_entity_id,
              relationship_predicate, target_entity_id, timestamp,
              certainty, negated, source_proposition_ids}]
verification_pairs: [{claim_id, claim, label, error_type, source_fact_ids}]
```

`source_fact_ids` contains two facts for `causality_insertion` and one for other corruptions.

## Validator guarantees

Strict validation rejects:

- duplicate or malformed IDs/JSON;
- a narrative or proposition that differs from deterministic gold rendering;
- a fact entity or timestamp absent from its source proposition;
- an unmapped gold fact;
- a timeline actor-target edge without its matching relationship;
- a supported claim not rendered from a narrative-backed gold fact;
- a negative claim that is not the requested deterministic corruption;
- a negative corruption identical or trivially equivalent to its source;
- label-revealing corruption markers;
- missing language, scenario, template, corruption, or positive-slot coverage.

## Offline commands

Run from the repository root:

```powershell
python -m experiments.semantic_verification generate
python -m experiments.semantic_verification validate
python -m unittest discover -s experiments/semantic_verification/tests -p "test_*.py"
python -m compileall -q experiments/semantic_verification
```

Generation writes `data/semantic_verification.jsonl`, `reports/summary.json`, and `reports/summary.md`.

## Boundary

The package uses only the Python standard library. It makes no network, database, retrieval, external-knowledge, or model calls and contains no external taxonomy content. Passing validates fixture construction; it is not an E0 run, semantic-verifier result, forensic conclusion, or deployed-model quality result.
