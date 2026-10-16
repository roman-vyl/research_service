## ADDED Requirements

### Requirement: Create-only export to the Runtime catalog

`POST /api/research/candidates/{candidate_id}/runtime-export` SHALL create one new
JSON file in the directory named by `RESEARCH_RUNTIME_SPECS_PATH` and SHALL return
its name and Runtime identity. The route SHALL take no body and no query
parameters; any supplied body field, including `enabled`, SHALL be rejected with
HTTP 422. Research SHALL NOT expose any route that updates, enables, disables or
deletes a file of that directory, and SHALL NOT open an existing file of it for
writing.

#### Scenario: Engine-backed candidate

- **WHEN** a candidate whose snapshot holds a spec is exported
- **THEN** a file `btcusdt_p-<candidate_id>.json` appears in the directory
- **AND** the response returns its name and Runtime identity.

#### Scenario: Body with enabled

- **WHEN** the request carries `{"enabled": true}`
- **THEN** the answer is 422 and nothing is written.

#### Scenario: No mutating routes

- **WHEN** the application's routes are listed
- **THEN** the only route touching the catalog directory for writing is the
  export route.

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

#### Scenario: Accepted by Runtime's rules

- **WHEN** the written file is checked with Runtime's acceptance rules
- **THEN** it is accepted and its identity equals the one returned.

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
`strategy_id`, `ticker`, `base_timeframe` and `raw_spec` only.

#### Scenario: Pinned against Runtime

- **WHEN** the identity of a fixed test spec is computed
- **THEN** it equals the id Strategy Runtime derives for the same spec.

#### Scenario: Provenance does not change identity

- **WHEN** only `research_source` or `enabled` of a file differs
- **THEN** the computed identity is the same.

### Requirement: Catalog scan matches Runtime

Research SHALL scan the catalog directory with Runtime's rules: direct entries
that are files, name not starting with ".", suffix exactly `.json`, JSON parsed
with NaN and Infinity rejected. A file SHALL count as a deployment only if Runtime
would accept it (a JSON object without `strategy_instance_id`, `strategy_version`
or `compatibility_profile`, with boolean `enabled`, non-empty string `ticker`,
`base_timeframe` and `strategy_id`, and object `raw_spec`). Any other file SHALL
be skipped and SHALL NOT block an export or count as a duplicate.

#### Scenario: Broken neighbour file

- **WHEN** the directory has a file that is not valid JSON, a hidden file, a nested
  file, a file with suffix `.JSON` and a file Runtime would reject
- **THEN** export of an unrelated candidate succeeds.

#### Scenario: Rejected file with the same strategy

- **WHEN** the directory has a file with the candidate's four fields that Runtime
  would reject (for example `enabled` as a string)
- **THEN** export succeeds, because Runtime does not count that file.

### Requirement: No duplicate identities

When an accepted catalog file has the candidate's Runtime identity, export SHALL
be HTTP 409 `runtime_duplicate` naming every such file, and nothing SHALL be
written.

#### Scenario: Exported twice

- **WHEN** a candidate is exported a second time
- **THEN** the answer is 409 `runtime_duplicate` with the first file's name.

#### Scenario: Same strategy written by hand

- **WHEN** the directory has a hand-written file with the same four fields in
  another key order and indentation
- **THEN** export is 409 `runtime_duplicate`.

### Requirement: Serialized export

Scan, duplicate check and publish SHALL run under one exclusive inter-process lock
held in Research's own storage, not in the catalog directory. A waiting export
SHALL fail with HTTP 503 `runtime_export_busy` after 10 seconds. The guarantee
SHALL be stated as covering Research processes sharing the lock file and SHALL NOT
be claimed against writers outside Research.

#### Scenario: Concurrent export with one identity

- **WHEN** two exports of different candidates with the same Runtime identity run
  at the same time in separate processes
- **THEN** exactly one file exists, one request succeeds and the other is 409
  `runtime_duplicate`.

#### Scenario: Concurrent exports of different identities

- **WHEN** two exports with different identities run at the same time
- **THEN** both succeed and both files are complete.

#### Scenario: External writer between scan and publish

- **WHEN** a file with the same identity is created outside Research after the
  scan
- **THEN** the exported file is still created without overwriting anything
- **AND** the next list shows `duplicate: true` with both names.

### Requirement: Safe file name

