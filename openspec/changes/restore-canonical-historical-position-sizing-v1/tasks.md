# Tasks: Restore Canonical Historical Position Sizing v1

## 1. Contract and ownership cutover

- [x] Remove caller-selectable fixed quantity from canonical historical `ExecutionPolicy` request semantics for single-instance and batch candidates.
- [x] Keep slippage and price/protection anchors in `ExecutionPolicy`; add no parallel fixed/equity canonical mode.
- [x] Confirm Strategy Engine ports, DTOs, and requests remain free of equity, notional, quantity, fees, and sizing policy.
- [x] Update request serialization, OpenAPI, persisted request fixtures, and validation tests atomically with the contract change.

## 2. Acyclic lifecycle seam

- [x] Introduce a pure Research-owned full-current-equity sizing service accepting current equity, actual entry fill price, and proportional entry fee rate.
- [x] Split entry-price resolution from final `EntryFill` construction so quantity is calculated after side-aware slippage and before the fill is recorded.
- [x] Refactor the canonical projection materializer into a sequential lifecycle coordinator that owns current realised equity and ordered trade records.
- [x] Expose/reuse a closed-position accounting kernel so the coordinator can account each close immediately without execution importing accounting.
- [x] Preserve `EntryDecision` as an equity/quantity-free decision fact and `EntryFill` as the execution fact carrying final quantity.
- [x] Build final `ExecutionLoopResult` and `TradeAccountingResult` from the same sequential lifecycle without re-accounting trades a second time.

## 3. Financial semantics

- [x] Under the existing proportional-fee/no-fixed-fee assumptions, implement `quantity = current_available_equity / (actual_entry_fill_price * (1 + entry_fee_rate))` with Decimal arithmetic.
- [x] Apply the vectorbt-grounded positive-quantity formula to long and short, with existing adverse slippage direction and side-aware execution/PnL behavior.
- [x] Calculate entry fee from entry notional for sizing and carry it into realised net PnL; calculate exit fee only from the actual exit fill at close.
- [x] Advance current equity after each close before sizing any later entry.
- [x] Preserve open-at-range-end behavior without a synthetic close or fabricated equity update.

## 4. Fail-closed invariants

- [x] Reject non-finite/non-positive initial or current equity, fill price, quantity, or notional.
- [x] Reject missing/inconsistent closed-position, fee, PnL, and equity-chain facts.
- [x] Reject non-finite/non-positive next realised equity without clipping, fallback quantity, or partial candidate success.
- [x] Preserve batch failure isolation between candidates while failing the invalid candidate atomically.

## 5. Shared-path proof

- [x] Add the first-entry example proving `10000 / 50000 = 0.2` at zero entry fee.
- [x] Add long/short tests proving slippage changes actual fill price before quantity calculation and non-zero entry fees reduce quantity using the all-in denominator.
- [x] Add multi-trade tests proving fees/PnL update the equity and quantity of the next position.
- [x] Add single-versus-batch equivalence tests for execution quantities, notionals, fees, PnL, trades, and final equity.
- [x] Add an AutoResearch boundary test proving it delegates sizing to canonical `RunBatchExperiment` results.
- [x] Extend old-BBB/vectorbt-grounded parity fixtures and comparison surfaces to the canonical sizing/equity chain, including non-zero proportional fees on both long and short.

## 6. Acceptance

- [x] Run focused entry, execution lifecycle, accounting, single-instance, batch, AutoResearch, and parity tests.
- [x] Run `make verify`.
- [x] Run `openspec validate restore-canonical-historical-position-sizing-v1 --strict`.
- [x] Run `openspec validate --all --strict`.
- [x] Confirm no second canonical `qty=1` mode or Strategy Engine sizing knowledge exists.
