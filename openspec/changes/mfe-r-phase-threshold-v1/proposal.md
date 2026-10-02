## Why

Strategy Engine adds the phase atom `mfe_r` (change
`mfe-r-phase-threshold-v1` in strategy_engine): the trade's best
excursion in multiples of its initial risk. Engine projects it as
`trade_metric: "mfe_r"` with a constant R threshold, because a per-bar
threshold series cannot express a per-trade value. Research executes the
projection per trade, so the division by the trade's own initial risk is
Research's.

## What Changes

- `TradeMetric` gains `mfe_r`.
- The generic managed consumer evaluates `mfe_r` as
  `|mfe_price - reference_entry_price| / initial_risk` with
  `initial_risk = |reference_entry_price - initial stop level|` of the
  position, frozen at entry and carried unchanged through the managed
  state's whole lifecycle (eager timeline and incremental advance).
- A position with no initial stop, or a non-positive initial risk, never
  meets an `mfe_r` threshold (fail closed).
- Dispatch stays on `trade_metric`; no component id is read.
- No change to specs that do not use the metric; no new per-bar cost
  beyond one division.