The file name SHALL be `<slug>-<candidate_id>.json`, where `slug` is the record's
`ticker` lowercased with each run of characters outside `[a-z0-9]` replaced by one
`_`, trimmed of `_`, at most 40 characters, and `spec` when empty, and
`candidate_id` is taken from the stored record and matches `^cand_[0-9a-f]{24}$`.
The name SHALL contain no path separator, SHALL NOT start with ".", SHALL NOT
exceed 255 bytes, and the resolved parent of the final path SHALL equal the
resolved catalog directory; otherwise export SHALL be HTTP 500
`runtime_invalid_name` with nothing written.

#### Scenario: Hostile ticker

- **WHEN** a spec's ticker is `../../etc/X` or `/abs`, contains control or non-ASCII
  characters, starts with ".", or is 300 characters long
- **THEN** the file is created inside the catalog directory with a name made only
  of `[a-z0-9_-]` and `.json`, or the export is refused, and nothing is written
  outside the directory.

### Requirement: Never overwrite, never half-written

The file SHALL be written to a hidden temporary file in the catalog directory,
flushed, and then created under its final name only if that name does not exist;
an existing name SHALL be HTTP 409 `runtime_file_exists`. Research SHALL NOT
modify, rename or delete any existing file of the directory and SHALL NOT create
the directory.

#### Scenario: Name taken

- **WHEN** a file with the target name exists
- **THEN** the answer is 409 `runtime_file_exists` and the existing file is
  unchanged.

#### Scenario: Existing files untouched

- **WHEN** any export succeeds or fails
- **THEN** every file that existed before has the same bytes and mtime.

### Requirement: Filesystem failures

When the temporary file cannot be created or written, the export SHALL be HTTP
500 `runtime_write_failed`; when the final name cannot be created for a reason
other than existing, HTTP 500 `runtime_publish_failed`, with no fallback to a
non-atomic write. In both cases nothing SHALL be published and the temporary file
SHALL be removed. A failure to remove the temporary file after publication SHALL
NOT fail the export. Research SHALL NOT delete a published file to compensate for
any later error.

#### Scenario: Disk full while writing

- **WHEN** writing the temporary file raises an out-of-space error
- **THEN** the answer is 500 `runtime_write_failed`, no temporary file remains and
  no final file exists.

#### Scenario: Link refused

- **WHEN** creating the final name fails with a permission error
- **THEN** the answer is 500 `runtime_publish_failed`, no temporary file remains
  and no final file exists.

### Requirement: Journal failure does not hide a published export

When the journal line cannot be written after the file is published, the answer
SHALL be success with `journal: "failed"`, the error SHALL be logged, and the file
SHALL stay. A repeated export SHALL then answer 409 `runtime_duplicate` naming it.

#### Scenario: Journal write fails

- **WHEN** the journal append raises after publication
- **THEN** the response is 201 with `journal: "failed"` and the file exists
- **AND** a second export answers 409 `runtime_duplicate`.

### Requirement: Runtime catalog configuration

When `RESEARCH_RUNTIME_SPECS_PATH` is unset, export SHALL be HTTP 503
`runtime_catalog_unconfigured`; when it does not name a readable directory,
HTTP 503 `runtime_catalog_unavailable`.

#### Scenario: Not configured

- **WHEN** the setting is unset
- **THEN** export answers 503 and the candidate list still works.

### Requirement: Runtime presence describes the directory only

`GET /api/research/candidates` SHALL add `current.runtime` to every record,
computed from the catalog directory on each list and never stored in the record.
It SHALL describe only the presence and `enabled` value of a file and SHALL NOT
claim that Strategy Runtime loaded, selected or executes the strategy.

#### Scenario: Enabled by hand

- **WHEN** the exported file's `enabled` is set to true outside Research
- **THEN** the next list shows `present: true, enabled: true`.

### Requirement: Shapes of the Runtime presence block

`current.runtime` SHALL be `{"present": true, "file": <name>, "enabled": <bool>}`
when exactly one accepted file has the candidate's identity,
`{"present": true, "duplicate": true, "files": [...]}` when several have it,
`{"present": false}` when none has, and null when the setting is unset, the
directory is unreadable or the record has no spec.

#### Scenario: Duplicated identity

- **WHEN** two accepted files have the candidate's identity
- **THEN** the list shows `duplicate: true` with both names and no `enabled`.

#### Scenario: Not configured

- **WHEN** the setting is unset
- **THEN** `current.runtime` is null.

### Requirement: Export leaves the shortlist unchanged

A successful export SHALL append one `runtime_export` line to
`candidates_journal.jsonl` and SHALL NOT change `candidates.json`.

#### Scenario: Record untouched

- **WHEN** a candidate is exported
- **THEN** `candidates.json` is byte-identical and the journal has one new line.
