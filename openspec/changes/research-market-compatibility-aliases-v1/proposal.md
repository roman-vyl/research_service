# Proposal: Research market compatibility aliases v1

Port the legacy Workbench endpoints `GET /api/market/candles` and
`GET /api/market/indicators/ema` without introducing new market or indicator
semantics. The routes delegate to the already ported candle-window and EMA-window
application services and return only the legacy list payloads.
