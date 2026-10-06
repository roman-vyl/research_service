## MODIFIED Requirements

### Requirement: Parity gate before publish

The gate SHALL be metric parity only. For each completed row the job SHALL compare every result-binding value of the
Engine run summary with the value stored in the row, using the gate named by
`materialize.parity`: `strict` (the default) or `legacy_surface`.

Under `strict`, metrics with format `integer` SHALL be equal and other metrics SHALL satisfy
`|actual − expected| ≤ max(1e-6 × max(|actual|, |expected|), 1e-9)`.

Under `legacy_surface`, the rule SHALL be chosen by the Engine summary field of the
binding: `realised_trade_count` SHALL be equal; `return_pct`, `profit_factor`,
`win_rate` and `max_drawdown` SHALL satisfy `round(actual, 4) = round(expected, 4)`;
`cumulative_net_r` SHALL satisfy `round(actual, 2) = round(expected, 2)`; `net_pnl`
SHALL satisfy `|actual − expected| ≤ 0.5`. A field without a legacy rule SHALL use
the strict rule.

Under both gates two empty values SHALL pass and one empty value SHALL fail. The
rules SHALL NOT be configurable. A row with any failing metric SHALL end as `parity_failed` with the
list of `{column, expected, actual, rule}`; its row SHALL NOT change and its run SHALL
be kept and SHALL NOT be written to the row.

#### Scenario: Replay matches Engine

- **WHEN** every metric of the Engine run agrees with the replay row within the
  tolerance
- **THEN** the row is published.

#### Scenario: Replay differs

- **WHEN** the Engine trade count differs from the replay row by one
- **THEN** the row ends as `parity_failed`, keeps its replay metrics, provenance
  and empty `run_id`
- **AND** the journal names the Engine `run_id` and the differing metrics.

#### Scenario: Legacy Surface stored at 4 decimals

- **WHEN** `materialize.parity` is `legacy_surface`, the row stores return `0.8861`,
  net PnL `8861.0` and the Engine returns `0.886150` and `8861.4976`
- **THEN** both metrics pass.

#### Scenario: Legacy difference beyond stored precision

- **WHEN** `materialize.parity` is `legacy_surface`, the row stores win rate `0.2594`
  and the Engine returns `0.2596`
- **THEN** the row ends as `parity_failed`.

#### Scenario: Strict by default

- **WHEN** the `materialize` block has no `parity`
- **THEN** the strict gate applies and the same rounded row ends as `parity_failed`.
