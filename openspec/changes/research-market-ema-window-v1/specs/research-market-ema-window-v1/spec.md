# Research Market EMA Window v1 Specification

## Requirement: preserved Workbench route

Research Service SHALL serve `GET /api/market/ema-window` with the existing BBB query parameters and response field names.

## Requirement: Strategy Engine ownership

Research Service SHALL NOT calculate EMA locally. It SHALL request an EMA feature through Strategy Engine `POST /v1/indicator-evaluations/range`.

## Requirement: presentation conversion

Strategy Engine Decimal-text values SHALL be converted to JSON numbers only at the BFF chart DTO boundary. Timestamps SHALL be converted from milliseconds to Unix seconds.

## Requirement: cache behavior

The BFF SHALL retain a process-local cache keyed by ticker, timeframe and period, report `cache_hit`, and request only a missing right-edge suffix when extending cached coverage.

## Requirement: honest origin metadata

Until an upstream earliest-available boundary exists, `calculation_origin_ms` SHALL equal the first requested range start. The service SHALL NOT claim full-history canonical origin parity.
