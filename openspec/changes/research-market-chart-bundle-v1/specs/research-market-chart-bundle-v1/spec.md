# Research Market Chart Bundle v1 Specification

## Requirement: preserved route

Research Service SHALL expose `GET /api/market/chart-bundle` with the legacy Workbench request parameters and response structure.

## Requirement: external data ownership

Research Service SHALL obtain OHLCV candles through `MarketDataPort` and EMA values through `StrategyEnginePort`.

Research Service SHALL NOT calculate EMA values locally.

## Requirement: ordered overlays

The response SHALL contain exactly three overlays ordered as `fast`, `anchor`, and `slow`, using the periods supplied in the request.

## Requirement: validation

Requests SHALL be rejected when the periods do not satisfy `fast < anchor < slow`.

## Requirement: request efficiency

A chart-bundle request SHALL perform one Market Data Service range read. Repeated identical requests MAY repeat candle reads but SHALL reuse already materialized EMA ranges from the app-scoped EMA cache.
