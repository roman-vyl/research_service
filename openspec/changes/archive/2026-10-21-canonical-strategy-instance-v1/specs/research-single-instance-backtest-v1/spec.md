## MODIFIED Requirements

### Requirement: Resolved evaluation window

The use case SHALL resolve the requested market range into an effective
window before evaluation. For `range_policy=explicit_range`, the request
SHALL supply a real `from_ms`/`to_ms`, verified against Market Data
Service's continuity audit. For `range_policy=full_available`, the
request SHALL supply only `ticker` and `base_timeframe` — no `from_ms`/
`to_ms` — and the full range reported by Market Data Service's stream
bounds SHALL be resolved and verified the same way. The resolved window's
market range and `market_data_hash` — not any caller-supplied range —
SHALL be used for every downstream stage of that backtest: Strategy
Engine range evaluation, historical candle acquisition, and
managed-replay requests.

#### Scenario: full_available resolves a wider effective range

- **WHEN** a request specifies `range_policy=full_available`
- **THEN** the resolved window covers the full available range, and
  Strategy Engine evaluation, historical candle acquisition, and every
  managed-replay request for that backtest all use that resolved range.

#### Scenario: full_available request carries no range

- **WHEN** a request specifies `range_policy=full_available`
- **THEN** the request contains no `from_ms`/`to_ms` fields, and the
  endpoint does not reject it for missing range fields.

#### Scenario: Continuity audit fails

- **WHEN** Market Data Service's continuity audit for the resolved range
  reports a gap or a candle count that does not match the range
- **THEN** the backtest is rejected before Strategy Engine evaluation
  begins.
