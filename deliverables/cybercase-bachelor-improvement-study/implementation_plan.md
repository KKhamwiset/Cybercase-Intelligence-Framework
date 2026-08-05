# CyberCase Case-File Study Implementation Plan

Status: implementation plan only. No B0/B1 experiment, model run, product integration, or effectiveness evaluation has been completed.

Snapshot reviewed: 2026-08-05, Git HEAD 0011d89c35b8906a9bb01defe5d55c2e54bb97c1.

## 1. Decision

Implement the thesis experiment as a new, isolated research harness under:

    experiments/casefile_study/

Do not begin by modifying the production frontend, backend, PostgreSQL schema, RAG service, Docker stack, or existing follow-up pilot.

This is the smallest defensible path because the live application accepts one text message, persists chat state, asks a product-oriented clarification before RAG, and builds an unverified report only in the browser. It does not currently accept or persist a multi-artifact case file, preserve evidence-grade source locations, or generate a backend-owned report.

The scientific comparison will be:

- B0: an adapted Dehing-style two-stage extraction and synthesis pipeline over a frozen cyber-investigative case packet.
- B1: one reduced FollowupQ-inspired clarification before the exact unchanged B0.
- Optional complete-packet reference: the complete packet through B0, reported only as a recoverability reference.

This is an adaptation and controlled evaluation, not a new algorithm.

## 2. Authority and scope

Use sources in this order when statements conflict:

1. Executable code and tests in the current checkout.
2. This implementation plan and the corrected cybercase-bachelor-improvement-study package.
3. The current Chapter I and Chapter II drafts after their planned corrections.
4. The older cybercase-report-followup-gap-study package only as an advanced or archival methodology reference.
5. Old project Markdown only when it still agrees with the executable path.

Production paths that are out of scope for the core experiment:

