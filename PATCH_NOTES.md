# Patch notes

## research-diagnostics-projection-v1

- Added immutable-run signal trace and chart events BFF projections.
- Strategy evidence is projected without recalculation.
- Research execution events add actual fill/lifecycle markers.
- Added context overlay selection, window slicing and stable validation.
- Step 15 of 18 is complete.

# Research initial protection v1

This cumulative repository:

- preserves the authoritative function-by-function rebuilding plan;
- implements `research-entry-execution-v1`;
- implements `research-initial-protection-v1`;
- adds immutable `InitialProtection` attached to `PositionState`;
- restores the reviewed legacy `entries & stop_ready` entry gate;
- converts Strategy Engine stop/take ratios into long/short absolute Decimal levels;
- anchors `bbb_v1` protection to the signal-bar close, matching legacy VectorBT and managed-loop behavior;
- preserves absent stop/take rules;
- adds acceptance tests without executing `legacy_source`.

Deferred: static exit hit detection/arbitration, managed policy consumption, accounting, artifacts and full backtest orchestration.


## research-static-exit-arbitration-v1

- Added static SL/TP/signal candidate collection.
- Preserved gap-at-open, touch-at-level and signal-at-close fills.
- Preserved same-bar priority and losing-candidate diagnostics.
- Added 7 acceptance tests; full suite is 53 passing.

## research-unified-exit-arbitration-v1

- combined static and managed exit candidates;
- preserved exact BBB v1 priority;
- applied `disable_initial_tp` semantics;
- preserved winning candidate attribution on `ExitFill`;
- removed regressed shadow/cutover wording from active plans.


## research-trade-accounting-v1

- added modular `accounting/contracts.py` and `accounting/service.py`;
- calculates actual-fill notionals, entry/exit fees, side-aware gross/net PnL and realised equity;
- calculates MFE/MAE, capture ratio and giveback from entry through exit inclusive;
- leaves final open positions unrealised;
- full suite is 73 passing.

## research-single-instance-backtest-v1

- Added authoritative one-instance orchestration.
- Composed Strategy Engine, MDS, execution-contract acceptance, unified execution and accounting.
- Added managed replay request construction per opened position.
- Added immutable `research_single_instance_backtest.v1` result.


## research-run-artifacts-v1

- Added atomic immutable run-directory publication under `var/runs/<run_id>/`.
- Added versioned manifest with contract provenance, market-data hash, SHA-256 and byte sizes.
- Persisted request, strategy evaluation, execution events, trades, metrics and full result.
- Prevented overwrite of existing run IDs and cleaned failed temporary bundles.


## research-backtest-api-v1

- Activated `POST /api/research/backtests`.
- Added synchronous run + atomic persistence composition.
- Added compact versioned completion response.
- Added stable HTTP 409 conflict for duplicate immutable run IDs.
- Removed the obsolete preserved 501 route.

## research-batch-experiments-v1

- Added immutable ordered batch request/result contracts.
- Runs candidates strictly sequentially over the authoritative single-instance backtest path.
- Isolates one candidate failure and continues later candidates.
- Reuses atomic per-run artifacts and publishes an immutable batch summary under `var/runs/batches/<experiment_id>/`.
- Adds comparison-level accounting totals and market-data provenance without embedding full run payloads.
- Full suite is 88 passing.


## research-results-bff-v1

- Activated list/latest/detail/summary/trades/metrics routes over new immutable run bundles.
- Added manifest SHA-256 and size verification before projecting artifacts.
- Removed regressed transitional migration language from active planning documents.
