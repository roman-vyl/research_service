# Design: Restore Canonical Historical Position Sizing v1

## 1. Decision

Canonical historical Research uses full-current-equity position sizing:

```text
available_equity := AccountingPolicy.initial_equity

for each position, sequentially:
  actual_entry_fill_price := side-aware adverse-slippage price
  quantity := available_equity / actual_entry_fill_price
  execute the position with that positive quantity
  on close:
    net_pnl := side-aware gross_pnl - entry_fee - exit_fee
    available_equity := available_equity + net_pnl
```

There is one canonical historical sizing behavior. `ExecutionPolicy.quantity = 1` is removed from canonical request semantics rather than retained as a selectable alternative.

With no entry slippage, `initial_equity = 10000` and first entry fill price `50000` produce `quantity = 0.2`. If slippage changes the actual fill price, quantity uses that changed price and therefore differs accordingly.

## 2. Ownership

Research Service owns quantity because it already owns actual fills, fees, PnL, and equity. Strategy Engine continues to provide strategy decisions and price-relative protection/exit facts only. Engine requests and responses carry no equity, notional, quantity, or sizing policy.

AutoResearch owns no sizing behavior. It submits canonical Research candidates and consumes canonical Research results through `RunBatchExperiment`.

## 3. Lifecycle placement and dependency direction

The current high-level shape materializes all execution facts first and calls `account_execution_loop` afterward:

```text
run_projection_execution_loop(..., ExecutionPolicy.quantity)
  -> ExecutionLoopResult
  -> account_execution_loop(..., AccountingPolicy)
```

That ordering cannot compound position size: the second entry is created before the first closed trade has updated equity.

The target shape is a Research application-layer historical lifecycle coordinator used by `MaterializeBacktestProjectionOutcome`:

```text
MaterializeBacktestProjectionOutcome
  owns current realised equity and ordered TradeRecords
  -> execution primitive: obtain EntryDecision/opportunity
  -> execution primitive: resolve actual slipped entry fill price
  -> pure Research sizing service: equity + fill price -> quantity
  -> execution primitive: create EntryFill/PositionState with quantity
  -> execution primitives: arbitrate/close position
  -> accounting kernel: closed PositionExecution + equity -> TradeRecord
  -> coordinator advances equity from TradeRecord.equity_after
  -> final aggregate ExecutionLoopResult + TradeAccountingResult
```

The coordinator imports execution primitives, the sizing service, and accounting primitives. Execution modules do not import accounting, and accounting modules do not call execution loops. This keeps dependency direction acyclic.

The existing `EntryDecision` remains a strategy/market decision fact and gains no equity or quantity. `EntryFill` remains the first durable execution fact carrying quantity. Entry construction is split conceptually into price resolution and fill finalization so sizing can occur after actual fill price is known but before `EntryFill` is created.

## 4. Sizing service

The sizing calculation lives in a small Research-owned pure service outside Strategy Engine and outside `ExecutionPolicy`. It accepts only:

- current available realised equity;
- actual entry fill price.

It returns positive Decimal quantity:

```text
quantity = current_available_equity / actual_entry_fill_price
```

It does not inspect strategy components, side, candles, fees, exits, or future bars. Side has already affected the actual fill price through entry slippage. Keeping this service separate prevents execution from depending on accounting while allowing the application coordinator to compose both.

## 5. Long and short semantics

Quantity is a positive magnitude for both sides.

```text
long actual entry  = reference_price * (1 + entry_slippage_rate)
short actual entry = reference_price * (1 - entry_slippage_rate)

long gross_pnl  = (exit_fill_price - entry_fill_price) * quantity
short gross_pnl = (entry_fill_price - exit_fill_price) * quantity
```

For either side, entry notional is `abs(entry_fill_price * quantity)` and equals the current available equity under the canonical formula. This is historical exposure sizing, not a new leverage or margin model.

## 6. Fees and equity timing

Entry and exit fees continue to use their actual fill notionals independently. Quantity uses current realised equity and actual entry fill price; it is not calculated from reference price and is not retrospectively changed by fees.

Consistent with the existing realised-equity contract, a closed trade applies both entry and exit fees through net PnL:

```text
entry_fee  = abs(entry_fill_price * quantity) * entry_fee_rate
exit_fee   = abs(exit_fill_price * quantity) * exit_fee_rate
net_pnl    = gross_pnl - entry_fee - exit_fee
next_equity = equity_before + net_pnl
```

The next entry is sized from `next_equity`. An open position at range end remains unrealised and does not fabricate a close or a next-equity update.

## 7. ExecutionPolicy and request migration

`ExecutionPolicy` remains the home of execution assumptions such as entry slippage and price/protection anchors. Fixed quantity is not an execution assumption for canonical historical Research and is removed from the canonical single-instance and batch candidate request shape.

Implementation may stage parsing changes atomically with callers and persisted request fixtures, but it must not silently accept a caller quantity and ignore it, nor expose a `fixed` versus `equity` canonical mode. If compatibility parsing is temporarily necessary during one commit series, it is migration scaffolding only, unreachable in the completed canonical contract and deleted before the acceptance gate.

## 8. Single, batch, and AutoResearch convergence

`MaterializeBacktestProjectionOutcome` is already the canonical per-run materializer shared by direct single-instance execution and every batch candidate. The sizing lifecycle is implemented there once.

- Single-instance calls the materializer directly.
- Batch calls the same materializer per candidate and retains failure isolation.
- AutoResearch calls `RunBatchExperiment` and therefore inherits identical semantics.

No batch-only or AutoResearch-only quantity calculation, equity ledger, or accounting branch is permitted.

## 9. Fail-closed financial invariants

The lifecycle rejects the candidate/run rather than defaulting, clipping, or continuing when any of the following occurs:

- initial or current available equity is non-finite or non-positive;
- reference price or actual fill price is non-finite or non-positive;
- calculated quantity or fill notional is non-finite or non-positive;
- a closed trade has missing/inconsistent fills, quantity, fee, PnL, or equity-chain facts;
- the next realised equity is non-finite or non-positive;
- a trade's `equity_before` does not exactly equal the coordinator's current equity.

Batch failure isolation still applies across candidates: the invalid candidate fails, later independent candidates may continue. Within one candidate, no impossible financial state is converted to `qty=1`, zero quantity, clipped equity, or a partial successful result.

## 10. Validation and parity evidence

Acceptance requires focused tests proving:

- first-entry example (`10000 / 50000 = 0.2` without slippage);
- side-aware slippage changes the denominator before sizing for long and short;
- long and short share the positive-quantity/notional formula;
- fees and realised PnL update the equity used by a later entry;
- multiple closed trades form an exact equity/quantity chain;
- single and batch produce identical execution/accounting for the same candidate;
- AutoResearch adds no sizing path;
- impossible financial states fail closed;
- old-BBB/vectorbt-grounded parity includes quantity, notionals, fees where configured, PnL, and equity evolution.

## 11. Rejected alternatives

### Keep `ExecutionPolicy.quantity = 1` as canonical

Rejected: it is the semantic defect being corrected and breaks capital-relative outcomes.

### Add `fixed` and `equity` canonical modes

Rejected: there is no independently proven need for two canonical historical meanings, and parallel modes would split parity, batch comparison, and AutoResearch semantics.

### Put equity in Strategy Engine

Rejected: Engine owns strategy decisions, not execution/account state.

### Run full accounting only after the execution loop

Rejected: later quantities cannot depend on earlier realised results.

### Make execution import accounting

Rejected: it creates the dependency cycle the application-layer lifecycle coordinator is intended to avoid.
