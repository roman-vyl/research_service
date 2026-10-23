## ADDED Requirements

### Requirement: Preview warmup lower bound

A preview EMA calculation, one-off or the combined 200/500/1000 preview, SHALL NOT request a range that
begins before `earliest_open_time_ms` of the ticker and timeframe as served by Market Data. When the
warmup would begin earlier, the calculation SHALL begin at that bound. When the bounds cannot be read,
the route SHALL fail with the upstream error and SHALL NOT call Strategy Engine. A requested range that
ends at or before `earliest_open_time_ms` SHALL be rejected as an invalid request.

#### Scenario: One-off EMA near the start of history

- **WHEN** an EMA with a period outside 200, 500 and 1000 is requested for a window that starts less than
  `5 * period` bars after the first stored bar
- **THEN** Strategy Engine is asked for a range that begins at the first stored bar.

#### Scenario: Cold stack preview near the start of history

- **WHEN** no entry exists and an EMA of 200, 500 or 1000 is requested for a window that starts less than
  5000 bars after the first stored bar
- **THEN** the preview calculation begins at the first stored bar and `calculation_origin_ms` equals it.

#### Scenario: Bounds unavailable

- **WHEN** Market Data bounds cannot be read for a preview
- **THEN** the route fails with the upstream error, Strategy Engine is not called, and a later request is
  not blocked by the failed preview.

#### Scenario: Range before the history

- **WHEN** the requested range ends at or before the first stored bar
- **THEN** the route responds with an invalid-request error and Strategy Engine is not called.
