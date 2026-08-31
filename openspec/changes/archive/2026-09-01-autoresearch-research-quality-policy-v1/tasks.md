## 1. Versioned contracts

- [x] Add exact JSON schemas for `bbb_research_quality_policy.v1` and
      `bbb_research_quality_assessment.v1`.
- [x] Introduce explicit v2 enclosing iteration/state/journal contracts; do not silently extend the
      exact v1 documents.
- [x] Define explicit compatibility behavior for existing v1 sessions and any operator-driven
      migration path.

## 2. Session policy and worker program

- [x] Extend initialization/template handling to persist one fully resolved immutable quality
      policy with provenance and phase bindings.
- [x] Update the operational program/prompt to require stage-aware metric roles, four-layer quality
      assessment, side classification, trade-off summary, and promotion blockers.
- [x] Keep the EMA skill referenced and unchanged.

## 3. Mechanical supervisor enforcement

- [x] Validate exact policy and assessment shapes, stage binding, evidence references, and durable
      advancement.
- [x] Enforce structural gates for entry into exit-geometry research, positive after-cost semantics
      for promotion out of exit geometry and later/final viability, canonical metric consistency,
      configured thresholds, neighborhood support, side-policy restrictions, and required
      validation.
- [x] Ensure null optional thresholds create no implicit gate and that the supervisor never ranks
      candidates or computes a weighted score.

## 4. Durable knowledge

- [x] Persist full quality assessments in iteration/journal history and compact latest assessment
      plus promotion history in state.
- [x] Preserve losing but informative experiments, rejected regions, validation failures, and
      `NO_STABLE_EDGE` conclusions.

## 5. Verification

- [x] Add contract and supervisor negative tests for every hard invariant and configured gate.
- [x] Add acceptance tests for all scenarios in this capability, including phase-specific metric
      meaning and no-winner behavior.
- [x] Run targeted AutoResearch tests, `make verify`, `openspec validate --all --strict`, and
      `git diff --check` during implementation.

## 6. Explicitly out of scope

- [x] Do not modify `src/research_service/**`, Strategy Engine, MDS, accounting/execution/backtest
      semantics, or the EMA component/skill as part of this policy layer.
- [x] Do not add weighted scoring, optimizer/search frameworks, automatic parameter ranking, or
      deletion of negative evidence.
