# Research Service Boundaries v1 Specification

## Purpose

Define the current, canonical ownership split between Strategy Engine, Market
Data Service, and Research Service, and the invariant that governs how
Research Service combines their outputs. Every other current spec in this
service defers to this one for ownership language and states only its own
capability-local requirements.
## Requirements
### Requirement: Strategy Engine ownership

Strategy Engine SHALL own strategy-spec semantics, indicator/context/component
evaluation, entry decisions, initial stop/take policy, standard signal exits,
and managed phase/stop/take-profile/runtime-exit policy decisions. Research
Service SHALL NOT recalculate any of the above.

#### Scenario: A capability needs a strategy decision

- **WHEN** a Research Service capability needs an entry decision, an initial
  stop/take ratio, a signal-exit flag, or a managed-policy decision
- **THEN** it SHALL obtain that value from Strategy Engine output and SHALL
  NOT derive it locally from indicators or raw market data.

### Requirement: Market Data Service ownership

Market Data Service SHALL own canonical OHLCV candle data: storage,
readiness, and market identity (ticker, timeframe, bar grid). Research
Service SHALL NOT compute, interpolate, or locally synthesize candle data.

#### Scenario: A capability needs OHLCV

- **WHEN** a Research Service capability needs market candles for
  presentation or execution simulation
- **THEN** it SHALL read them exclusively through `MarketDataPort`.

### Requirement: Research Service ownership

Research Service SHALL own: research-run orchestration; canonical OHLCV acquisition for simulation; entry and exit fill execution; historical position sizing from current available equity, actual entry fill price, and entry execution costs; gap/open handling and same-bar candidate arbitration; position lifecycle; fees, slippage, PnL, equity, and metrics; trade records, artifacts, and diagnostics projection; research-specific state (saved configs, run artifacts); and the public BFF namespace consumed by the Research Workbench frontend. Strategy Engine SHALL NOT receive or derive account equity, notional, quantity, fees, or sizing policy.

#### Scenario: A capability performs execution or presentation work

- **WHEN** a capability performs fill arbitration, position sizing, position lifecycle, accounting, artifact persistence, or BFF projection
- **THEN** Research Service owns that behavior outright and no other service is consulted for its semantics.

#### Scenario: Strategy Engine provides an entry decision

- **WHEN** Strategy Engine returns a historical entry decision or executable opportunity
- **THEN** that fact contains no equity, notional, quantity, or sizing decision
- **AND** Research derives quantity only after resolving its own actual entry fill price.

### Requirement: BFF namespace ownership

The Research Service FastAPI application SHALL be the sole owner of the
browser-facing `/api/market/*` and `/api/research/*` namespaces.

#### Scenario: Browser client reaches Research Service only

- **WHEN** the Research Workbench frontend calls any `/api/market/*` or
  `/api/research/*` route
- **THEN** it SHALL require only the Research Service base URL, never a
  Strategy Engine or Market Data Service URL.

### Requirement: Typed seam

Any Research Service use case that consumes Strategy Engine output and
Market Data Service output together SHALL do so through typed domain values
(`StrategyEvaluationResult`, `MarketFrame`) and SHALL produce a typed result.

#### Scenario: Execution simulator input

- **WHEN** the backtest orchestration composes a Strategy Engine range
  response with a Market Data Service candle range
- **THEN** both inputs are the typed domain values, not the raw transport
  payload, and the composition produces a typed `BacktestResult`.

### Requirement: Alignment invariant

Before Research Service uses a Strategy Engine decision frame and a Market
Data Service execution frame together, it SHALL reject any mismatch between
them on ticker, timeframe, requested range, ordered timestamps and bar
count, and market-data identity/hash when both sides provide one.

#### Scenario: Strategy Engine and MDS disagree on market identity

- **WHEN** the Strategy Engine evaluation's market range and the Market Data
  Service candle range differ in ticker, timeframe, bar count, or ordered
  timestamps
- **THEN** Research Service SHALL reject the combination with an
  `invalid_request` error and SHALL NOT execute a simulation.

### Requirement: No local fallback

Research Service production code SHALL NOT locally recalculate indicators,
interpolate or silently truncate data, or fall back to a disconnected
reference source anywhere.

#### Scenario: Upstream data is incomplete

- **WHEN** Strategy Engine or Market Data Service data needed for a request
  is missing or incomplete
- **THEN** Research Service SHALL fail the request through a stable error
  rather than substitute a locally computed or cached approximation.