- backend/**
- frontend/**
- rag_service/**
- docker-compose.yml
- experiments/followup_pilot/**
- all database migrations and existing database state

The core experiment must not import the production analysis prompt, chat worker, product follow-up policy, RAG client, database models, demo report builder, or RAG service. Reusing them would inherit a Microsoft 365-specific task, a string-only input contract, up to three product follow-up rounds, transient retrieval provenance, and a report format that is not the B0/B1 method.

Reusable ideas are limited to repository conventions such as typed records, fake-adapter tests, append-only result files, and explicit timing/call logging.

## 3. Current pipeline versus research pipeline

### Current live product

    Chat textarea
      -> POST /api/v1/chats/{thread_id}/messages
      -> persist ChatMessage and queued ChatRun
      -> add the current Microsoft 365 analysis preprompt
      -> backend follow-up policy
           -> ask: persist one assistant question and make zero RAG calls
           -> proceed: build one clarified text query
      -> rag_service POST /query
      -> persist assistant answer, retrieval_context_id, MITRE rows, and demo metadata
      -> browser constructs a non-persistent, unverified seven-section report

Important limits:

- Input is plain text; there is no upload, OCR, case, exhibit, or source-file contract.
- PostgreSQL stores chat threads, messages, and runs, not case dossiers or reports.
- The RAG boundary accepts query: str, not a CasePacket.
- Retrieval context is an in-memory time-limited snapshot, not durable evidence provenance.
- The report tab is client-side and explicitly demo-only.

### Selected research pipeline

    Official source record and rights review
      -> examiner-curated complete CasePacket
      -> immutable packet hash
      -> deterministic missing-finding mask
      -> paired condition

    B0:
      incomplete packet
      -> Stage 1 evidence extraction with evidence_id and source locators
      -> Stage 2 fixed provisional report
      -> structural and provenance validation

    B1:
      the same incomplete packet
      -> one candidate from each of three fixed perspectives
      -> normalize and remove exact duplicates
      -> visible-evidence-only selector chooses zero or one question
      -> blind target-match adjudication
      -> optional supplemental investigator statement
      -> the byte-identical B0
      -> structural and provenance validation

    Both:
      -> append-only run records
      -> blinded scoring
      -> case-level descriptive paired analysis

### Effect on the live system

During the core study, there is no runtime effect on the live application:

- no API changes;
- no migration or database changes;
- no UI changes;
- no Docker or deployment changes;
- no RAG-service behavior changes;
- no new handling of real police or private case files.

The only repository impact is a new isolated experiment directory plus later, explicitly reviewed thesis/paper document updates.

## 4. Core data contract

The experiment should define strict, versioned models for:

- SourceRecord: source URL, retrieval time, filename, byte count, SHA-256, creator or rights holder, reuse basis, redistribution decision, reviewer, and verification date.
- CasePacket: case ID, language, packet version, mandate, exhibit register, acquisition/integrity records, evidence items, and packet hash.
- EvidenceItem: evidence ID, artifact type, packet locator, original forensic-artifact locator when available, content, content hash, and provenance.
- RequiredFinding: hidden examiner-prepared finding and valid supporting evidence locations.
- GapDefinition: gap ID, removed evidence, acceptable question predicates, hidden answer, answer provenance, and resolution rule.
- SupplementalInvestigatorStatement: a new statement ID, provider, question ID, gap ID, time, content, and source type. It must never reuse an exhibit evidence ID.
- Stage1Finding: normalized finding, confidence/status, evidence ID, packet locator, and original locator.
- ProvisionalReport: fixed sections, claims, source labels, evidence references, uncertainty, and limitations.
- RunRecord: condition, repeat, packet/config/prompt hashes, model identity, raw responses, timing, tokens, calls, failure state, and output hashes.
- ScoreRecord: blind item ID, scorer ID, original labels, adjudicated labels, and rationale.

Claim support must use three distinct labels:

- evidence_supported: supported by a resolvable original exhibit;
- investigator_reported: supported only by a supplemental investigator statement;
- unsupported: supported by neither.

An investigator-reported statement may improve completeness. It must not increase forensic evidence-reference coverage unless it introduces a separately registered exhibit with a valid source locator.

## 5. Proposed file ownership

One implementer should own the entire experiment directory to avoid cross-file contract drift:

    experiments/casefile_study/
      __init__.py
      README.md
      schemas.py
      source_registry.py
      packet_builder.py
      masking.py
      validation.py
      prompts.py
      model_client.py
      baseline.py
      clarification.py
      runner.py
      scoring.py
      analysis.py
      data/
        sources/
          source_manifest.json
          source_hashes.json
        packets/
        gaps/
        preregistration/
      prompts/
        b0_stage1.txt
        b0_stage2.txt
        b1_entity_role.txt
        b1_chronology.txt
        b1_evidence_citation.txt
        b1_selector.txt
        report_schema.json
      rubrics/
      results/
        .gitkeep
      scores/
        raw/
        adjudicated/
      tests/
        test_schemas.py
        test_source_registry.py
        test_packet_hashes.py
        test_source_locators.py
        test_no_gold_leakage.py
        test_masking.py
        test_stage_contracts.py
        test_citation_resolution.py
        test_candidate_visibility.py
        test_target_release.py
        test_b0_parity.py
        test_result_contract.py
        test_secret_redaction.py
        test_metric_denominators.py
        test_case_level_aggregation.py

Raw CFReDS forensic images must not be committed. Store official URLs, checksums, and local acquisition instructions. Commit only legally redistributable metadata, examiner-curated packet text/structure, schemas, prompts, configuration, and evaluation artifacts.

## 6. Phased implementation

### Phase 0 - freeze the decision and research contract

Dates: 2026-08-05 to 2026-08-09.

Actions:

1. Record Git HEAD and the full dirty baseline.
2. Mark cybercase-bachelor-improvement-study as the active package.
3. Mark cybercase-report-followup-gap-study as advanced/archival, not the Bachelor source of truth.
4. Freeze B0, B1, the three question perspectives, the one-question limit, and the three claim-support labels.
5. Correct the Chapter II intervention position: B1 occurs before the complete unchanged B0, not between Stage 1 and Stage 2.
6. Freeze the list of prohibited production imports and paths.

Outputs:

- approved implementation plan;
- draft correction checklist;
- experiment ownership and prohibited-path list.

Acceptance gate:

- the supervisor can describe B0 and B1 without referencing the current chat workflow;
- all planned production-path diffs are empty;
- no result or effectiveness claim is present.

Rollback:

- remove only the new planning file or revert explicitly selected deliverable edits.

### Phase 1 - source acquisition and rights gate

Dates: 2026-08-10 to 2026-08-23.

Actions:

1. Acquire the minimum official CFReDS scenario/reference files required to prepare the packet; link to raw images rather than redistributing them.
2. Acquire the CASE Owl narrative and JSON-LD needed for the small transfer check.
3. Record exact URLs, timestamps, names, sizes, SHA-256 hashes, creator/rights holder, applicable reuse text, and redistribution decisions.
4. Review item-level third-party material.
5. Stop and replace a source if its intended derivative cannot be lawfully used.

Outputs:

- executable source_manifest.json;
- source_hashes.json;
- source_review.md;
- reproducible acquisition instructions.

Acceptance gate:

- every used file has a hash and rights decision;
- no raw image or restricted solution is committed;
- the CASE derivative decision is explicit rather than assumed.

Rollback:

- remove the unapproved source and its planned gaps; do not weaken the rights gate.

### Phase 2 - CasePacket, packet builder, and preregistration

Dates: 2026-08-24 to 2026-09-06.

Actions:

1. Implement the strict models listed in Section 4.
2. Build the complete examiner-curated packet before creating any gaps.
3. Preserve both packet locators and original forensic-artifact locators where available.
4. Use public answer documents only to define hidden required findings and locate supporting artifacts; do not copy answer prose into the visible packet.
5. Hash and freeze the complete packets.
6. Create six CFReDS gaps balanced across entity/role, chronology, and evidence/citation where practical.
7. Create two CASE Owl transfer gaps under a separate namespace.
8. Preregister acceptable question predicates, hidden answers, provenance, and resolution rules before viewing model output.
9. Derive every incomplete packet deterministically from the complete packet.

Outputs:

- valid complete packets;
- six primary and two transfer gap definitions;
- packet/gap hashes;
- preregistration file;
- validation and leakage tests.

Acceptance gate:

- all IDs are unique;
- every visible locator resolves;
- every removed finding and its direct duplicates are absent from model-visible input;
- gold files are unreachable through the model input object;
- the packet is clearly described as examiner-curated, not raw-disk extraction.

Rollback:

- regenerate an invalid gap from the immutable complete packet; never patch a masked packet by hand.

### Phase 3 - implement and validate B0 only

Dates: 2026-09-07 to 2026-09-20.

Actions:

1. Freeze a report schema before model runs.
2. Implement Stage 1 extraction over ordered packet evidence or bounded chunks.
3. Require Stage 1 findings to retain evidence IDs and locators.
4. Implement Stage 2 using only ordered Stage 1 findings.
5. Prevent Stage 2 from reading the packet, hidden gold, condition label, or scorer data directly.
6. Record prompt, schema, model, decoding, and context hashes.
7. Add structural, citation-resolution, and unsupported-ID validators.
8. Run an offline fake-model test suite before any paid/live model call.

Outputs:

- executable B0;
- fixed prompts and report schema;
- fake-model fixtures;
- B0 validation report.

Acceptance gate:

- every emitted evidence reference resolves or the run fails validation;
- Stage 2 cannot access hidden data;
- B0 records exact configuration hashes;
- no production module is imported.

Rollback:

- revert only baseline.py, prompts, report schema, and their tests; packet artifacts remain immutable.

### Phase 4 - implement B1 as the only treatment

Dates: 2026-09-21 to 2026-10-04.

Actions:

1. Generate exactly one candidate from each fixed perspective: entity/role, chronology, and evidence/citation.
2. Normalize and remove exact duplicates.
3. Use one selector prompt that sees only the visible incomplete packet and candidates.
4. Select zero or one question.
5. Freeze selected questions before looking at target labels.
6. Have two blinded reviewers judge target match against preregistered semantic predicates; adjudicate disagreements.
7. Release one supplemental investigator statement only on a matched question.
8. Run the exact B0 configuration used in the paired B0 condition.
9. Prove B0 prompt/schema/model/decoding hashes are identical across B0 and B1.

Outputs:

- executable B1 question pass;
- blind match sheets and adjudication;
- conditional statement-release pass;
- B0 parity report.

Acceptance gate:

- generation and selection cannot access hidden gold;
- mismatch releases no answer;
- a supplemental statement cannot masquerade as exhibit evidence;
- the serialized B0 configuration is byte-identical in paired conditions.

Rollback:

- disable B1 and retain a valid B0 study; never alter B0 to make B1 easier.

### Phase 5 - runner, records, and pilot freeze

Dates: 2026-10-05 to 2026-10-11.

Actions:

1. Implement condition/repeat orchestration.
2. Make result files append-only with unique run IDs.
3. Record raw output, failures, latency, model calls, tokens when available, and all hashes.
4. Redact secrets and environment values from results.
5. Run one preregistered pilot gap only to verify mechanics.
6. Fix implementation defects, then freeze code/prompts/config before the full run.
7. Do not use pilot values as final results unless the protocol explicitly includes them.

Outputs:

- runner;
- immutable run contract;
- pilot mechanics report;
- frozen experiment version.

Acceptance gate:

- reruns never overwrite earlier records;
- failed calls remain visible;
- no secret appears in output;
- the pilot demonstrates only mechanics;
- the frozen commit/snapshot and configuration are recorded.

Rollback:

- retain failed run records, fix the defect under a new version, and repeat the pilot; do not silently replace history.

### Phase 6 - full paired execution

Dates: 2026-10-12 to 2026-10-18.

Planned run count:

- CFReDS: 6 gaps x 2 conditions x 3 repeats = 36 primary runs.
- CASE Owl: 2 gaps x 2 conditions x 3 repeats = 12 transfer runs.
- Total: 48 report runs, plus the separately recorded B1 question-selection calls.

Actions:

1. Randomize execution order without changing paired settings.
2. Use three repeats even at low temperature unless deterministic behavior is demonstrated and preregistered otherwise.
3. Preserve every raw success and failure.
4. Run validators immediately after each output.
5. Stop on systemic parity, leakage, citation, or secret-redaction failure.

Outputs:

- raw append-only reports;
- question and statement records;
- validator results;
- run manifest and cost log.

Acceptance gate:

- the expected run matrix is complete or every missing cell has a documented failure;
- B0/B1 parity checks pass;
- all primary citations have validator outcomes;
- CASE is clearly separated from CFReDS.

Rollback:

- no destructive rollback of results; a corrected run uses a new experiment version and run IDs.

### Phase 7 - blinded scoring and adjudication

Dates: 2026-10-19 to 2026-11-01.

Actions:

1. Remove condition labels and randomize report/question identifiers for scoring.
2. Score required-finding recall, evidence-supported claim precision, investigator-reported claims, unsupported-claim rate, evidence-reference coverage, locator accuracy, entity correctness, and timeline correctness.
3. Score target-gap match@1, redundancy, answerability, latency, tokens, and calls.
4. Double-score all CFReDS primary outputs for the paper.
5. If resources are limited, preregister any reduced double-scoring scope for the CASE transfer before opening results.
6. Preserve original labels, calculate agreement, and adjudicate disagreements.

Outputs:

- blind scorer packets;
- original scorer files;
- agreement summary;
- adjudication log;
- frozen analysis-ready table.

Acceptance gate:

- denominators are explicit and tested;
- evidence-supported and investigator-reported claims are not merged;
- CFReDS and CASE are aggregated separately;
- no scorer sees the condition label during initial scoring where practical.

Rollback:

- correct rubric or tooling defects under a recorded scoring version; preserve prior labels.

### Phase 8 - analysis, thesis, and paper

Dates: 2026-11-02 to 2026-11-15.

Actions:

1. Report every gap and repeat.
2. Aggregate gaps within each case before comparing conditions.
3. Report descriptive paired B1-minus-B0 changes; do not run significance tests over eight correlated gaps.
4. Keep CASE as a small transfer check, not broad external validation.
5. Update Chapter I to match the implemented scope.
6. Update Chapter II to describe the final B0/B1 position and FollowupQ adaptation correctly.
7. Write Chapter III from the frozen protocol, Chapter IV from implemented code, and Chapter V only from frozen results.
8. Write one narrow paper using the same experiment; do not create a second experiment.

Outputs:

- result tables and figures;
- updated thesis chapters;
- focused paper draft;
- claim-evidence map;
- reproducibility appendix.

Acceptance gate:

- every numeric claim resolves to a result artifact;
- every method claim resolves to implemented code/config;
- no current product demo is counted as experimental evidence;
- limitations explicitly include English-source data, examiner-curated packets, small case count, controlled supplemental answers, and no operational validation.

Rollback:

- remove or weaken unsupported claims; never backfill missing evidence with prose.

### Phase 9 - submission QA and contingency

Dates: 2026-11-16 to 2026-11-22.

Actions:

1. Re-run all offline validation.
2. Verify hashes, citations, tables, figures, references, and artifact links.
3. Render and visually inspect the thesis and paper.
4. Freeze a reproducibility bundle that excludes restricted/raw evidence and secrets.
5. Reserve this week for failed-source, model, or scoring contingencies.

Acceptance gate:

- clean reproducibility instructions work from the declared environment;
- no result file was overwritten;
- the manuscript separates implemented, planned, absent, and demo-only capabilities;
- final source rights and redistribution decisions are documented.

## 7. Draft reconciliation

Draft lineage checked on 2026-08-05:

| Role | Current source | Evidence |
|---|---|---|
| Chapter I | F:/Chapter_I_Final.docx | Modified 2026-06-15 12:35; SHA-256 D313E3995FA7C3C555DF5B80A600FB8CCF57BA461E387F8C6F93C0BB1EFCF8F6 |
| Chapter II | F:/Draft_Chapter_II_Revised_Dehing_Followup.docx | Modified 2026-07-24 16:22; SHA-256 CDA2FEE7444F5489E4A460CA1231E6077BEBD4F449CD2D686F41F4869FCB8098 |
| Presentation | F:/Cybercase Framework - Interactive case and report generation.pdf | Created 2026-06-17; 14 pages; SHA-256 703B27A480DB8A2413CA3342BF6444EE821D37E68AC441A7DD7037701F837DDB |

F:/Draft.docx is an obsolete May 2026 Chapter II ancestor. F:/Cybercase Framework_edited (1).pdf is an older deck that still claims Thai-law retrieval and law-technique validation not present in the current code; archive it rather than using it as a source of truth.

### Chapter I: Chapter_I_Final.docx

Keep:

- the cybersecurity/CTI motivation;
- ATT&CK and RAG as product context;
- the need for bounded human clarification;
- the May-Nov high-level project period.

Revise:

- Replace a generic raw case narrative with a frozen multi-artifact case packet as the research unit.
- Replace claims that the current system already generates high-fidelity verified forensic reports with the measurable aim of producing provisional, examiner-verifiable drafts.
- Separate the implemented chat/RAG prototype from the proposed case-file experiment.
- Remove or label as future any upload, formatted export, persistent report engine, case management, or dynamic evidence UI claim.
- Replace promises to eliminate hallucination, reduce false positives, or improve accuracy with measurable evaluation questions.
- Treat the 5-10-user usability study as optional secondary work. It is not required for the paper's B0/B1 claim and should not displace double-scoring.
- Replace the old Gantt task Implement Follow-up Module and Integration Testing with the phases in this plan.

### Chapter II: Draft_Chapter_II_Revised_Dehing_Followup.docx

Keep:

- Dehing as method provenance for two-stage extraction/synthesis;
- evidence grounding, entity/role, chronology, and citation evaluation dimensions;
- the narrow one-clarification research motivation.

Revise:

- Change the scientific input from free-form incident information or chat-derived records to a frozen multi-artifact case packet.
- Replace schema-gated B1-F between Stage 1 and Stage 2 with the approved reduced FollowupQ-inspired B1 before the complete unchanged B0.
- Replace one target-slot question generator with three fixed candidate perspectives plus one bounded selector.
- Add FollowupQ as direct inspiration and clearly state that the implementation is reduced, not a reproduction.
- Change answer normalization into a Stage 2 field to a separately sourced supplemental investigator statement added before B0.
- Replace Trace ID as the study citation with dataset-neutral evidence_id plus source locators; retain Trace ID only when describing Dehing.
- Update RQ1-RQ3 and metrics to match required-finding recall, three-way claim support, locator accuracy, question match, and cost.

### Presentation: Cybercase Framework - Interactive case and report generation.pdf

Revise after Phase 5:

- Page 5 solution claims should distinguish implemented chat/RAG behavior from proposed case-file reporting.
- Page 8 scope should label structured reporting and case-file clarification as research implementation, not current production capability.
- Pages 9-10 architecture/user flow should show the isolated study path or clearly mark future components.
- Page 11 expected benefits should become expected or evaluated outcomes, not asserted improvements.
- Page 12 Gantt should use the remaining August-November schedule above.

### Older deliverable package

Keep deliverables/cybercase-report-followup-gap-study only as an advanced/archival appendix. Do not use its Crystal Clear reproduction, CAM-LDS design, inter-stage B1, or product-oriented follow-up definitions as the active Bachelor experiment.

## 8. Validation matrix

| Risk | Automated check | Human/research check |
|---|---|---|
| Source drift | URL/version/hash validation | rights and redistribution review |
| Gold leakage | visibility/object-graph tests and phrase/locator scans | independent packet review |
| Broken provenance | evidence ID and locator resolver | examiner checks sampled source locations |
| B0/B1 drift | config/prompt/schema/model hash equality | protocol review |
| Oracle confound | selector has no gold object; release requires frozen match record | two-person blind target adjudication |
| Evidence inflation | three-way claim-support schema | scorer guidance and adjudication |
| Hidden retries | append-only run IDs and failure records | run-manifest review |
| Secret leakage | output redaction tests | manual artifact inspection |
| Correlated samples | aggregate by case | no significance claims |
| Product contamination | prohibited-import and production-diff checks | final scope review |

Planned commands after implementation:

    .\env_mitre\Scripts\python.exe -m pytest -q experiments\casefile_study\tests -p no:cacheprovider
    .\env_mitre\Scripts\python.exe -m experiments.casefile_study.validation --sources experiments\casefile_study\data\sources\source_manifest.json --packets experiments\casefile_study\data\packets --gaps experiments\casefile_study\data\gaps --require-hashes --require-rights --check-locators --check-no-gold-leakage
    .\env_mitre\Scripts\python.exe -m experiments.casefile_study.runner --conditions b0 b1 --repeats 3
    .\env_mitre\Scripts\python.exe -m experiments.casefile_study.analysis --require-two-scorers --aggregate-by-case
    rg -n "analysis_prompt|chat_worker|rag_client|followup_pilot|buildChatDemoReport" experiments\casefile_study
    rg -n -i "Crystal Clear|NFI" experiments\casefile_study\data
    git diff --check
    git status --short --branch
    git diff -- backend frontend rag_service docker-compose.yml experiments/followup_pilot

Expected meaning:

- the prohibited-import search returns no matches;
- Crystal Clear/NFI appears in related-work metadata only, never case packets;
- the production-path diff remains identical to the recorded starting dirty baseline.

## 9. Risks and mitigations

| Risk | Likelihood/impact | Mitigation |
|---|---|---|
| CASE or CFReDS derivative rights remain unclear | medium/high | stop at Phase 1; use links and hashes; replace the source rather than assume permission |
| Raw forensic preprocessing becomes the project | high/high | evaluate examiner-curated packets; no OCR/raw-disk extraction contribution |
| Public answer key leaks into visible input | medium/high | use it only for hidden findings and source-location review; leakage tests |
| B1 receives an answer oracle | medium/high | two-pass question freeze and blind target adjudication before release |
| Supplemental answer is treated as evidence | high/high | three-way support labels and separate statement identity |
| Current M365 preprompt biases cases | high/high | prohibit every production prompt/policy/RAG import |
| B0 changes between conditions | medium/high | byte-level configuration hashes and parity test |
| API inference is nondeterministic | high/medium | three repeats; record provider/model/decoding and all failures |
| Manual scoring is too large | medium/medium | double-score 36 primary reports; keep transfer separate and preregister any reduced scope |
| Thai claims exceed the data | high/high | English core only; translated condition is optional and separately labeled |
| Full product case-file integration expands scope | high/high | defer behind a separate product gate after research freeze |

## 10. Optional future product gate

Do not begin this work as part of the core Bachelor experiment.

If the study succeeds and a product case-file workflow is explicitly approved, plan a separate architecture project for:

- authentication, ownership, and access logging;
- durable case, source-file, evidence-segment, clarification, and report models;
- safe file intake, MIME/size checks, malware scanning, encrypted object storage, and retention;
- durable parsing/OCR jobs outside FastAPI BackgroundTasks;
- immutable case versions and source-span identifiers;
- case-bound clarification state;
- backend-owned report sessions, validation, revisions, export, and claim-to-source links;
- durable retrieval snapshots;
- new migrations, route-surface expectations, frontend states, and security tests.

That work would materially change the system pipeline:

    case upload
      -> secure object storage
      -> durable extraction job
      -> immutable case/evidence snapshot
      -> case-bound clarification
      -> evidence and knowledge retrieval
      -> backend report generation and validation
      -> persisted versioned report
      -> review/export UI

It is a separate product feature, not a prerequisite for the controlled thesis/paper experiment.

## 11. Definition of done

The implementation is complete only when:

1. Source rights, versions, hashes, and redistribution decisions are frozen.
2. Six CFReDS gaps and two CASE transfer gaps pass schema, locator, and leakage checks.
3. B0 emits validated, locator-bearing provisional reports.
4. B1 uses one visible-evidence-only question and then byte-identical B0.
5. Every run and failure is append-only and reproducible.
6. Primary reports are blind double-scored and agreement/adjudication is retained.
7. Results are aggregated by case and reported descriptively.
8. Thesis and paper claims map to actual code, data, and result artifacts.
9. Production code and the user's pre-existing dirty changes remain untouched.
10. No result is claimed before the corresponding artifact exists.
