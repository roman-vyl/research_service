## Why

BBB AutoResearch's B1/B2 stages need a deterministic derived metric that combines trade count and
win rate into a single risk-outcome scalar, `cumulative_risk_outcome` (ΣR = N * (2*WR - 1)), so the
researcher can cite it as canonical evidence when comparing candidates. This is a pure function of
facts already computed once per candidate (`realised_trade_count`, `win_rate`) and must live exactly
where those facts already live, not as a new artifact, evidence kind, or memory mechanism.

## What Changes

- Compute `cumulative_risk_outcome` (aggregate, `long`, `short`) inside
  `research_service/application/experiments/candidate_summary.py`, at the exact point `trades` count
  and `win_rate` are already computed for a completed candidate and for each side.
- Add `cumulative_risk_outcome: Decimal` to `BatchSideSummary` and `BatchCandidateResult`
  (`research_service/application/experiments/contracts.py`) -- minimal extension of the existing,
  strictly-typed (`extra="forbid"`) models; no parallel structure, no new model, no new artifact file.
  Required when `status == "completed"`, forbidden when `status == "failed"`, matching the existing
  `_SUMMARY_FIELDS` / `_SUMMARY_FIELDS_REQUIRED_ON_COMPLETION` pattern.
- Extend `CANONICAL_METRIC_PATHS` in `scripts/autoresearch_quality_contracts.py` with
  `cumulative_risk_outcome`, `long.cumulative_risk_outcome`, `short.cumulative_risk_outcome`, so
  `EvidenceRef` (`kind: canonical_metric`) can cite the new paths. No new evidence kind; `_metric()`
  needs no change (schema-agnostic dict walk).

Because `run_batch_experiment.execute()` produces the same `BatchExperimentResult` instance that both
`persist_batch_experiment.execute()` hashes into the canonical `summary.json`/`manifest.json` and the
harness (`scripts/autoresearch_execute_batch.py`) dumps into `execution_output.json`, computing ΣR at
this single source point makes it appear consistently in both artifacts from one formula, one call
site -- no double computation, no drift.

## Capabilities

### Modified Capabilities
- `research-batch-experiments-v1`: `BatchSideSummary` and `BatchCandidateResult` gain a
  `cumulative_risk_outcome` field, deterministically derived from `trades`/`win_rate` at candidate-
  summary construction time.

Note: `CANONICAL_METRIC_PATHS` (the `EvidenceRef.metric_path` allowlist in
`scripts/autoresearch_quality_contracts.py`) is not governed by any existing capability spec -- no
spec documents the allowlist mechanism itself. Extending it with the three new paths is an
implementation detail of this same change (see Impact), not a separate spec-level behavior change.

## Impact

- `src/research_service/application/experiments/candidate_summary.py` (new pure derivation function,
  wired into `_side_summary` and `derive_batch_candidate_summary`).
- `src/research_service/application/experiments/contracts.py` (`BatchSideSummary`,
  `BatchCandidateResult`, `_SUMMARY_FIELDS*`).
- `scripts/autoresearch_quality_contracts.py` (`CANONICAL_METRIC_PATHS`).
- No change to Research Service's public API surface, persistence format version, prompts,
  `program.md`, `MetricRoles` priorities, or any other AutoResearch scientific-methodology contract.
