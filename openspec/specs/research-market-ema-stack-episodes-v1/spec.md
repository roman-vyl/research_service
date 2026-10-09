# research-market-ema-stack-episodes-v1 Specification

## Purpose
Research Service exposes Strategy Engine EMA stack episode history and the strategy feature plan to the Workbench as thin proxies: requests and answers pass through unchanged, Engine errors keep their status and body, nothing is computed or cached.
## Requirements
### Requirement: Episode history proxy route

Research Service SHALL serve `POST /api/market/ema-stack-episodes/history` and SHALL forward its JSON
request body unchanged to Strategy Engine `POST /v1/ema-stack-episodes/history`, with one Engine call
per request.

#### Scenario: First page

- **WHEN** the Workbench posts `{market, episode, side, page}` without a pin
- **THEN** Research Service SHALL post the same body to Strategy Engine once
- **AND** SHALL return Engine's response.

#### Scenario: Repeated request

- **WHEN** the same request is sent twice
- **THEN** Research Service SHALL call Strategy Engine twice
- **AND** SHALL NOT answer from a cache of its own.

### Requirement: Engine owns the episode

Research Service SHALL NOT compute, validate, default or cache episodes or episode parameters. Engine's
validation decides every request.

#### Scenario: Invalid parameters

- **WHEN** the body has `fast_period` 1000 and `anchor_period` 500
- **THEN** Research Service SHALL forward it
- **AND** SHALL return Engine's rejection.

### Requirement: Response unchanged

A 200 Engine response SHALL be returned with the same JSON object: the same fields, values and times in
milliseconds, including `history_id`, `market` (with `earliest_ms` and `as_of_ms`), `episode`,
`params_hash`, `market_data_hash`, `side`, `current`, `episodes` and `next_before_start_ms`. A 200 response whose body is not a JSON
object SHALL be HTTP 502 `upstream_service_error`.

#### Scenario: Times stay in milliseconds

- **WHEN** Engine returns an episode with `start_ms` 1700000000000
- **THEN** the Research Service response SHALL carry `start_ms` 1700000000000.

### Requirement: Engine errors passed through

A non-200 Engine response SHALL be returned with the same HTTP status and the same JSON body. A body
that is not a JSON object SHALL be wrapped in the standard error envelope with code
`upstream_service_error` and the same status. A transport failure or timeout SHALL be HTTP 503
`dependency_unavailable` with `service` `strategy_engine`.

#### Scenario: Pinned version changed

- **WHEN** the request carries an `expected_market_data_hash` and Engine answers 409
  `market_data_version_changed` with both hashes in `details`
- **THEN** Research Service SHALL answer 409 with the same body.

#### Scenario: Market stream not ready

- **WHEN** Engine answers 503
- **THEN** Research Service SHALL answer 503 with the same body.

#### Scenario: Invalid request

- **WHEN** Engine answers 422
- **THEN** Research Service SHALL answer 422 with the same body.

#### Scenario: Engine unreachable

- **WHEN** the connection to Strategy Engine fails
- **THEN** Research Service SHALL answer 503 `dependency_unavailable`.

### Requirement: Strategy feature plan proxy

Research Service SHALL serve `POST /api/research/strategies/{strategy_id}/feature-plan` and SHALL forward
its JSON body unchanged to Strategy Engine `POST /v1/strategies/{strategy_id}/feature-plan`, returning
the response unchanged and Engine errors with the same status and body. `strategy_id` SHALL match
`[A-Za-z0-9_-]{1,64}`; any other value SHALL be rejected without an Engine call.

#### Scenario: Effective episode parameters

- **WHEN** the Workbench posts `{strategy_id, raw_spec}` of a strategy with `ema_stack_episode`
- **THEN** the response SHALL be Engine's feature plan, including `episode_params_by_ref`.

#### Scenario: Odd strategy id

- **WHEN** the path `strategy_id` is `a.b`
- **THEN** Research Service SHALL answer 422 without calling Strategy Engine.

