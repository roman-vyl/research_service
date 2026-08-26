# Tasks: Research History Window Planning v1

## Status

Partially implemented. Research Service's own range-resolution and Market
Data Service acquisition slice is done and reconciled into
`research-single-instance-backtest-v1` (2026-08-26 reconciliation pass, see
below). The Strategy Engine warmup/history-policy half and the coordinated
three-service rollout remain not started.

## Cross-repository audit

- [x] Re-audit Research Service run/config range policies and Workbench
      chart-window behavior. Evidence: `ResolveBacktestWindow`
      (`src/research_service/application/backtests/history_window.py`),
      `SingleInstanceBacktestRequest.range_policy`
      (`src/research_service/application/backtests/contracts.py`); EMA-window
      origin still uses first-request start, unchanged
      (`research-market-ema-window-v1`).
- [ ] Re-audit current MDS stream-state and available-boundary storage
      contracts. Out of scope for this repo — Research's `HttpMarketDataClient`
      assumes a `/v1/streams/{ticker}/{timeframe}/bounds` and
      `/v1/streams/{ticker}/{timeframe}/continuity-audits` contract, but MDS's
      own implementation was not audited from this repository.
- [ ] Re-audit Strategy Engine FeaturePlan, HTF alignment, lookbacks and state
      replay requirements. Not started; out of scope for this repo.
- [ ] Produce a cross-service request/response and error-mapping matrix.

## Market Data Service

- [ ] Add a focused stream-coverage application query and read port. Not
      verified from this repo.
- [ ] Add the canonical coverage HTTP endpoint. Not verified from this repo.
- [ ] Return state and exclusive available boundaries from one consistent
      snapshot. Not verified from this repo.
- [ ] Add ready/non-ready/unknown-stream contract tests. Not verified from
      this repo.
- [ ] Add OpenAPI and documentation. Not verified from this repo.

## Strategy Engine

- [ ] Add `history_policy` to range-evaluation contracts. Confirmed not
      implemented: `StrategyEvaluationRequest` carries no `history_policy`
      field (`src/research_service/domain/contracts.py`).
- [ ] Implement deterministic required-history derivation from FeaturePlan and
      strategy component lookbacks.
- [ ] Query MDS coverage before requesting expanded candles.
- [ ] Separate requested evaluation range from market-input range.
- [ ] Crop public feature/decision arrays to the requested evaluation range.
- [ ] Add `requested_range`, `market_input_range`, `valid_from_ms` and warmup
      metadata.
- [ ] Add structured `insufficient_history` handling.
- [ ] Add golden tests for base indicators, HTF completion, lookbacks and
      stateful components.

## Research Service

- [x] Add explicit evaluation-range policy models. Evidence:
      `SingleInstanceBacktestRequest.range_policy: Literal["explicit_range",
      "full_available"]`, `ResolvedBacktestWindow`, `StreamBounds`,
      `ContinuityAudit` (`application/backtests/history_window.py`).
- [x] Implement `full_available` by resolving MDS coverage into a concrete
      range. Evidence: `ResolveBacktestWindow.execute` calls
      `MarketDataPort.get_bounds` for `full_available` and verifies the
      resolved range through `audit_range`. Test:
      `test_full_available_resolved_market_reaches_every_downstream_stage`
      (`tests/test_single_instance_backtest.py`).
      Fixed during this reconciliation pass: the resolved window previously
      reached Strategy Engine range evaluation and historical candle
      acquisition but leaked the original *requested* (pre-resolution) range
      into managed-replay requests — invisible under `explicit_range` (the
      two ranges coincide) and untested under `full_available` (no test used
      that policy at all before this pass). Fixed in
      `RunSingleInstanceBacktest._managed_provider`.
- [ ] Stop using first-request origin as the final EMA-origin contract.
      Confirmed not implemented: `ema_window.py` and its current spec both
      still document `calculation_origin_ms` as the first requested range
      start.
- [ ] Pass history policy to Strategy Engine. Not implemented — no
      `history_policy` is sent (see Strategy Engine section above).
- [x] Verify strategy market-data hashes against simulation MarketFrame
      hashes. Evidence: `accept_strategy_execution_contract`
      (`application/backtests/strategy_contract.py`) rejects a mismatched or
      missing `market_data_hash` on either side.
- [ ] Preserve Workbench DTOs while correcting coverage/origin metadata. Not
      started — no origin-metadata correction exists yet to preserve DTOs
      around.

## Acceptance

- [ ] Run real MDS + Strategy Engine + Research Service container
      integration.
- [ ] Verify full-history and explicit-range runs. Unit-level equivalent now
      exists (`test_full_available_resolved_market_reaches_every_downstream_stage`,
      `test_single_instance_backtest_composes_all_layers`), but no real
      three-service integration run.
- [ ] Verify insufficient-history behavior under both policies. Not
      applicable yet — `require_fully_warmed`/`allow_partial_warmup` do not
      exist.
- [ ] Verify canonical EMA origin after cold start and cache restart.
- [ ] Benchmark representative chart, one-year and full-history requests.
- [ ] Update all three repository master plans and archive the coordinated
      OpenSpecs.


## Historical read activation

Done for the Research Service side: `RunSingleInstanceBacktest` uses
`MarketDataPort.read_historical_range` with `expected_market_data_hash` for
its execution frame (`application/backtests/run_backtest.py`); runtime
`GET /v1/candles` (`MarketDataPort.read_range`) is not used by backtest
orchestration — it remains wired only to the BFF chart routes
(`candles-window`, `chart-bundle`, and their compatibility aliases). No
hidden warmup/pre-roll or repair is introduced by this path.
