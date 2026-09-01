# Design: Restore Canonical Historical Position Sizing v1

## 1. Decision

Canonical historical Research uses full-current-equity position sizing:

```text
available_equity := AccountingPolicy.initial_equity

for each position, sequentially:
  actual_entry_fill_price := side-aware adverse-slippage price
  quantity := available_equity / (actual_entry_fill_price * (1 + entry_fee_rate))
  execute the position with that positive quantity
  on close:
    net_pnl := side-aware gross_pnl - entry_fee - exit_fee
    available_equity := available_equity + net_pnl
```

There is one canonical historical sizing behavior. `ExecutionPolicy.quantity = 1` is removed from canonical request semantics rather than retained as a selectable alternative.

With zero entry fee, `initial_equity = 10000` and actual first entry fill price `50000` produce `quantity = 0.2`. If slippage changes the actual fill price, quantity uses that changed price and therefore differs accordingly. With a non-zero proportional entry fee, entry notional is less than current equity because the fee must fit in the same all-in budget.

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
  -> pure Research sizing service: equity + fill price + entry fee rate -> quantity
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
- proportional entry fee rate.

It returns positive Decimal quantity:

```text
quantity = current_available_equity
           / (actual_entry_fill_price * (1 + entry_fee_rate))
```

It does not inspect strategy components, candles, exits, or future bars. It consumes the configured entry fee rate as an execution cost input; it does not calculate accounting results. Side has already affected the actual fill price through entry slippage. Keeping this service separate prevents execution from depending on accounting while allowing the application coordinator to compose both.

## 5. Long and short semantics

Quantity is a positive magnitude for both sides.

```text
long actual entry  = reference_price * (1 + entry_slippage_rate)
short actual entry = reference_price * (1 - entry_slippage_rate)

long gross_pnl  = (exit_fill_price - entry_fill_price) * quantity
short gross_pnl = (entry_fill_price - exit_fill_price) * quantity
```

Under the existing proportional-fee/no-fixed-fee assumptions, the exact positive magnitude for both sides is:

```text
quantity = current_available_equity
           / (actual_entry_fill_price * (1 + entry_fee_rate))
entry_notional = actual_entry_fill_price * quantity
entry_fee = entry_notional * entry_fee_rate
entry_notional + entry_fee = current_available_equity
```

The identical denominator is not an analogy between sides. In vectorbt's `size=np.inf` execution path, an infinite short amount is converted to 100% of resources, and the short-sale limit is derived from free cash using `adjusted_price * (1 + fees)`; the sell fill then deducts its fee from acquired cash. Thus long and short produce the same positive quantity under these assumptions while retaining different cash-flow, debt, and PnL behavior. At zero fee, entry notional equals current equity; at non-zero fee it does not.

This is historical all-in exposure sizing, not a new leverage or margin model.

## 6. Fees and equity timing

Entry and exit fees continue to use their actual fill notionals independently. Entry slippage is resolved first; the entry fee rate then participates in sizing so entry notional plus entry fee fit current equity. The resulting entry fee is carried with the position and included in realised net PnL at close. Exit fee does not affect entry quantity and is calculated only when the actual exit fill exists.

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

- first-entry example (`10000 / 50000 = 0.2`) explicitly at zero entry fee;
- side-aware slippage changes the denominator before sizing for long and short;
- non-zero proportional entry fees reduce quantity for both long and short according to the vectorbt-grounded all-in formula;
- entry notional plus entry fee, rather than entry notional alone, consumes current equity;
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
