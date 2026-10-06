## MODIFIED Requirements

### Requirement: Parity gate before publish

The gate SHALL be metric parity only. For each completed row the job SHALL compare every result-binding value of the
Engine run summary with the value stored in the row. Metrics with format
`integer` SHALL be equal. A metric whose result schema entry declares `decimals = d`
SHALL satisfy `|actual − expected| ≤ 0.5 × 10^−d + 1e-9`. Other metrics SHALL satisfy
`|actual − expected| ≤ max(1e-6 × max(|actual|, |expected|), 1e-9)`. Two empty
values SHALL pass; one empty value SHALL fail. The tolerance SHALL NOT be
configurable beyond `decimals`, which states how the stored value was rounded. A row with any failing metric SHALL end as `parity_failed` with the
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

- **WHEN** a metric declares `decimals = 4`, the row stores `0.8861` and the Engine
  returns `0.886149`
- **THEN** that metric passes the gate.

#### Scenario: Difference beyond the stored precision

- **WHEN** a metric declares `decimals = 4`, the row stores `0.8861` and the Engine
  returns `0.8863`
- **THEN** the row ends as `parity_failed`.

#### Scenario: Integer metric with decimals

- **WHEN** a result schema declares `decimals` on a metric with format `integer`
- **THEN** the Experiment is rejected as invalid.
