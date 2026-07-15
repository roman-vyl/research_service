# Design: Research Market Candles Window v1

## Current path

```text
Workbench
→ GET /api/market/candles-window
→ research_api.services.market_reader.fetch_candles_window
→ legacy Db.range_get
→ ChartBar + CandlesWindowCoverage
```

## Target path

```text
Workbench
→ GET /api/market/candles-window
→ Research Service market router
→ GetCandlesWindow application use case
→ MarketDataPort
→ HttpMarketDataClient
→ MDS GET /v1/candles
→ ChartBar + CandlesWindowCoverage
```

## Compatibility seam

The external BFF contract remains:

- query: `symbol`, `timeframe`, `from`, and exactly one of `to` or `to_open_time_ms`;
- response: `{candles, coverage}`;
- chart time: Unix seconds;
- OHLCV: JSON numbers;
- invalid BFF parameters: HTTP 400.

Research Service maps `BTCUSDT` to `BTCUSDT.P`. Already-canonical `.P` values pass unchanged.

## Coverage semantics

The legacy SQLite reader could return partial rows and set `coverage.truncated=true`. MDS v1 deliberately refuses partial/out-of-bounds ranges. Therefore:

- a successful response contains the complete requested grid;
- `actual_from_ms == requested_from_ms`;
- `actual_to_ms == requested_to_ms`;
- `truncated == false`;
- MDS range failures are returned as structured upstream errors, not partial `200` responses.

This preserves the DTO while strengthening the data-completeness invariant.

## Layer ownership

- router: query extraction and response model only;
- application use case: symbol compatibility, range construction, transport conversion, coverage construction;
- MarketDataPort/client: MDS HTTP contract and canonical grid validation;
- no SQL or legacy imports in production code.
