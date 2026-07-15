# Research single-instance backtest v1 specification

## Requirements

1. The service SHALL run exactly one strategy instance per request.
2. Strategy decisions SHALL come only from Strategy Engine APIs.
3. Market OHLCV SHALL come only from Market Data Service.
4. Market identity and bar grid SHALL be accepted before any execution.
5. Research Service SHALL own fill arbitration, position lifecycle and accounting.
6. Managed decisions SHALL be requested per opened position and consumed with next-bar timing.
7. Open positions at range end SHALL remain unrealised.
8. The result SHALL use contract version `research_single_instance_backtest.v1`.
9. The use case SHALL not import or execute legacy BBB source.
