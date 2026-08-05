# Paper Story

## Working title

**One Question Before Synthesis: Evaluating Report-Critical Clarification for Evidence-Bound Cyber Incident Reports**

## Thesis

We study whether adding exactly one schema-gated, report-critical clarification to a fixed external two-stage reporting method recovers supported claims or exact ATT&CK mappings when one answerable fact is missing, while characterizing question burden and paired downstream changes when evidence is sufficient or explicitly unavailable.

## Task boundary

- **Fidelity input/output:** the frozen NFI Crystal Clear chat corpus, ten released parts, exact upstream prompts/schema, and Trace-ID report. This is B0-reproduction only.
- **External input:** a schema-valid versioned cyber case with immutable evidence spans and one of three case kinds: eligible-masked, sufficient, or explicitly-unknown.
- **External output:** a fixed adapted report containing atomic claims, timeline events, exact ATT&CK decisions, and source/answer lineage.
- **Treatment:** B1 adds one gate call and, only after a valid eligible ask, one canonical answer before the otherwise identical Stage 2 synthesis.
- **Out of scope:** wholesale multi-agent design, production case/report APIs, authentication, automatic source verification, real-world investigator productivity, and operational response automation.

## Gap

[Dehing et al.](https://research.rug.nl/en/publications/structured-report-generation-using-local-llms-for-chat-based-digi/) provide a reproducible two-stage chat-report method but no interaction for a report-critical missing fact. [Gatto et al.](https://arxiv.org/abs/2503.17509) generate and filter broad medical question pools, but RIM does not penalize extra questions and the task has much larger question burden. Neither evaluates a single cyber clarification by its necessity, target slot, resolution, and downstream report/ATT&CK change under matched gate-off controls.

## Method insight

Clarification is justified only when an absent, answerable incident fact can change a required output slot. The gate therefore optimizes decision value under a one-question budget rather than question diversity. Evidence lineage is held fixed so the only causal treatment is whether the gate may ask and then receive the canonical answer.

## Method and stratum separation

1. **B0-reproduction:** recompute released artifacts and freshly run one predeclared feasible model using the exact NFI prompts/schema. Add no ATT&CK output. Report fidelity separately.
2. **B0-external-adapted Stage 1:** extract ordered evidence into a fixed CAM-LDS-compatible representation.
3. **B1 gate:** inspect only Stage 1 and the fixed schema; ask zero or one question for one target slot.
4. **Resolution:** eligible cases receive the one canonical, provenance-tagged answer only after a valid ask. Sufficient and explicitly-unknown cases receive no answer.
5. **Matched Stage 2:** B0-external-adapted and B1 use the same model, synthesis prompt, schema, decoding, evidence lineage, and scorer.

The external method adapts source domain, identifiers, input representation, output schema, reference construction, prompts, and metrics from the publication. It is not a faithful NFI reproduction.

## Contributions

1. A bounded fidelity record for the published NFI method, kept outside the external causal analysis.
2. One treatment: a report-critical gate that may ask one question for one schema slot before synthesis.
3. A discriminated three-kind case contract and semantic validator that encode withholding, no-question controls, canonical answers, and answer-to-claim lineage.
4. A matched eight-row evaluation measuring gate selectivity, resolved-gap rate, supported claims, exact ATT&CK mappings, burden, and descriptive harm deltas.
5. A versioned dataset plan and annotation procedure that expose synthetic-data, generated-reference, and seven-cluster limitations.

## Research questions and hypotheses

- **RQ1 — Fidelity:** Can the NFI released scores/artifacts be recomputed and one primary-model B0 run be recreated under a recorded environment?
- **RQ2 — Gate quality:** On eligible cases, does B1 ask one necessary, answerable question for the correct slot; on controls, does it proceed?
- **RQ3 — Downstream effect:** Does B1 improve supported-claim F1 and exact ATT&CK accuracy versus matched B0-eligible-masked?
- **RQ4 — Harm:** What paired downstream and burden deltas arise when the gate is enabled on sufficient and explicitly-unknown inputs?

- **H1:** B1 has high necessity recall and target-slot accuracy on eligible cases and low unnecessary-question rates on both control kinds.
- **H2:** B1-eligible-clarified improves paired supported-claim F1 over B0-eligible-masked; ATT&CK accuracy is secondary.
- **H3 (descriptive objective only):** Estimate gate-on minus gate-off harm deltas on sufficient and explicitly-unknown cases and report all seven family effects without a near-zero threshold, equivalence margin, or safety hypothesis.

H1 and H2 are preregistered confirmatory directional hypotheses, not findings. H3 is a descriptive label rather than a confirmatory hypothesis; no equivalence test or safety claim is supported with seven families. There is no lineage ablation or second treatment.

## Evidence plan

- NFI prompt/schema/hash parity, released-artifact recomputation, and one fresh primary-model run for RQ1.
- CAM-LDS scenario-family grouped external cases; Attack Flow/TRAM only as declared supplements.
- Five repetitions per external row, one fixed primary model, blinded claim/gate adjudication, exact-ID ATT&CK scoring, and intention-to-treat failures.
- Exact cluster-level sign permutation over seven scenario families for H2; H3 reports all seven paired family effects descriptively, with no equivalence test or safety conclusion. Do not pool either with the single NFI case.

## Claims to make only after evidence

- The fidelity stratum did or did not reproduce specified upstream properties.
- B1 changed preregistered gate/report/ATT&CK metrics relative to B0-external-adapted.
- Any effect is limited to the frozen synthetic datasets, model, prompts, schema, and annotation protocol.

## Claims to avoid

- B0-external-adapted is a faithful reproduction of Dehing.
- CyberCase already implements B0 or the research B1 gate.
- Lineage guarantees truth.
- One synthetic pilot proves clarification effectiveness.
- B1 improves real-world forensic accuracy, analyst productivity, trust, or incident response.
- Novelty comes from RAG, agents, HITL, ATT&CK, report rendering, or follow-up questions alone.

## Bachelor scope

Keep one fidelity run, one external primary model, one treatment, one question maximum, one adapted schema, three case kinds, seven family-level inference groups, and a manageable adjudicated case set. Optional all-five-model reruns and telemetry holdouts are robustness work, not completion requirements.

## Reviewer risks

- Adaptation drift could be mistaken for reproduction; report strata separately.
- Seven inference groups yield coarse p-values and limited power.
- Synthetic data and human-derived masks may not reflect analyst uncertainty.
- A generated NFI reference and adjudicated external gold have different error modes.
- One-question gains may be offset by latency, unnecessary asks, or downstream hallucination.
