## ADDED Requirements

### Requirement: Export a candidate to the Runtime catalog

`POST /api/research/candidates/{candidate_id}/runtime-export` SHALL write one new
JSON file into the directory named by `RESEARCH_RUNTIME_SPECS_PATH`, named
`<ticker lowercased, "." replaced by "_">-<candidate_id>.json`, and SHALL return
the file name and the Runtime identity.

#### Scenario: Engine-backed candidate

- **WHEN** a candidate whose snapshot holds a spec is exported
- **THEN** a file `btcusdt_p-<candidate_id>.json` appears in the directory
- **AND** the response returns its name and Runtime identity.

### Requirement: Exported file content

The file SHALL contain `strategy_id`, `ticker`, `base_timeframe` and `raw_spec`
copied unchanged from `strategy_spec_snapshot.spec`, `enabled: false`, and a
`research_source` block with `candidate_id`, `experiment_id`, `coords`, `run_id`
and `exported_at`. It SHALL NOT contain `strategy_instance_id`,
`strategy_version` or `compatibility_profile`.

#### Scenario: Arrives switched off

- **WHEN** a candidate is exported
- **THEN** the file has `enabled: false` and its four strategy fields equal the
  snapshot's.

### Requirement: Fitness for Runtime is the owner's decision

Research SHALL check only the presence and type of the four strategy fields and
SHALL NOT judge whether the candidate suits live trading. A record whose
`strategy_spec_snapshot` is null or has no `spec` SHALL be refused with HTTP 409
`no_strategy_spec`.

#### Scenario: Candidate without a spec

- **WHEN** a replay candidate with a null snapshot is exported
- **THEN** the answer is 409 `no_strategy_spec` and nothing is written.

### Requirement: Runtime identity

Research SHALL compute a spec's Runtime identity with Strategy Runtime's formula:
the strategy id, a colon, and the first 24 hex characters of SHA-256 over the
canonical JSON (sorted keys, compact separators, non-ASCII kept, NaN refused) of
`strategy_id`, `ticker`, `base_timeframe` and `raw_spec`.

#### Scenario: Pinned against Runtime

- **WHEN** the identity of a fixed test spec is computed
- **THEN** it equals the id Strategy Runtime derives for the same spec.

### Requirement: No duplicate identities

Before writing, Research SHALL compute the identity of every direct, visible,
lowercase `.json` file of the directory that parses and has the four fields;
other files SHALL be skipped. When one has the candidate's identity, export
SHALL be HTTP 409 `runtime_duplicate` naming that file, and nothing SHALL be
written.

#### Scenario: Exported twice

- **WHEN** a candidate is exported a second time
- **THEN** the answer is 409 `runtime_duplicate` with the first file's name.

#### Scenario: Same strategy written by hand

- **WHEN** the directory has a hand-written file with the same four fields in
  another key order and indentation
- **THEN** export is 409 `runtime_duplicate`.

#### Scenario: Broken neighbour file

- **WHEN** the directory has a file that is not valid JSON
- **THEN** export of an unrelated candidate succeeds.

### Requirement: Never overwrite, never half-written

The file SHALL be written to a hidden temporary file in the same directory and
then created under its final name only if that name does not exist; an existing
name SHALL be HTTP 409 `runtime_file_exists`. Research SHALL NOT modify or delete
any existing file of the directory and SHALL NOT create the directory.

#### Scenario: Name taken

- **WHEN** a file with the target name exists
- **THEN** the answer is 409 `runtime_file_exists` and the existing file is
  unchanged.

### Requirement: Runtime catalog configuration

When `RESEARCH_RUNTIME_SPECS_PATH` is unset, export SHALL be HTTP 503
`runtime_catalog_unconfigured`; when it does not name a readable directory,
HTTP 503 `runtime_catalog_unavailable`.

#### Scenario: Not configured

- **WHEN** the setting is unset
- **THEN** export answers 503 and the candidate list still works.

### Requirement: Runtime presence in the candidate list

`GET /api/research/candidates` SHALL add `current.runtime` to every record:
`{"present": true, "file": <name>, "enabled": <bool>}` when a catalog file has
the candidate's identity, `{"present": false}` when none has, and null when the
setting is unset, the directory is unreadable or the record has no spec. It SHALL
be computed from the directory on each list and SHALL NOT be stored in the record.

#### Scenario: Enabled by hand

- **WHEN** the exported file's `enabled` is set to true outside Research
- **THEN** the next list shows `present: true, enabled: true`.

### Requirement: Export leaves the shortlist unchanged

A successful export SHALL append one `runtime_export` line to
`candidates_journal.jsonl` and SHALL NOT change `candidates.json`.

#### Scenario: Record untouched

- **WHEN** a candidate is exported
- **THEN** `candidates.json` is byte-identical and the journal has one new line.
