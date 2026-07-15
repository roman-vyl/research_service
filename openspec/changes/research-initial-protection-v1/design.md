# Design

Strategy Engine remains authoritative for `stop_loss_ratio`, `take_profit_ratio` and `stop_ready`. Research Service validates the aligned side series and converts the entry-bar ratios into Decimal price levels.

For compatibility profile `bbb_v1`, levels are anchored to the signal-bar close (`EntryFill.reference_price`), matching legacy VectorBT `stop_entry_price=close` and the managed execution loop. Entry slippage affects the fill but not this compatibility anchor.

A position is created only when its side's entry decision and `stop_ready` are both true. The resulting immutable `PositionState` contains an immutable `InitialProtection` object.
