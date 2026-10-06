## MODIFIED Requirements

### Requirement: Parity gate before publish

The gate SHALL be metric parity only. For each completed row the job SHALL compare every result-binding value of the
Engine run summary with the value stored in the row. Metrics with format
`integer` SHALL be equal. Other metrics SHALL satisfy
`|actual − expected| ≤ max(1e-3 × max(|actual|, |expected|), 1e-6)`. Two empty
values SHALL pass; one empty value SHALL fail. The tolerance SHALL NOT be
configurable. A row with any failing metric SHALL end as `parity_failed` with the
list of `{column, expected, actual}`; its row SHALL NOT change and its run SHALL
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

#### Scenario: Stored value rounded

- **WHEN** the row stores cumulative R `5.34` and the Engine returns `5.34421`
- **THEN** that metric passes.

#### Scenario: Result changed

- **WHEN** the row stores return `0.8861` and the Engine returns `0.8880`
- **THEN** the row ends as `parity_failed`.
