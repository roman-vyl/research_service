## Context

12 source files read `market_frame.candles` (22 places): `len`, index, `[-1]`, one slice in accounting, plain
iteration in the execution loops, and small windows returned by the market API. About 30 test files and
`scripts/lane_a_timing_probe.py` build `MarketFrame(candles=tuple[Candle])`.

## Decisions

**D1 Columnar fixed-width storage.** `open_time_ms` as int64; each of open/high/low/close/volume as int64
mantissa plus int8 exponent. About 684,704 x (8 + 5 x 9) = 36 MB, versus 1.2 GB now.

**D2 Exact `Decimal` restore, no float.** Restoring a value gives a `Decimal` equal to the current decode in
value AND representation (sign, digits, exponent). A single scale per column would add trailing zeros
(`100.5` becoming `100.50`) and could change serialized trade artifacts, so the exponent is kept per value.
If a value does not fit int64, decoding fails loudly; it is never rounded.

**D3 Same input semantics as today.** The current decode goes through pydantic `Decimal` validation of the JSON
value (number or string). The new decoder SHALL produce the same `Decimal` for the same payload; which one
applies (JSON number via `str(float)` or string) is established by a pre-apply measurement on real MDS output.

**D4 Boundary abstraction, not a consumer rewrite.** `MarketFrame.candles` returns a read-only `Sequence[Candle]`
view over the arrays; `Candle` objects are built on access. `MarketFrame(candles=tuple[Candle])` stays valid and
is converted to arrays at construction, so all existing tests and callers keep one code path.

**D5 Speed is not promised.** Building a `Candle` per access may cost time in the bar-by-bar loop; array locality
may offset it. Peak RSS and wall time are measured before and after and reported.

## Risks

- Representation drift of `Decimal` (exponent, `-0`, very small/large values): covered by D2 and the byte-for-byte
  gate. Overflow of int64 mantissa: loud failure.
- Hidden consumers relying on `tuple` (hashing, equality, `tuple.index`): found by the test suite and a grep gate.

## Open measurements before apply (need the owner's Mac data)

1. Memory breakdown of the current `MarketFrame` (Candle objects, Decimals, tuple, JSON buffer), bytes per candle.
2. What MDS returns for prices (JSON numbers or strings), maximum fractional digits and magnitude for BTCUSDT.P
   and ETHUSDT.P.
3. Baseline peak RSS and wall time of the reference runs.
