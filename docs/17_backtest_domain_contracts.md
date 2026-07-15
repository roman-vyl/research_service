# Backtest domain contracts

## MarketFrame

```text
MarketFrame
- ticker
- timeframe
- from_ms
- to_ms
- bars[]
  - open_time_ms
  - open
  - high
  - low
  - close
  - volume
- market_data_identity
```

Invariants:

- half-open aligned range;
- strictly ascending complete grid;
- no duplicate timestamps;
- Decimal-text values at the port boundary;
- exact ticker/timeframe/range match with strategy evaluation metadata.

## StrategyEvaluationResult

Research Service treats the response from `POST /v1/strategy-evaluations/range` as an upstream immutable decision frame. The adapter must expose at minimum:

```text
- strategy_id / version / instance_id
- ticker / base_timeframe
- requested range
- ordered bar timestamps
- long and short entry decisions
- initial stop/take levels or candidates
- standard signal-exit decisions
- managed phase and active stop/take state
- runtime-exit decisions
- candidate identity, layer, rule/component id and evidence
- market-data provenance metadata
```

Research Service must not infer missing strategic decisions from raw indicators.

## ExecutionPolicy

```text
ExecutionPolicy
- initial_cash
- order_size_policy
- fees_rate
- slippage_model
- entry_fill_policy
- stop_gap_policy
- take_gap_policy
- same_bar_priority
- close_open_position_at_end
```

V1 will initially support the existing single-size research semantics. Sizing is explicit and may not be hidden inside a simulator adapter.

## PositionState

```text
PositionState
- trade_id
- instance_id
- side
- status
- entry_signal_time_ms
- entry_fill_time_ms
- entry_price
- quantity
- entry_fees
- active_stop
- active_take
- active_phase
- bars_held
- strategy_state_refs
```

Only execution facts are mutable here. Strategy policy state is copied from the latest Strategy Engine decision and is not recalculated.

## ExitCandidate

```text
ExitCandidate
- time_ms
- side
- layer
- candidate_type
- trigger_price
- executable_price_policy
- priority
- rule_id
- component_id
- reason
- effective_from_ms
- metadata
```

The adapter converts Strategy Engine decisions into candidates. The arbitrator selects among candidates touched by the current OHLC bar.

## FillEvent

```text
FillEvent
- fill_id
- trade_id
- event_type: entry | exit
- time_ms
- bar_open_time_ms
- side
- quantity
- reference_price
- fill_price
- fees
- slippage
- candidate identity
- arbitration metadata
```

## TradeRecord

```text
TradeRecord
- trade_id
- instance_id
- side
- entry and exit fills
- status
- quantity
- gross_pnl
- fees
- net_pnl
- return_pct
- bars_held
- exit reason/layer/owner
- management state at exit
- strategy evidence references
```

## BacktestResult

```text
BacktestResult
- run_id
- status
- request metadata
- upstream provenance
- execution policy
- fills[]
- trades[]
- equity points[]
- metrics
- diagnostics summary
- artifact manifest
```

The domain result is independent of Workbench DTOs. API and artifact projectors adapt it later.

## Alignment failures

The orchestration must fail before simulation when any of these differ:

- ticker;
- timeframe;
- requested range;
- bar count;
- ordered timestamps;
- market-data hash when available.

No best-effort interpolation, silent truncation or local indicator recalculation is allowed.


## ManagedPolicyReplay

For an actually opened logical trade, Research Service consumes `POST /v1/strategy-evaluations/managed-replay`. The response supplies phase, active stop, take-profile, runtime-exit state, ordered events and effective timing. It supplies no fill, arbitration, fee, PnL or closed-trade result.
