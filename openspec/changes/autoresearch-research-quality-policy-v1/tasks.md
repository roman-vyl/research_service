## 1. Versioned contracts

- [ ] Add exact JSON schemas for `bbb_research_quality_policy.v1` and
      `bbb_research_quality_assessment.v1`.
- [ ] Introduce explicit v2 enclosing iteration/state/journal contracts; do not silently extend the
      exact v1 documents.
- [ ] Define explicit compatibility behavior for existing v1 sessions and any operator-driven
      migration path.

## 2. Session policy and worker program

- [ ] Extend initialization/template handling to persist one fully resolved immutable quality
      policy with provenance and phase bindings.
- [ ] Update the operational program/prompt to require stage-aware metric roles, four-layer quality
      assessment, side classification, trade-off summary, and promotion blockers.
- [ ] Keep the EMA skill referenced and unchanged.

## 3. Mechanical supervisor enforcement

- [ ] Validate exact policy and assessment shapes, stage binding, evidence references, and durable
      advancement.
- [ ] Enforce positive after-cost promotion semantics, canonical metric consistency, configured
      thresholds, neighborhood support, side-policy restrictions, and required validation.
- [ ] Ensure null optional thresholds create no implicit gate and that the supervisor never ranks
      candidates or computes a weighted score.

## 4. Durable knowledge

- [ ] Persist full quality assessments in iteration/journal history and compact latest assessment
      plus promotion history in state.
- [ ] Preserve losing but informative experiments, rejected regions, validation failures, and
      `NO_STABLE_EDGE` conclusions.

## 5. Verification

- [ ] Add contract and supervisor negative tests for every hard invariant and configured gate.
- [ ] Add acceptance tests for all scenarios in this capability, including phase-specific metric
      meaning and no-winner behavior.
- [ ] Run targeted AutoResearch tests, `make verify`, `openspec validate --all --strict`, and
      `git diff --check` during implementation.

## 6. Explicitly out of scope

- [ ] Do not modify `src/research_service/**`, Strategy Engine, MDS, accounting/execution/backtest
      semantics, or the EMA component/skill as part of this policy layer.
- [ ] Do not add weighted scoring, optimizer/search frameworks, automatic parameter ranking, or
      deletion of negative evidence.
