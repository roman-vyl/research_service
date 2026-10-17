## ADDED Requirements

### Requirement: Read-only bounds route
Research Service SHALL expose `GET /api/market/bounds` with query parameters `symbol` and
`timeframe`. The route SHALL be read-only and SHALL NOT modify any state.

#### Scenario: Frontend asks for the bounds of a market
- **WHEN** a client calls `GET /api/market/bounds?symbol=ETHUSDT.P&timeframe=5m`
- **THEN** the response is HTTP 200 with the committed bounds of that market

### Requirement: Bounds come from Market Data Service unchanged
The route SHALL first validate the trimmed timeframe locally through the existing domain `timeframe_ms()` (no second list of timeframes), and only then obtain the bounds through `MarketDataPort.get_bounds` using the canonical `.P`
ticker and the trimmed textual timeframe, and SHALL return `earliest_open_time_ms`,
`latest_open_time_ms` and `stream_state` exactly as the port returned them. The route SHALL NOT
compute, shift, round or cache them.

#### Scenario: Values are forwarded
- **WHEN** the port returns earliest `1614556800000`, latest `1760000100000` and state `ready`
- **THEN** the response contains `earliest_open_time_ms=1614556800000`,
  `latest_open_time_ms=1760000100000` and `stream_state="ready"`

#### Scenario: Legacy ticker is supplied
- **WHEN** a request supplies `symbol=BTCUSDT`
- **THEN** the port is called with `BTCUSDT.P` and the response `symbol` is `BTCUSDT.P`

#### Scenario: Each request asks the port again
- **WHEN** two requests for the same market arrive one after the other
- **THEN** the port is called twice

### Requirement: Response shape
The response SHALL contain exactly `symbol` (canonical ticker), `timeframe`,
`earliest_open_time_ms`, `latest_open_time_ms` and `stream_state`. The two times SHALL be open
times of existing bars in milliseconds, so `latest_open_time_ms` is valid as `to_open_time_ms` of
`GET /api/market/candles-window`.

#### Scenario: Shape
- **WHEN** the route succeeds
- **THEN** the body has exactly those five fields and no others

### Requirement: Stable errors
Invalid `symbol` or an unsupported `timeframe` SHALL return HTTP 400 with the Research Service error envelope.
Market Data Service unavailability SHALL return HTTP 503. Other Market Data Service failures SHALL
be mapped through structured upstream errors keeping the upstream status.

#### Scenario: Invalid symbol
- **WHEN** `symbol` is not a valid ticker
- **THEN** the route returns HTTP 400 with the error envelope and does not call the port

#### Scenario: Unsupported timeframe
- **WHEN** `timeframe` has a valid query length but is not supported by the domain `timeframe_ms()` (for example `7x`)
- **THEN** the route returns HTTP 400 with the error envelope and `MarketDataPort.get_bounds` is not called (call count 0)

#### Scenario: Market Data Service is unreachable
- **WHEN** Market Data Service does not respond
- **THEN** the route returns HTTP 503 using the error envelope

#### Scenario: Unknown stream
- **WHEN** Market Data Service answers 404 for the stream
- **THEN** the route returns HTTP 404 through the structured upstream error

### Requirement: No other behaviour changes
The change SHALL NOT alter `candles-window`, `ema-window`, `chart-bundle`, the compatibility
routes, Market Data Service, or `MarketDataPort`.

#### Scenario: Existing routes unchanged
- **WHEN** the change is applied
- **THEN** the existing market route tests pass without modification
