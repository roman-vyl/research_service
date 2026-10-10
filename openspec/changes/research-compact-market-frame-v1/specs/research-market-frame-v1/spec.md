## ADDED Requirements

### Requirement: Compact market history

Research Service SHALL hold the candle history of a `MarketFrame` in fixed-width columnar storage and SHALL NOT
hold one Python object per candle.

#### Scenario: Full window
- **WHEN** a `MarketFrame` is read for 684,704 five-minute candles
- **THEN** the history occupies tens of megabytes, not more than 100 MB.

### Requirement: Lossless prices

Every open, high, low, close and volume SHALL be restored as a `Decimal` equal to the value the current decode
produces for the same payload, in value and in representation (sign, digits and exponent). `float` SHALL NOT be
used for canonical prices. A value that cannot be stored exactly SHALL fail the read and SHALL NOT be rounded.

#### Scenario: Trailing zeros
- **WHEN** the payload carries `100.50` and `100.5`
- **THEN** the restored `Decimal` values keep their own exponents.

### Requirement: Compatible candle access

`MarketFrame.candles` SHALL behave as a read-only sequence of `Candle`: `len`, indexing including negative
indexes, slicing and iteration. `MarketFrame` SHALL still accept a sequence of `Candle` at construction. The grid
check (complete, ordered, no gaps) SHALL still reject an incomplete or gapped frame.

#### Scenario: Existing caller
- **WHEN** a caller builds `MarketFrame(market=m, candles=tuple_of_candles)`
- **THEN** it works unchanged and `frame.candles[-1]` equals the last supplied `Candle`.

### Requirement: Execution parity

Replacing the storage SHALL NOT change any execution or accounting result.

#### Scenario: Reference runs
- **WHEN** a fixed SL/TP run and a managed trailing run are executed with the old and the new storage
- **THEN** trades, managed events, fills, fees and accounting are identical and the serialized trade and metrics
  artifacts are byte-identical, with no numeric tolerance.
