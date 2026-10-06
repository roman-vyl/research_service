# research-candidate-shortlist-v1 Specification

## Purpose
Research Service keeps the owner's shortlist of starred Surface points (candidates): one record per Experiment point, its row state against the current result table, a snapshot of the picked row and the historical strategy spec of its run, served through GET, PUT and DELETE `/api/research/candidates`.
## Requirements
### Requirement: A record is the selection

Research Service SHALL keep the user's shortlist in `analysis/candidates.json`. A
record SHALL mean that one Surface point is picked by the user, and the absence of a
record SHALL mean that it is not. A record SHALL NOT carry a status, lifecycle,
deployment or runtime field.

#### Scenario: Unstar

- **WHEN** a candidate is unstarred
- **THEN** its record is removed from `candidates.json`
- **AND** a journal line with the removed record is appended to
  `candidates_journal.jsonl`.

### Requirement: Backend-built candidate identity

The star request SHALL carry `experiment_id` and `coords` keyed by semantic ids.
The required keys SHALL be every dimension id, plus `grid` when a dimension has
grids, plus `arm` when arms are declared; any other key set SHALL be HTTP 400
`invalid_coords`. The backend SHALL canonicalize numeric coordinates
(`format(float, ".12g")`) and SHALL derive `candidate_id` from `experiment_id` and
the canonical coordinates only. `run_id` and the row index SHALL NOT be part of
the identity, and the client SHALL NOT supply `candidate_id` on star.

#### Scenario: Same point written differently

- **WHEN** a point is starred with `sl=6` and again with `sl=6.0`
- **THEN** both requests return the same `candidate_id` and one record exists.

#### Scenario: Run replaced

- **WHEN** the starred row's run is deleted and later a new run fills its `run_id`
- **THEN** the `candidate_id` is unchanged.

### Requirement: Fail closed on ambiguous rows

When the coordinates match more than one row of the result table, star SHALL be
HTTP 409 `ambiguous_row` and SHALL write nothing. When they match no row, star
SHALL be HTTP 404 `row_not_found`.

#### Scenario: Duplicate coordinates

- **WHEN** two rows share all coordinates
- **THEN** star answers 409 `ambiguous_row` and the shortlist is unchanged.

### Requirement: Snapshot and fingerprint at star

A star SHALL store the row's values for every metric of the manifest, its
provenance, `run_id` and row columns, the table's `(mtime_ns, size)`, the fixed list
of fingerprint fields (every served semantic id of the row except `run_id` and provenance) and a
SHA-256 fingerprint of their canonical values. Starring an existing candidate SHALL
return the stored record unchanged.

#### Scenario: Repeated star

- **WHEN** a starred point is starred again after its metrics changed
- **THEN** the stored snapshot and fingerprint are unchanged.

### Requirement: Strategy spec is a historical snapshot

When the row has a `run_id`, a star SHALL copy the strategy spec from that run's
`request.json` into `strategy_spec_snapshot`; when it has none, the field SHALL be
null; when the file cannot be read, the star SHALL still succeed and record the
reason. The snapshot SHALL be described and served as a historical record of what
was picked and SHALL NOT be presented as a current or deployable specification.

#### Scenario: Replay point

- **WHEN** a replay row without `run_id` is starred
- **THEN** the record is stored with `strategy_spec_snapshot` null.

### Requirement: Current row state on read

`GET /api/research/candidates` SHALL return every record with a `current` block:
`row_state`, current `run_id`, provenance, metrics and `meaning`. When the table's
`(mtime_ns, size)` equals the stored key the state SHALL be `same` without reading
the table. Otherwise the row SHALL be resolved by coordinates: one row with the
stored fingerprint SHALL be `same`, one row with another fingerprint `changed`, no
row or an unregistered or unreadable Experiment `missing`, several rows
`ambiguous`. A change of `run_id` or provenance alone SHALL NOT make a row
`changed`; the current values SHALL be reported in `current`. Columns
outside the stored fingerprint fields SHALL NOT affect the state.

#### Scenario: Run deleted

- **WHEN** the starred row's run is deleted by `research-run-deletion-v1`
- **THEN** the candidate is listed with `row_state` `same` and `run_id` null.

#### Scenario: Replay point gets an Engine run with equal metrics

- **WHEN** a starred replay row gets provenance `engine` and a `run_id` while its
  coordinates, metrics and row columns keep their canonical values
- **THEN** the candidate is listed with `row_state` `same`, `current.provenance`
  `engine` and the new `run_id`.

#### Scenario: Row recalculated

- **WHEN** a metric of the starred row changes value
- **THEN** the candidate is listed with `row_state` `changed`, current metrics and
  the unchanged snapshot.

#### Scenario: Auxiliary column added

- **WHEN** a column not declared at star time is added to the table or a metric
  is added to the manifest
- **THEN** the candidate stays `same`.

### Requirement: Meaning from the manifest

The `meaning` block SHALL be built from the registry and manifest only: title,
ticker and anchor; for each coordinate its id, label, value, unit, and the
component id and parameter from the matching `varied_params` entry when present;
and the manifest's `fixed_params` as stored.

#### Scenario: Ratio surface point

- **WHEN** a ratio Surface point is listed
- **THEN** `meaning` lists width, lookback, SL and TP ratio with labels and units
  and the manifest's fixed parameters.

### Requirement: Shortlist storage is atomic and cheap

Every change SHALL be written to a temporary file and moved over
`candidates.json` with an atomic replace, followed by one journal line. A missing
file SHALL read as an empty shortlist; an unreadable file SHALL be HTTP 500
`invalid_candidates_file` and SHALL NOT be overwritten. The shortlist routes SHALL
NOT list the artifacts root or call the run listing; reading SHALL open no run
folder, and a star SHALL open at most one run file (`request.json`). The routes
SHALL NOT write the result table, the manifest or any run folder.

#### Scenario: Listing does not touch runs

- **WHEN** the shortlist is listed
- **THEN** no run folder is opened and the artifacts root is not listed.

