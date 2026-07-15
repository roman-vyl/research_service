# Proposal: Research Market Candles Window v1

## Why

The Workbench candle-window route currently reads the legacy BBB SQLite store directly. Research Service must preserve the frontend contract while replacing that storage coupling with the independent Market Data Service.

## What changes

- Implement `GET /api/market/candles-window` in Research Service.
- Preserve the BBB query parameter names and response DTO.
- Translate legacy Workbench symbols such as `BTCUSDT` to canonical MDS ticker `BTCUSDT.P`.
- Call Market Data Service `GET /v1/candles` through `MarketDataPort`.
- Convert Decimal-text OHLCV into numeric Workbench chart bars.
- Preserve `to` and `to_open_time_ms` compatibility.
- Remove only this route from the preserved `501 capability_not_ported` router.

## Out of scope

- EMA routes and chart bundle.
- Frontend changes.
- Partial/truncated reads outside the MDS proven available window.
- Market-data caching.
- Strategy Engine integration.
