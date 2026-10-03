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

The block SHALL also carry a `view` descriptor listing one or more views; each
view SHALL declare its x and y dimension ids, the dimension ids exposed as
controls, the default metric, and, for an aggregated map, the dimension ids it
aggregates over. The descriptor tells the frontend how the Experiment is shown;
the frontend SHALL NOT derive views from the dimension list.

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
- **THEN** requests for that Experiment return a stable error naming the missing unit.

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

Research Service SHALL serve exactly three experiment routes:
`GET /api/research/experiments` (the registry contents, read without touching any
manifest, table or run), `GET /api/research/experiments/{experiment_id}` (the
manifest) and `GET /api/research/experiments/{experiment_id}/results`. The results
route SHALL return columnar JSON (`columns`, `rows`, `data`), SHALL accept an
optional column selection, and SHALL filter by equality on dimension ids given as
query parameters. It SHALL use the semantic ids declared in `result_schema`,
SHALL translate them to physical table columns including every unit column of a
multi-grid dimension, and SHALL NOT require or return physical column names. An
unknown id SHALL be HTTP 400. The service SHALL NOT write to Experiment folders
and SHALL NOT expose a Surface, cells, aggregates or findings route.

#### Scenario: Registry read is cheap

- **WHEN** the experiment list is requested
- **THEN** only `experiments.json` is read.

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

#### Scenario: Malformed table

- **WHEN** a requested experiment's manifest or table is malformed
- **THEN** that request returns a stable error naming the problem and other
  experiments are unaffected.

### Requirement: Run id is optional drill-down

A missing run bundle SHALL NOT invalidate an Experiment, a registry entry or any
result row. Opening a run whose bundle is missing SHALL fail through the existing
run API as HTTP 404.

#### Scenario: Missing bundle

- **WHEN** a row's `run_id` has no bundle and the user opens it
- **THEN** the existing run API returns 404 and nothing else is affected.

### Requirement: Registry and data root

The experiment registry SHALL be read from `analysis/experiments.json` under the
analysis root, which SHALL be derived from the configured research data root
(`<artifacts_root>/../analysis`) and SHALL NOT have its own setting.

#### Scenario: One root

- **WHEN** the artifacts root is configured
- **THEN** the analysis root is its sibling `analysis` directory.

### Requirement: One-time preparation of historical data

Existing historical artifacts SHALL be prepared once, outside runtime, in
stages that stop on failure and move nothing until the dry-run report has been
reviewed: inventory and dry-run; normalization of referenced run bundles into
`<artifacts_root>/<run_id>` by rename with a rollback journal; preparation of the
two EMA500 datasets (manifest `result_schema` with `view`, `experiments.json`,
nullable `run_id` column in the trailing table); verification (table metrics
unchanged, equal to existing HTML data where it exists, every non-null `run_id`
has a bundle at the canonical location); and a separate cleanup requiring explicit
approval. Identical copies of a run SHALL collapse to one; conflicting copies, or a
folder name different from `manifest.run_id`, SHALL stop the preparation. Run ids
SHALL NOT change and nothing SHALL be deleted before verification passes.

#### Scenario: Conflicting duplicate

- **WHEN** two copies of one `run_id` have different manifests
- **THEN** the preparation stops and reports the run id for a manual decision.

#### Scenario: Dry run

- **WHEN** the preparation is run in dry-run mode
- **THEN** it writes a plan and report and changes no file.

### Requirement: Trailing run links

The preparation SHALL add `run_id` to a trailing row only when a run is
confirmed for it: the run's own recorded strategy spec declares the row's
dimension values, the run's recorded metrics equal the row's, and, only when the
row carries an authoritative `market_data_hash`, the run's market hash equals it.
Metric equality alone SHALL NOT link a run. A row with more than one such run, and
every other candidate pair, SHALL remain without `run_id` and be listed in the
report. No market-hash tie-break and no table-wide market window SHALL be used.

#### Scenario: Two runs for one row

- **WHEN** two runs satisfy the confirmation for one row
- **THEN** no `run_id` is written for that row and the report names both runs.

#### Scenario: Numbers match but the spec differs

- **WHEN** a run's metrics equal a row's but its recorded spec does not declare
  the row's dimension values
- **THEN** no `run_id` is written.
