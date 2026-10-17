## Context

Measured before the change (research_service 9d1d629, local Docker Engine and MDS,
full window, one candidate per run, fresh process):

| Run | Kind | Trades | Wall | Peak RSS |
|---|---|---|---|---|
| run_3401fb28 (`ratio_4d`, w3 lb20 SL4 TP/SL 4) | fixed SL/TP | 1026 | 32.1 s | 1,650 MB |
| run_d0ceec8f (`trailing_geometry_fee4_4d`, w4 lb150 SL6 T4 D2) | managed trailing | 573 | 52.0 s | 1,384 MB |

The same runs re-executed on current code reproduce the stored `trades.json`,
`execution_events.json`, `strategy_evaluation.json` and `metrics.json` byte for byte;
`managed_policy_events.json` and `result.json` differ only in the run id, `manifest.json`
only in the creation time and the hashes of those two files. So byte-identical artifacts
are an achievable acceptance gate.

Candle memory breakdown (tracemalloc): `json.loads` of the MDS body 376 MB transient;
validated `Candle` tuple 1,117 MB resident. Value shape in this window: open/high/low/close
have 0 or 1 decimal places (max 126,150), volume 0–8 (mostly 3).

Consumers: 24 references to `.candles` under `src/` (execution loop, projection loop,
entry, projection entry, managed policy, accounting, market routers and windows). They
index, take `len`, iterate, take `[-1]` and slice.

## Decisions

- Storage: one `int64` array for `open_time_ms`; for each of open, high, low, close,
  volume an `int64` coefficient array and an `int8` exponent array (`Decimal` sign,
  digits and exponent are recovered exactly). About 684,704 × (8 + 5 × 9) ≈ 36 MB.
  Values whose coefficient does not fit `int64` are rejected at decode (none exist here).
- Access: `MarketFrame.candles` is a sequence view (`__len__`, `__getitem__` for int and
  slice, `__iter__`) returning `Candle` objects built on demand; the `Candle` model stays
  the public type. No cache of built candles.
- Decode: parse the MDS JSON once and fill the arrays directly; keep the grid validation
  on the arrays.
- No float anywhere in canonical prices; no change to rounding, fills or accounting.

## Risks

- Speed: building a `Candle` per bar access costs CPU in the hot loop. Measure wall time
  before/after on the reference runs; if slower, add a light non-pydantic candle object
  with the same attributes or vectorised field access in the two loops, still exact.
- Pickling/serialisation of `MarketFrame`, if anything relies on it: check during apply.
