# Known cross-service gaps

Last verified 2026-08-26 during the OpenSpec reconciliation pass (see
`openspec/changes/research-history-window-planning-v1/tasks.md` for the
full requirement-by-requirement matrix this summarizes).

## Open

- **Strategy Engine `history_policy` / warmup derivation.** Strategy Engine
  does not accept a `history_policy` and does not derive or report required
  warmup. Confirmed absent: `StrategyEvaluationRequest` carries no such
  field. UNVERIFIED_FROM_THIS_REPO whether Strategy Engine internally
  computes `market_data_hash` itself rather than accepting an MDS-supplied
  value — not audited from `research_service`.
- **Canonical EMA chart origin.** `research-market-ema-window-v1` still
  reports `calculation_origin_ms` as the first requested range start, not a
  true MDS-coverage-derived origin. Confirmed current behavior, not yet
  changed.
- **Coordinated three-service rollout.** The full `require_fully_warmed` /
  `allow_partial_warmup` policy, `market_input_range` vs. requested-range
  separation, and insufficient-history handling do not exist in any of the
  three services as far as this repo's contracts show. UNVERIFIED_FROM_THIS_REPO
  for the Market Data Service and Strategy Engine sides specifically.

## Resolved / confirmed (Research Service side, 2026-08-26)

- MDS-owned `market_data_hash` equality check — implemented and enforced:
  `accept_strategy_execution_contract` rejects a missing or mismatched hash
  between the Strategy Engine evaluation and the Market Data Service frame.
- Separate historical-backtest read path — implemented:
  `RunSingleInstanceBacktest` reads execution candles through
  `MarketDataPort.read_historical_range` (`POST /v1/historical-candles`
  with `expected_market_data_hash`); runtime `GET /v1/candles`
  (`read_range`) is used only by the BFF chart routes, never by backtest
  orchestration.
- `explicit_range` / `full_available` range resolution against MDS stream
  bounds and continuity audit — implemented and covered by regression
  tests (`ResolveBacktestWindow`,
  `test_full_available_resolved_market_reaches_every_downstream_stage`).
