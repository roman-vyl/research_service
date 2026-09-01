# Tasks: Restore Canonical Historical Position Sizing v1

## 1. Contract and ownership cutover

- [ ] Remove caller-selectable fixed quantity from canonical historical `ExecutionPolicy` request semantics for single-instance and batch candidates.
- [ ] Keep slippage and price/protection anchors in `ExecutionPolicy`; add no parallel fixed/equity canonical mode.
- [ ] Confirm Strategy Engine ports, DTOs, and requests remain free of equity, notional, quantity, fees, and sizing policy.
- [ ] Update request serialization, OpenAPI, persisted request fixtures, and validation tests atomically with the contract change.

## 2. Acyclic lifecycle seam

- [ ] Introduce a pure Research-owned full-current-equity sizing service accepting current equity and actual entry fill price.
- [ ] Split entry-price resolution from final `EntryFill` construction so quantity is calculated after side-aware slippage and before the fill is recorded.
- [ ] Refactor the canonical projection materializer into a sequential lifecycle coordinator that owns current realised equity and ordered trade records.
- [ ] Expose/reuse a closed-position accounting kernel so the coordinator can account each close immediately without execution importing accounting.
- [ ] Preserve `EntryDecision` as an equity/quantity-free decision fact and `EntryFill` as the execution fact carrying final quantity.
- [ ] Build final `ExecutionLoopResult` and `TradeAccountingResult` from the same sequential lifecycle without re-accounting trades a second time.

## 3. Financial semantics

- [ ] Implement `quantity = current_available_equity / actual_entry_fill_price` with Decimal arithmetic.
- [ ] Apply the same positive-quantity formula to long and short, with existing adverse slippage direction and side-aware PnL formulas.
- [ ] Keep entry and exit fees based on actual fill notionals and apply both through realised net PnL at close.
- [ ] Advance current equity after each close before sizing any later entry.
- [ ] Preserve open-at-range-end behavior without a synthetic close or fabricated equity update.

## 4. Fail-closed invariants

- [ ] Reject non-finite/non-positive initial or current equity, fill price, quantity, or notional.
- [ ] Reject missing/inconsistent closed-position, fee, PnL, and equity-chain facts.
- [ ] Reject non-finite/non-positive next realised equity without clipping, fallback quantity, or partial candidate success.
- [ ] Preserve batch failure isolation between candidates while failing the invalid candidate atomically.

## 5. Shared-path proof

- [ ] Add the first-entry example proving `10000 / 50000 = 0.2` without slippage.
- [ ] Add long/short tests proving slippage changes actual fill price before quantity calculation.
- [ ] Add multi-trade tests proving fees/PnL update the equity and quantity of the next position.
- [ ] Add single-versus-batch equivalence tests for execution quantities, notionals, fees, PnL, trades, and final equity.
- [ ] Add an AutoResearch boundary test proving it delegates sizing to canonical `RunBatchExperiment` results.
- [ ] Extend old-BBB/vectorbt-grounded parity fixtures and comparison surfaces to the canonical sizing/equity chain.

## 6. Acceptance

- [ ] Run focused entry, execution lifecycle, accounting, single-instance, batch, AutoResearch, and parity tests.
- [ ] Run `make verify`.
- [ ] Run `openspec validate restore-canonical-historical-position-sizing-v1 --strict`.
- [ ] Run `openspec validate --all --strict`.
- [ ] Confirm no second canonical `qty=1` mode or Strategy Engine sizing knowledge exists.
