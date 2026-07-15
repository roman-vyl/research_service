# Tasks: Research History Window Planning v1

## Status

Deferred until the end of the current Research Service cutover program.

## Cross-repository audit

- [ ] Re-audit current MDS stream-state and available-boundary storage contracts.
- [ ] Re-audit Strategy Engine FeaturePlan, HTF alignment, lookbacks and state replay requirements.
- [ ] Re-audit Research Service run/config range policies and Workbench chart-window behavior.
- [ ] Produce a cross-service request/response and error-mapping matrix.

## Market Data Service

- [ ] Add a focused stream-coverage application query and read port.
- [ ] Add the canonical coverage HTTP endpoint.
- [ ] Return state and exclusive available boundaries from one consistent snapshot.
- [ ] Add ready/non-ready/unknown-stream contract tests.
- [ ] Add OpenAPI and documentation.

## Strategy Engine

- [ ] Add `history_policy` to range-evaluation contracts.
- [ ] Implement deterministic required-history derivation from FeaturePlan and strategy component lookbacks.
- [ ] Query MDS coverage before requesting expanded candles.
- [ ] Separate requested evaluation range from market-input range.
- [ ] Crop public feature/decision arrays to the requested evaluation range.
- [ ] Add `requested_range`, `market_input_range`, `valid_from_ms` and warmup metadata.
- [ ] Add structured `insufficient_history` handling.
- [ ] Add golden tests for base indicators, HTF completion, lookbacks and stateful components.

## Research Service

- [ ] Add explicit evaluation-range policy models.
- [ ] Implement `full_available` by resolving MDS coverage into a concrete range.
- [ ] Stop using first-request origin as the final EMA-origin contract.
- [ ] Pass history policy to Strategy Engine.
- [ ] Verify strategy market-data hashes against simulation MarketFrame hashes.
- [ ] Preserve Workbench DTOs while correcting coverage/origin metadata.

## Acceptance

- [ ] Run real MDS + Strategy Engine + Research Service container integration.
- [ ] Verify full-history and explicit-range runs.
- [ ] Verify insufficient-history behavior under both policies.
- [ ] Verify canonical EMA origin after cold start and cache restart.
- [ ] Benchmark representative chart, one-year and full-history requests.
- [ ] Update all three repository master plans and archive the coordinated OpenSpecs.


## Historical read activation

After a successful audit, Research SHALL use `POST /v1/historical-candles` for its execution frame and SHALL pass the same `expected_market_data_hash` to Strategy Engine. Runtime `GET /v1/candles` is not used by backtest orchestration. No hidden warmup/pre-roll or repair is introduced.
