# Proposal: Research Market Chart Bundle v1

Port the preserved `GET /api/market/chart-bundle` Workbench endpoint from the BBB monolith into Research Service.

The endpoint remains a deprecated compatibility/debug route. It composes canonical candles from Market Data Service with three chart-overlay EMA series from Strategy Engine while preserving the existing Workbench response shape.
