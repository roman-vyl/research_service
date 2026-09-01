## MODIFIED Requirements

### Requirement: Existing batch path only

Experiments SHALL use current canonical candidate contracts, live config validation, `RunBatchExperiment`, canonical per-run persistence, and `PersistBatchExperiment`. AutoResearch SHALL NOT implement simulation, position sizing, an equity ledger, accounting, metric derivation, direct MDS/Strategy Engine research execution, or a second summary format. It SHALL inherit the canonical Research sizing semantics of each batch candidate. Before accepting a batch result, the supervisor SHALL verify the canonical request/summary/manifest identity, summary hash, candidate identities and counts, completed run IDs, and shared completed-candidate market-data hash against the worker result. Before reading that bundle, it SHALL resolve the reported path and require the exact canonical `<Settings().artifacts_root>/batches/<experiment_id>` location without traversal or symlink escape.

#### Scenario: Valid batch experiment

- **WHEN** a worker runs a justified batch
- **THEN** every successful candidate is a canonical persisted run whose quantities and equity chain were produced by Research Service
- **AND** the journal references the existing batch artifact and run IDs.

#### Scenario: Canonical batch reference mismatch

- **WHEN** a worker result disagrees with its canonical request, summary, or manifest
- **THEN** the supervisor rejects the result without recomputing trading metrics or sizing.

#### Scenario: Valid-looking bundle outside canonical storage

- **WHEN** a worker reports a structurally valid bundle below its session directory or another non-canonical path
- **THEN** the supervisor rejects it before reading bundle contents.

#### Scenario: AutoResearch does not select quantity

- **WHEN** AutoResearch constructs or interprets a candidate
- **THEN** it supplies no independent fixed/equity sizing choice and derives no quantity from research metrics.
