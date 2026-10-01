## Why

Research Service's historical managed backtest in `main` (`5018ec8`)
still calls Strategy Engine `POST /v1/strategy-evaluations/managed-replay`
once per opened trade (`execution/projection_loop.py::_resolve_managed_timeline`)
and drops the `managed` projection Strategy Engine already sends in the
same `/range-batch` response.

The local consumer of that projection exists only on the unmerged branch
`historical-managed-projection-v1` (`3167831`). Strategy Engine's side is
the archived change `strategy_engine/openspec/changes/archive/2026-09-29-historical-managed-projection-v1`.
A 2026-09-30 audit (`/mnt/project-files/research-projection-cutover/audit.md`)
found four blockers on that branch relative to the canonical Strategy
Engine baseline `main` `07ff91150c2ca0fecf4e37fa483e98345cb7131b`
(PR #21, `composite-managed-phase-condition-v1`):

1. `ManagedPhaseTransitionRuleDTO` rejects the new `paths` variant
   (`extra="forbid"`), and the consumer has no path branch. Every
   `composite_phase_condition` candidate fails to decode.
2. With `managed_policy_enabled=False`, the new path still applies
   managed policy, because `_open_managed_state` checks `managed` before
   the caller's gating.
3. `managed_policy_events` is always empty on the new path, because
   events came only from `/managed-replay` responses.
4. OLD-vs-NEW parity (203/203 trades) and the performance numbers were
   measured against Strategy Engine `e95a252`, before PR #21, for atomic
   rules only. The harness that produced them was never committed.

This change finishes the cutover. It builds on the existing branch and
changes nothing in Strategy Engine.

## What Changes

- Decode the final projection contract: a `phase_transition` rule
  carries exactly one of `condition_id`, (`distance_id`, `trade_metric`)
  or `paths`. New generic DTOs cover `ManagedTransitionPath`,
  `ManagedTransitionThreshold`, `ManagedTransitionAtLeast` and
  `ManagedTransitionTerm`.
- Resolve `paths` in the incremental consumer (`advance_managed_trade_state`)
  and in the eager oracle builder through one shared phase-rule
  evaluator. The first true path in order wins, `path_id` is
  attributed, and NaN thresholds are false. The consumer still never
  reads a `component_id` or a component name.
- Mirror Strategy Engine's stop attribution: the active stop price and
  rule id change only when the tightened price moves by more than
  `1e-8`. This fixes an `exit_rule_id` divergence the old corpus never
  exercised.
- Honor `managed_policy_enabled=False` before choosing between the
  local and legacy implementations.
- Emit `ManagedPolicyEvent`s locally from the incremental consumer
  (`phase_changed`, `active_stop_updated`, `active_take_updated`,
  `runtime_exit_triggered`). They use the same trigger rules as
  Strategy Engine's `managed.py`, so the persisted
  `managed_policy_events.json` and its API stay meaningful after the
  cutover.
- Commit a reproducible OLD-vs-NEW parity harness
  (`scripts/managed_projection_parity.py`). It compares TradeRecords,
  accounting summary, candidate metrics and managed events, with an
  explicit list of allowed diagnostic differences.
- Commit a reproducible performance harness
  (`scripts/managed_projection_benchmark.py`). It records HTTP call
  counts per endpoint, Engine CPU, Research CPU, total CPU, wall time
  and trade count over several natural workloads.
- After both gates pass on the owner's command, merge the branch
  (existing 4 commits plus this change) into `main`.

**BREAKING**: none on the wire. The historical batch path stops
issuing `/managed-replay` calls. `/managed-replay` itself and the
legacy consumer stay available behind the explicit code-level oracle
opt-in `allow_legacy_managed_replay_fallback=True`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `research-managed-policy-consumption-v1`: the policy source for
  historical batch execution becomes Strategy Engine's candidate-wide
  `HistoricalManagedProjection`, executed locally. `/managed-replay`
  becomes the oracle only. The Attribution requirement is scoped to
  what each source carries. New requirements cover projection decoding
  (atomic and paths), managed gating, local event trace, and the
  parity and performance gates.

## Out of scope

- Any Strategy Engine change. The contract after PR #21 is sufficient.
- Removing `/managed-replay` (issue strategy_engine#19) or the eager
  oracle builder.
- Per-candidate isolation of malformed `/range-batch` stream elements.
  That is existing transport semantics and a separate batch-isolation
  question.
- A `Research CPU <= OLD Research CPU` criterion. Research now executes
  the trade lifecycle itself, so its own CPU may legitimately grow.
- New managed semantics (`mfe_r`, trailing stop, partial exits, etc.).

## Impact

- `src/research_service/domain/contracts.py`: path DTOs and the
  three-way XOR on `ManagedPhaseTransitionRuleDTO`.
- `src/research_service/execution/managed_policy.py`: shared phase-rule
  evaluator, stop attribution, and local event emission from
  `advance_managed_trade_state`.
- `src/research_service/execution/projection_loop.py`: gating order in
  `_open_managed_state`, and an event sink from the incremental path.
- `src/research_service/application/backtests/materialize_backtest_projection.py`:
  collects local events into `managed_policy_events`.
- `scripts/managed_projection_parity.py` and
  `scripts/managed_projection_benchmark.py`: new, operator-run only.
- Tests: new unit tests for paths, gating, stop attribution and events.
  The existing 361 tests stay green.
