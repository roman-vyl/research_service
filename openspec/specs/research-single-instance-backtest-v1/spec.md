# Research Single-Instance Backtest v1 Specification

## Purpose

Define the authoritative single-instance backtest orchestration use case:
compose Strategy Engine, Market Data Service, execution, and accounting into
one immutable result. Ownership (Strategy Engine vs Research Service vs
Market Data Service) is normative in `research-service-boundaries-v1`; this
spec states only the requirements specific to this use case.

## Requirements

### Requirement: One instance per request

The service SHALL run exactly one strategy instance per request.

#### Scenario: Single-instance scope

- **WHEN** a backtest request is executed
- **THEN** exactly one strategy instance is evaluated and simulated.

### Requirement: Market data source

Market OHLCV SHALL come only from Market Data Service.

#### Scenario: Execution frame source

- **WHEN** the use case needs candles for simulation
- **THEN** it reads them through `MarketDataPort`, never a local source.

### Requirement: Market identity accepted before execution

Market identity and bar grid SHALL be accepted before any execution.

#### Scenario: Identity check precedes simulation

- **WHEN** a backtest request begins
- **THEN** market identity and bar-grid acceptance runs before any fill or
  accounting logic executes.

### Requirement: Resolved evaluation window

The use case SHALL resolve the requested market range into an effective
window before evaluation: for `range_policy=explicit_range`, the requested
range verified against Market Data Service's continuity audit; for
`range_policy=full_available`, the full range reported by Market Data
Service's stream bounds, verified the same way. The resolved window's
market range and `market_data_hash` — not the originally requested range —
SHALL be used for every downstream stage of that backtest: Strategy Engine
range evaluation, historical candle acquisition, and managed-replay
requests.

#### Scenario: full_available resolves a wider effective range

- **WHEN** a request specifies `range_policy=full_available` with a narrower
  requested range than the ticker/timeframe's full available history
- **THEN** the resolved window covers the full available range, and
  Strategy Engine evaluation, historical candle acquisition, and every
  managed-replay request for that backtest all use that resolved range, not
  the originally requested one.

#### Scenario: Continuity audit fails

- **WHEN** Market Data Service's continuity audit for the resolved range
  reports a gap or a candle count that does not match the range
- **THEN** the backtest is rejected before Strategy Engine evaluation
  begins.

### Requirement: Strategy Engine contract acceptance

The Strategy Engine response SHALL be rejected when it omits any of the
required exit-policy fields (`signal_exit`, `stop_loss_ratio`,
`take_profit_ratio`, `stop_ready`), when any such field is not present for
both `long` and `short` with one value per market bar, or when either side
fails to report a `market_data_hash` or the two reported hashes differ.

#### Scenario: Missing exit-policy field

- **WHEN** a Strategy Engine range response omits `stop_ready`
- **THEN** the backtest request is rejected before simulation begins.

#### Scenario: Market-data hash mismatch

- **WHEN** the Strategy Engine response's `market_data_hash` differs from
  the Market Data Service response's `market_data_hash`
- **THEN** the backtest request is rejected.

### Requirement: Execution and accounting ownership

Research Service SHALL own fill arbitration, position lifecycle, and
accounting.

#### Scenario: End-to-end ownership

- **WHEN** a backtest runs to completion
- **THEN** every fill, position-state transition, and accounting figure in
  the result was produced by Research Service's own execution and
  accounting layers.

### Requirement: Managed decision timing

Managed decisions SHALL be requested per opened position and consumed with
next-bar timing.

#### Scenario: Managed replay per position

- **WHEN** a position opens during the backtest
- **THEN** managed replay is requested for that position and its decisions
  are consumed starting at their own effective bar, never the bar they were
  produced on.

### Requirement: Open positions remain unrealised

Open positions at range end SHALL remain unrealised.

#### Scenario: Backtest ends with an open position

- **WHEN** the requested range ends while a position is open
- **THEN** the result reports it open and unrealised, not force-closed.

### Requirement: Result contract version

The result SHALL use contract version `research_single_instance_backtest.v1`.

#### Scenario: Result versioning

- **WHEN** a backtest result is produced
- **THEN** its `contract_version` field is
  `research_single_instance_backtest.v1`.
