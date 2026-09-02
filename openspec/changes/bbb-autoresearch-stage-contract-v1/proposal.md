## Why

BBB AutoResearch currently tells a worker which scientific stage it is in but cannot mechanically
prove that a planned candidate changed only the strategy dimension permitted by that stage. The
first controlled A→B programme needs an immutable canonical starting strategy, matched measurement
geometries, and fail-closed stage mutation boundaries so workers spend autonomy on research rather
than reconstructing or accidentally changing the experimental control.

## What Changes

- Introduce opt-in `bbb_autoresearch_state.v3` sessions with an immutable resolved starting-strategy
  snapshot and an immutable typed A→B stage contract.
- Load a checked-in canonical EMA-anchor starting-strategy fixture at initialization, validate it
  through the existing Research→Engine config-validation boundary, and freeze the resolved copy in
  session state so later fixture edits cannot mutate an active session.
- Define four typed stages: `A_BASELINE`, `B1_WIDTH`, `B2_LOOKBACK`, and
  `B3_WIDTH_X_LOOKBACK`, using only the semantic mutation dimensions
  `symmetric_measurement_geometry`, `anchor_stack_width`, and `untouched_anchor_lookback` rather
  than a generic JSONPath/mutation language.
- Make Phase A measure an operator-configured reference line of symmetric geometries, one geometry
  per experiment, using canonical `realised_trade_count` and `win_rate`; it neither searches new
  TP/SL values nor selects a preferred geometry.
- Require every B experiment to name one completed Phase-A `geometry_id`; all candidates must keep
  exactly that geometry while changing only the semantic dimensions allowed for the active stage.
- Require B1 and B2 to start independently from the naked starting strategy; B2 must not inherit a
  width mutation from B1. Permit B3 only after both independent investigations are durably closed,
  while leaving B3 optional and scientifically justified by the worker.
- Have the supervisor compare each candidate with the applicable immutable reference and reject
  out-of-scope changes, identity changes, geometry mismatches, or causal-order violations before
  canonical execution. It does not choose parameter values, characterize topology, rank candidates,
  judge uplift, or decide whether B3 is scientifically worthwhile.
- Preserve exact v1/v2 compatibility and all supervisor-owned execution, canonical-evidence,
  quality-policy, recovery, and no-scalar-winner boundaries.
- Refine the structural-entry methodology from one global fixed neutral exit to matched fixed
  symmetric measurement geometries: a geometry is immutable within each A↔B comparison and is not
  an exit-optimization target.

## Capabilities

### New Capabilities

None. The stage contract extends the existing BBB AutoResearch capability rather than creating a
parallel research product.

### Modified Capabilities

- `bbb-autoresearch-v1`: add the v3 session/stage contract, immutable starting strategy, typed
  semantic mutation enforcement, matched Phase-A geometry references, causal availability rules,
  and fail-closed candidate validation.
- `autoresearch-research-quality-policy-v1`: clarify phase-aware metric and neutral-exit semantics
  for an operator-configured line of matched symmetric measurement geometries without turning
  Phase A into exit optimization or changing later economic-promotion rules.

## Impact

- AutoResearch templates, schemas, initialization, planning context, supervisor validation, durable
  state/journal representation, and deterministic tests.
- One checked-in full canonical EMA100/EMA200/EMA500 starting-strategy fixture, retaining trigger,
  direction, exits, ticker/timeframe, component identity, and every other required field.
- The EMA-anchor methodology text only where needed to describe configured matched geometries and
  the A→B1→B2→optional-B3 causal ladder.
- Existing `scripts/autoresearch_execute_batch.py`, Research evaluator/application path, Strategy
  Engine/MDS contracts, accounting/execution semantics, and canonical batch facts remain unchanged.
  No successful-trade-count metric, generic mutation DSL, Phase C, B4, optimizer, or scalar score is
  introduced.
