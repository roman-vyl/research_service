# Proposal: Research Market EMA Window v1

Port the preserved Workbench `GET /api/market/ema-window` route from legacy in-process EMA calculation to the Strategy Engine Indicator API while preserving the public BBB response shape.

The BFF remains the frontend boundary. It maps legacy symbols to canonical `.P` tickers, requests one EMA series from Strategy Engine, converts Decimal text to numeric chart points, and maintains a process-local window cache.

Known compatibility limitation: until Market Data Service exposes the earliest available candle boundary, the canonical calculation origin is the start of the first requested range rather than the start of the entire historical database.
