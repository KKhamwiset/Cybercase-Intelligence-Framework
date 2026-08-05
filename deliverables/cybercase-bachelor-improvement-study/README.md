# One Clarification Before Cyber-Investigative Case-File Drafting

## Recommendation

Study one bounded clarification before an unchanged published reporting baseline. The scientific unit is a frozen **cyber-investigative case file (สำนวนคดี)**: a mandate, exhibit register, acquisition/provenance records, and multiple evidence artifacts. It is not a chat transcript.

- **B0:** adapt Dehing et al.'s two-stage extraction/synthesis workflow to the frozen packet. Every extracted item uses dataset-neutral `evidence_id` and `source_locator` fields. The output is a provisional investigative report draft that still requires examiner verification.
- **B1:** run one reduced FollowupQ-inspired clarification step first, using the fixed perspectives entity/role, chronology, and evidence/citation. Generation and filtering never see hidden gold. If the selected question matches a preregistered target, add a separately identified and sourced `supplemental_investigator_statement`; then run the exact unchanged B0. Otherwise run B0 without a supplement.

This is a Bachelor-sized adaptation and evaluation, not a new mechanism and not a faithful reproduction of FollowupQ.

## Data decision

The primary source is the [NIST CFReDS Data Leakage Case](https://cfreds-archive.nist.gov/data_leakage_case/data-leakage-case.html), which provides a scenario, multiple exhibits, acquisition details and hashes, 60 investigation questions, and a public answer key. Six missing-finding conditions will be preregistered from one frozen case-file packet. A small secondary transfer uses the [CASE Owl Trafficking narrative and JSON-LD](https://caseontology.org/examples/owl_trafficking/) for two gaps without requiring the full raw corpus.

NFI Crystal Clear is excluded as experimental data: its chat-transcript modality does not represent a multi-artifact investigative dossier. It may appear only as provenance for Dehing-style method choices and in related work. Thai Police Open Data is aggregate motivation, not case-level evidence; no verified open Thai dossier corpus was found.

## Shared thesis and paper experiment

The thesis covers the system boundary, source preparation, implementation, and full evaluation. The paper tells only the narrow paired B0-versus-B1 story. Both use the same experiment, the same preregistered metrics, and no product output as research evidence. No experiment has been run and this package contains no results.

## Package

- [Bachelor research plan](bachelor_research_plan.md)
- [Implementation plan and timeline](implementation_plan.md)
- [Dataset and experiment plan](dataset_and_experiment_plan.md)
- [Paper story](paper_story.md)
- [Project inventory](project_inventory.md)
- [Dataset source manifest](dataset_source_manifest.json)
- [References](references.bib)

## Next actions

1. Record exact source versions, files, hashes, and reuse terms without redistributing raw images.
2. Freeze one CFReDS packet and one small CASE transfer packet; preregister six plus two missing-finding conditions and acceptable question targets.
3. Implement B0 and B1 only under `experiments/`, keeping B0 identical between conditions.
4. Run paired evaluation, preserve prompts/raw outputs/scoring, and report descriptive differences only.
