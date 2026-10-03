## ADDED Requirements

### Requirement: Copy-free multi-root discovery

Research Service SHALL index run bundles in place under the primary
`artifacts_root` and under each configured extra index root, without copying,
moving, linking or modifying them. A run bundle SHALL be any directory named
`run_` followed by 32 lowercase hexadecimal characters that contains
`manifest.json`, at any depth below a root. Extra roots SHALL be treated as
read-only.

#### Scenario: Run bundle inside a canonical research folder

- **WHEN** an extra root contains
  `<test>/runs/<batch_id>/candidates/<run_id>/manifest.json`
- **THEN** the index records that bundle under its `run_id`
- **AND** no file is created, changed or removed under the extra root.

#### Scenario: Directory without a manifest

- **WHEN** a directory named like a run id has no `manifest.json`
- **THEN** it is not indexed.

### Requirement: Exact run identity

The index SHALL identify a bundle copy by `run_id` and `manifest_sha256`, the
SHA-256 of the `manifest.json` bytes. Locations that resolve to the same real
directory SHALL count as one copy.

#### Scenario: Symlinked location

- **WHEN** two discovered paths resolve to the same real directory
- **THEN** the index records one copy of that run.

#### Scenario: Byte-identical copies in two roots

- **WHEN** the same `run_id` has copies with equal `manifest_sha256` in the
  primary root and in an extra root
- **THEN** the run is resolved to the primary-root copy
- **AND** the extra-root copy is recorded as a duplicate.

### Requirement: Deterministic resolution and conflicts

A bare `run_id` SHALL resolve only when all its copies share one
`manifest_sha256`. The read location SHALL be the copy with the lowest root
rank (primary root first, then extra roots in configured order), then the
lexicographically smallest real path. When copies of one `run_id` have
different `manifest_sha256` values, the run SHALL be ambiguous and SHALL NOT be
resolved from the bare id. A caller SHALL be able to select one copy exactly by
passing its `manifest_sha256`.

#### Scenario: Conflicting copies

- **WHEN** two copies of `run_x` have different manifest hashes
- **THEN** a bare-id lookup of `run_x` fails with `run_ambiguous`
- **AND** a lookup of `run_x` with one of the two manifest hashes resolves to
  that copy.

#### Scenario: Qualifier does not match

- **WHEN** a lookup passes a `manifest_sha256` that no copy of the run has
- **THEN** the lookup fails as run not found.

### Requirement: Index lifecycle and visibility

The index SHALL be built at service start without blocking reads of runs in
the primary root, SHALL persist a snapshot under
`<artifacts_root>/.run_index/`, SHALL add newly published bundles at publish
time, and SHALL be rebuildable on request. The service SHALL expose index state
(building, ready, failed), totals per root, duplicate count, and the list of
ambiguous run ids.

#### Scenario: Lookup during the initial build

- **WHEN** the index is still building and a run that exists only in an extra
  root is requested
- **THEN** the request fails with a stable `run_index_building` error rather
  than not found.

#### Scenario: Index report

- **WHEN** the index state endpoint is called after a build
- **THEN** it returns the state, per-root copy counts, the number of
  duplicate copies, and every ambiguous run id.

#### Scenario: Newly published run

- **WHEN** a backtest is published to the primary root
- **THEN** its `run_id` resolves through the index without a rebuild.
