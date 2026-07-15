# Research Service foundation v1 specification

## Requirement: Independent production package

The repository SHALL expose an installable `research_service` package under `src/`. Production modules SHALL NOT import from `legacy_source`, `research`, or `research_api`.

## Requirement: BFF ownership

The FastAPI application SHALL own the browser-facing `/api/market/*` and `/api/research/*` namespaces. Browser clients SHALL NOT need Strategy Engine or Market Data Service URLs.

## Requirement: Honest incomplete capabilities

Preserved routes without a completed semantic port SHALL return HTTP 501 with `error=capability_not_ported`. They SHALL NOT call legacy code or return empty fake-success payloads.

## Requirement: Explicit external ports

Strategy evaluation SHALL be accessed through `StrategyEnginePort`; canonical candles SHALL be accessed through `MarketDataPort`; artifact persistence SHALL be accessed through `ArtifactStore`.

## Requirement: Canonical market contract

Market requests SHALL use canonical `.P` ticker, a supported timeframe and an aligned half-open range. Market Data responses SHALL be rejected when identity, count, order or grid continuity does not match the request.

## Requirement: Operational endpoints

`GET /health` SHALL report process liveness. `GET /readiness` SHALL report Strategy Engine and Market Data Service dependency health and artifact-store location. OpenAPI SHALL be available through the FastAPI default route.
