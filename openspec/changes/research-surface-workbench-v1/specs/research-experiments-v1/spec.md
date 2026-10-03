## ADDED Requirements

### Requirement: Experiment bundle

An Experiment SHALL be a folder under the research analysis root containing a
`manifest.json` (machine-readable authority) and the result table it names.
`findings.jsonl`, `README.md` and `report.html` MAY accompany it. Research
Service SHALL NOT require `README.md` or `report.html`, SHALL NOT parse HTML,
and SHALL NOT take identity or resolution semantics from folder or HTML file
names. The existing result table name (for example `runs.csv`) SHALL be kept.

#### Scenario: Missing README and HTML

- **WHEN** an Experiment folder has a manifest and a result table but no README
  or HTML
- **THEN** the Experiment is served normally.

### Requirement: Manifest result schema

The Experiment `manifest.json` SHALL carry one additive block `result_schema`
with `contract_version` `research_experiment_result_schema.v1`, the result
`table`, the `run_id_column`, a `provenance` declaration, optional `row_columns`,
`dimensions`, optional `arms`, and `metrics`. Existing manifest keys SHALL be
left unchanged.

Every dimension SHALL declare `id`, `column` and `unit`. A dimension that exists
in more than one unit SHALL instead declare `grid_column` and, for each grid, the
column and unit holding the value in that grid. Every metric SHALL declare
`column`, `label` and `format`; `format` `fraction` SHALL mean the stored value
is a fraction. Arms SHALL declare the arm column, a role (`treatment` or
`comparison`) per arm value, the baseline arm, and the dimensions on which
comparison rows are matched to treatment rows.

#### Scenario: Trailing dual grid

- **WHEN** the trailing experiment declares trigger and distance
- **THEN** the manifest names the grid column `geometry_grid_unit` and, per
  grid, the ATR columns `trail_trigger_atr` / `trail_distance_atr` and the R
  columns `trigger_r` / `trail_distance_r`
- **AND** no consumer needs to infer a relation between columns from their names.

#### Scenario: Fraction metrics

- **WHEN** `return_pct` is declared with format `fraction`
- **THEN** its value `0.25` means 25 %.

#### Scenario: Missing unit

- **WHEN** a dimension has neither a unit nor grids with units
- **THEN** the Experiment is reported invalid.

### Requirement: Provenance is stored, not inferred

A result table SHALL declare row provenance either as a constant
(`provenance.value`) or a column (`provenance.column`), with origin values such
as `engine` and `replay`. Provenance SHALL NOT be derived from the presence or
absence of `run_id`. `run_id` SHALL mean only that a materialized Engine run
exists for drill-down.

#### Scenario: Replay row with a run

- **WHEN** a replay-produced row has a `run_id` of a confirming Engine run
- **THEN** its provenance is still the declared origin of the table or column
- **AND** the `run_id` only enables drill-down.

### Requirement: Row-level market identity

A result table MAY carry market identity columns declared in `row_columns`; they
SHALL be treated as authoritative row provenance. The manifest SHALL NOT assert
one experiment-wide market hash or window unless the table has exactly one.

#### Scenario: Several market snapshots

- **WHEN** a table's rows carry seven different `market_data_hash` values
- **THEN** the manifest declares the column in `row_columns` and does not
  declare a single hash.

### Requirement: Canonical run location

Every Engine run bundle SHALL have exactly one physical location,
`<artifacts_root>/<run_id>/`, regardless of whether, in how many, or in which
Experiments it is referenced. Resolving a `run_id` SHALL be that single rule;
Research Service SHALL NOT use a run index, a fallback or second root, recursive
discovery, symlink resolution, snapshots, root ranking or a manifest-hash
qualifier, and publishing an Experiment SHALL NOT move a run.

#### Scenario: Run referenced by no Experiment

- **WHEN** a run bundle exists in the artifacts root and no Experiment refers to it
- **THEN** it remains readable at the same location.

### Requirement: Experiment identity

An Experiment SHALL be identified by `experiment_id`, recorded both in the
registry and in the manifest and unique within the registry. The manifest
`test_id` SHALL be treated only as a legacy domain test name; it SHALL NOT be
used as an identity, registry key or route parameter.

#### Scenario: Same test name under two anchors

- **WHEN** the EMA500 and EMA1000 folders both carry `test_id`
  `width_x_untouched_x_stop_x_ratio_4d`
- **THEN** they have different `experiment_id` values and are served separately.

### Requirement: Experiment registry

Available Experiments SHALL be listed in `analysis/experiments.json` with, per
entry, `experiment_id` (unique within the registry), `title`, `ticker`, `anchor`
and the relative `manifest` path, and nothing copied from the manifest. An
Experiment absent from the registry SHALL NOT be served.

