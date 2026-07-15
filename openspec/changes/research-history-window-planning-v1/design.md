# Design: Research History Window Planning v1

## 1. Responsibility split

### Market Data Service

Owns the proven available history for a configured stream:

```text
available_from_ms
available_to_ms  # exclusive
stream state
```

It does not decide research periods or strategy warmup.

### Research Service

Owns the requested evaluation window: the interval on which entries, exits, trades, reports and Workbench artifacts are considered part of the requested run.

It resolves user/config policies such as:

- `explicit_range`;
- `full_available`;
- later train/test or rolling-window policies.

### Strategy Engine

Owns the required market-input window. It derives warmup from the validated strategy spec, FeaturePlan, indicator periods, HTF completion rules, component lookbacks and stateful strategy requirements.

The Strategy Engine may request candles earlier than the evaluation start, but returns public decision arrays aligned to the requested evaluation range.

## 2. Target flow

```text
Research Service
  -> MDS stream coverage
  -> resolve evaluation range
  -> Strategy Engine evaluation request

Strategy Engine
  -> build FeaturePlan
  -> derive required warmup/input range
  -> read MDS coverage
  -> clamp only when policy allows
  -> read expanded candle range
  -> calculate indicators and strategy decisions
  -> return results cropped to evaluation range
  -> include input-range and warmup metadata

Research Service
  -> independently read canonical OHLCV for simulation range
  -> verify identity/hash alignment
  -> simulate fills/trades and build artifacts
```

## 3. Market Data Service coverage contract

The exact route may be finalized during implementation, but the required semantic contract is:

```http
GET /v1/streams/{ticker}/{timeframe}/coverage
```

Successful response:

```json
{
  "ticker": "BTCUSDT.P",
  "timeframe": "5m",
  "state": "ready",
  "available_from_ms": 1514764800000,
  "available_to_ms": 1783987200000
}
```

Requirements:

- canonical configured `.P` ticker;
- textual timeframe;
- `available_to_ms` is exclusive;
- coverage is returned only from canonical committed candles;
- state and boundaries are from one consistent storage snapshot;
- non-ready streams do not advertise a usable ready range;
- no audit or repair is triggered by this read API.

## 4. Research evaluation-range contract

Research Service shall model the resolved range explicitly:

```json
{
  "range_policy": "explicit_range",
  "evaluation_from_ms": 1735689600000,
  "evaluation_to_ms": 1767225600000
}
```

For `full_available`, Research Service obtains MDS coverage and resolves the concrete half-open range before calling Strategy Engine.

Research Service shall not encode indicator warmup into the requested range.

## 5. Strategy Engine request extension

Strategy range requests shall carry an explicit history policy:

```json
{
  "strategy_id": "ema_pullback",
  "strategy_spec": {},
  "ticker": "BTCUSDT.P",
  "base_timeframe": "5m",
  "from_ms": 1735689600000,
  "to_ms": 1767225600000,
  "history_policy": "require_fully_warmed"
}
```

Supported v1 policies:

- `require_fully_warmed`: reject the request if the first evaluation bar cannot have all required strategy inputs valid;
- `allow_partial_warmup`: return the requested range with explicit invalid/warmup metadata until all required values become valid.

## 6. Warmup derivation

Warmup shall be derived inside Strategy Engine from the validated semantic plan. It must account for at least:

- base-timeframe indicator periods;
- HTF indicator periods and completed-candle visibility shift;
- rolling lookbacks;
- setup touch/bounce/history windows;
- blocker peak/lookback windows;
- any deterministic state replay required before the first evaluable bar.

The derivation must be deterministic and included in parity tests. External callers must not estimate this independently.

## 7. Strategy Engine response metadata

Every strategy evaluation shall report both ranges:

```json
{
  "requested_range": {
    "from_ms": 1735689600000,
    "to_ms": 1767225600000
  },
  "market_input_range": {
    "from_ms": 1733011200000,
    "to_ms": 1767225600000
  },
  "warmup": {
    "history_policy": "require_fully_warmed",
    "required_from_ms": 1733011200000,
    "available_from_ms": 1514764800000,
    "valid_from_ms": 1735689600000,
    "fully_warmed_at_requested_start": true
  }
}
```

The response shall also preserve existing plan/config/market-data hashes so Research Service can prove that simulation candles and strategy decisions refer to the same canonical market history.

## 8. Insufficient-history behavior

No service may silently treat uninitialized indicator or component state as valid.

- Under `require_fully_warmed`, insufficient history returns a structured `422 insufficient_history`.
- Under `allow_partial_warmup`, the response remains successful but exposes `valid_from_ms` and per-series/per-component validity. Entry and exit decisions before validity must be non-actionable.

## 9. BFF and EMA origin

`/api/market/ema-window` shall eventually use MDS coverage to establish the canonical calculation origin rather than using the first requested chart range. The existing Workbench DTO may remain unchanged, but `calculation_origin_ms` must reflect the true chosen canonical origin.

The browser does not calculate or request warmup. Research Service and Strategy Engine own that behavior.

## 10. Execution order and deferral

This change is deliberately deferred until after:

1. remaining high-value BFF route ports;
2. direct Strategy Engine integration in Research Service;
3. Research execution adapter and frozen-fixture parity;
4. authoritative Research Service backtest orchestration.

It shall then be implemented as a coordinated multi-repository change across Market Data Service, Strategy Engine and Research Service, with separate cumulative patches for each repository.


## Historical read activation

After a successful audit, Research SHALL use `POST /v1/historical-candles` for its execution frame and SHALL pass the same `expected_market_data_hash` to Strategy Engine. Runtime `GET /v1/candles` is not used by backtest orchestration. No hidden warmup/pre-roll or repair is introduced.
