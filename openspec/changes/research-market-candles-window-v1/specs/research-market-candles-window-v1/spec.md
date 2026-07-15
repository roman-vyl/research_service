# Specification: Research Market Candles Window v1

## Requirement: Preserved Workbench route

Research Service SHALL expose `GET /api/market/candles-window` with BBB-compatible query names and response fields.

## Requirement: Canonical MDS request

The route SHALL call Market Data Service through `MarketDataPort` using canonical `.P` ticker identity, textual timeframe and aligned half-open millisecond range.

Legacy `BTCUSDT` SHALL map to `BTCUSDT.P`; canonical `BTCUSDT.P` SHALL remain unchanged.

## Requirement: Workbench chart DTO

Every returned candle SHALL contain `time` in Unix seconds and numeric `open`, `high`, `low`, `close`, and optional `volume` fields.

The response SHALL contain coverage fields `requested_from_ms`, `requested_to_ms`, `actual_from_ms`, `actual_to_ms`, and `truncated`.

## Requirement: Complete success only

A successful response SHALL represent the complete requested grid and SHALL report exact coverage with `truncated=false`.

The route SHALL NOT synthesize partial success when MDS refuses an unavailable or out-of-bounds range.

## Requirement: Stable errors

Invalid BFF parameters SHALL return HTTP 400 with the Research Service error envelope. MDS unavailability SHALL return HTTP 503. Other MDS contract failures SHALL be mapped through structured upstream errors.

## Requirement: Clean architecture

The router and use case SHALL NOT import legacy BBB modules, SQLite, or direct MDS transport implementation details. The MDS adapter SHALL remain behind `MarketDataPort`.