#### Scenario: Unregistered folder

- **WHEN** a folder has a valid manifest but no registry entry
- **THEN** it does not appear in the Experiment list.

### Requirement: Read-only Experiment API

Research Service SHALL serve
`GET /api/research/experiments`,
`GET /api/research/experiments/{experiment_id}` (the manifest),
`GET /api/research/experiments/{experiment_id}/results` and
`GET /api/research/experiments/{experiment_id}/findings`. The results route
SHALL return columnar JSON (`columns`, `rows`, `data`), SHALL accept an optional
column selection, and SHALL filter by equality on dimension ids given as query
parameters. The route SHALL use the semantic ids declared in `result_schema`
(dimension and metric ids), SHALL translate them to physical table columns
including every unit column of a multi-grid dimension, and SHALL NOT require or
return physical column names. An unknown dimension id SHALL be HTTP 400. The service SHALL NOT write to Experiment folders and SHALL
NOT expose a backend entity or route named Surface, a cells route or an
aggregates route.

#### Scenario: Slice by initial stop

- **WHEN** results are requested with `sl=5`
- **THEN** only rows with that value are returned, in columnar form, with
  semantic column ids.

#### Scenario: Multi-grid dimension

- **WHEN** results are requested with `grid=R` and `trigger=7`
- **THEN** the backend filters on the grid column and on the R-unit trigger
  column named by the manifest, and the client never sees those column names.

#### Scenario: Unknown experiment

- **WHEN** an unregistered `experiment_id` is requested
- **THEN** the response is HTTP 404.

### Requirement: Experiment validation

Research Service SHALL validate each registered Experiment (cached by file
modification time and size): the manifest and `result_schema` are well formed,
the table header contains every declared column, dimension keys are unique per
arm, and every non-empty `run_id` exists as `<artifacts_root>/<run_id>/manifest.json`.
An invalid Experiment SHALL remain in the list marked invalid, and its data
routes SHALL return a stable error naming the violation.

#### Scenario: Run id without a bundle

- **WHEN** a row names a `run_id` that has no bundle at the canonical location
- **THEN** the Experiment is reported invalid with that run id.

### Requirement: Controlled migration of existing artifacts

Existing artifacts SHALL be brought to this contract by a staged migration that
moves nothing until its validation phases pass: inventory; dry-run report;
validation; normalization of referenced runs into `<artifacts_root>/<run_id>/`
by rename with a rollback journal; data edits; parity validation; and a
separate, last cleanup phase requiring explicit approval. Identical copies of a
run SHALL collapse to one; copies with different manifests, or a folder name
different from `manifest.run_id`, SHALL stop the migration. Run ids SHALL NOT
change. The migration SHALL NOT delete anything before parity validation passes.

#### Scenario: Conflicting duplicate

- **WHEN** two copies of one `run_id` have different manifests
- **THEN** the migration stops and reports the run id for a manual decision.

#### Scenario: Dry run

- **WHEN** the migration is run in dry-run mode
- **THEN** it writes a plan and report and changes no file.

### Requirement: Trailing result table run links

The migration SHALL add a nullable `run_id` column to the trailing geometry
result table without changing any existing value. Every candidate (run, row)
pair SHALL be classified CONFIRMED, POSSIBLE or NO LINK. A pair is CONFIRMED
only if the run's own recorded strategy spec declares the row's dimension
values, the run's recorded metrics equal the row's, and, when the row carries an
authoritative `market_data_hash`, the run's market hash equals that row value.
Metric equality alone SHALL NOT confirm a pair. `run_id` SHALL be written only
for CONFIRMED pairs with exactly one CONFIRMED run for the row. Market hash
SHALL NOT be used as a tie-break when the row has no market identity column, and
no table-wide market window SHALL be assumed. Rows with several CONFIRMED runs,
POSSIBLE pairs and NO LINK pairs SHALL remain without `run_id` and be listed in
the migration report.

#### Scenario: Two confirmed runs for one row

- **WHEN** two runs are CONFIRMED for one row
- **THEN** no `run_id` is written for that row
- **AND** the report names both runs.

#### Scenario: Numbers match but the spec differs

- **WHEN** a run's metrics equal a row's but its recorded spec does not declare
  the row's dimension values
- **THEN** the pair is POSSIBLE and no `run_id` is written.

### Requirement: Parity of migrated data

After migration, every non-empty `run_id` SHALL resolve to
`<artifacts_root>/<run_id>/`, every linked run's metrics SHALL equal its row,
and the result tables SHALL match the data of the existing HTML presentations.

#### Scenario: Historical HTML parity

- **WHEN** parity validation runs on ratio_4d
- **THEN** all 12 672 rows equal the data embedded in its existing HTML.
