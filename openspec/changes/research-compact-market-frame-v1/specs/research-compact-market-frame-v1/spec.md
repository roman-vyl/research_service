## ADDED Requirements

### Requirement: Lossless compact market frame

Research SHALL hold a `MarketFrame` column-wise in fixed-width arrays: candle open times
and, for open, high, low, close and volume, an integer coefficient with a decimal
exponent per value. Every value read from the frame SHALL equal the `Decimal` received
from MDS exactly, including its exponent. Canonical prices SHALL NOT be stored or
converted as floating point.

#### Scenario: Exact value round-trip

- **WHEN** MDS returns close `6500`, close `6500.0` and volume `0.00012345`
- **THEN** the frame returns `Decimal("6500")`, `Decimal("6500.0")` and `Decimal("0.00012345")`.

### Requirement: Compatible candle access

`MarketFrame.candles` SHALL support length, integer index (including negative), slicing
and iteration, and each element SHALL be a `Candle` with the same field values as
before. The grid check (complete, ordered, without gaps) SHALL still reject a frame.

#### Scenario: Gapped frame

- **WHEN** MDS returns a window with a missing candle
- **THEN** the frame is rejected as before.

### Requirement: Execution unchanged

Engine, MDS and their contracts SHALL NOT change. A run executed with the compact
frame SHALL produce trade, execution-event, strategy-evaluation, managed-policy-event
and metrics artifacts byte-identical to the same run executed before the change, apart
from the run id and creation time.

#### Scenario: Reference runs

- **WHEN** the fixed SL/TP run of `btcusdt_p.ema500.ratio_4d` (w3 lb20 SL4 TP/SL 4) and the managed trailing run of `btcusdt_p.ema500.trailing_geometry_fee4_4d` (w4 lb150 SL6 T4 D2) are executed again
- **THEN** their artifacts are byte-identical to the stored ones and the trade counts are 1026 and 573.
