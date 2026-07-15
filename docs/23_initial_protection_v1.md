# Initial protection v1

## Purpose

This change rebuilds the Research-owned half of the legacy BBB initial SL/TP seam. Strategy Engine remains authoritative for whether static protection is ready and for the per-bar stop/take ratios. Research Service converts those ratios into absolute execution levels for the opened position.

## Legacy source invariants

The reviewed BBB path applied entry masks as:

```text
entries_for_portfolio = entries & stop_ready
short_entries_for_portfolio = short_entries & stop_ready_short
```

Therefore an entry decision is not executable when the corresponding `stop_ready` value is false.

Absolute levels follow the legacy `_levels_from_ratios` formulas:

```text
long:  SL = anchor × (1 - sl_ratio), TP = anchor × (1 + tp_ratio)
short: SL = anchor × (1 + sl_ratio), TP = anchor × (1 - tp_ratio)
```

Under compatibility profile `bbb_v1`, the anchor is the signal-bar close. This matches both VectorBT's default `stop_entry_price=close` and the legacy managed loop, which stored the signal-bar close as entry price. Explicit Research Service slippage can alter the fill price without changing this compatibility anchor.

## Ownership

Strategy Engine owns:

- `stop_loss_ratio.long/short`;
- `take_profit_ratio.long/short`;
- `stop_ready.long/short`;
- strategy semantics that produced those series.

Research Service owns:

- filtering executable entries by `stop_ready`;
- Decimal parsing and validation;
- conversion to absolute price levels;
- attaching immutable `InitialProtection` to `PositionState`.

## Scope

Implemented:

- long and short level conversion;
- absent stop and/or take rules;
- readiness gating;
- side and source-bar consistency;
- rejection of invalid or non-positive levels;
- immutable initial protection state.

Deferred:

- checking whether a later candle touched a level;
- gap execution;
- same-bar stop/take arbitration;
- signal exits;
- managed stop/take replacement;
- fees and PnL.
