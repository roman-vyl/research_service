## ADDED Requirements

### Requirement: Surface contract

A research surface SHALL be a folder under `RESEARCH_SURFACES_ROOT` that
contains `surface.json` with `contract_version` `research_surface.v1`. The
contract SHALL declare `surface_id`, title, market (ticker, timeframe,
`from_ms`, `to_ms`, `market_data_hash`), the cells table path, axes, arms,
metrics, and optionally the findings file. Every axis SHALL declare its unit.
An axis whose value can be defined in more than one unit SHALL declare each
grid, its unit, and the column holding the value in each unit, plus the column
that names the grid of a row.

#### Scenario: Trailing geometry axes

- **WHEN** a surface defines trailing trigger and distance on an ATR grid and
  an R grid
- **THEN** `surface.json` declares both grids with units `ATR` and `R`, the
  columns `trail_trigger_atr`, `trail_distance_atr`, `trigger_r`,
  `trail_distance_r`, and the grid column `geometry_grid_unit`.

#### Scenario: Missing unit

- **WHEN** an axis in `surface.json` has no unit
- **THEN** the surface is reported invalid and is not served.

### Requirement: Cell identity and provenance

Every row of a surface cells table SHALL carry `cell_id`, `arm`, all axis
columns, `provenance`, `run_id` and `run_manifest_sha256`. `cell_id` SHALL be
`cell_` followed by the first 24 hexadecimal characters of the SHA-256 of the
canonical JSON of the surface `market_data_hash`, the arm and the axis values
in their declared units, and SHALL be unique within the surface. `provenance`
SHALL be one of `engine`, `engine_confirmed_replay`, `replay`. `run_id` and
`run_manifest_sha256` SHALL both be present for `engine` and
`engine_confirmed_replay` rows and both empty for `replay` rows.

#### Scenario: Replay row

- **WHEN** a row's metrics come from replay and no Engine run exists for it
- **THEN** its `provenance` is `replay` and its `run_id` is empty.

#### Scenario: Linked run must resolve

- **WHEN** a row has a `run_id` and `run_manifest_sha256`
- **THEN** the run index resolves exactly that copy
- **AND** a row whose linked run does not resolve makes the surface invalid.

#### Scenario: Duplicate cell id

- **WHEN** two rows of one surface produce the same `cell_id`
- **THEN** the surface is reported invalid.

### Requirement: Read-only surfaces API

Research Service SHALL serve surfaces read-only:
`GET /api/research/surfaces`, `GET /api/research/surfaces/{surface_id}`,
`GET /api/research/surfaces/{surface_id}/cells`,
`GET /api/research/surfaces/{surface_id}/geometry-aggregates`, and
`GET /api/research/surfaces/{surface_id}/findings`. The cells route SHALL
filter by axis columns and arms given as query parameters and SHALL return a
columnar payload of only the matching rows. The service SHALL NOT write to
surface folders.

#### Scenario: Slice for one geometry

- **WHEN** the cells route is called with an SL, a grid, a T and a D value and
  the arms `trailing_no_tp` and `control_tp5r`
- **THEN** the response contains exactly the matching rows of both arms with
  `cell_id`, axis values, metrics, `provenance`, `run_id` and
  `run_manifest_sha256`.

#### Scenario: Geometry aggregates against a comparison arm

- **WHEN** geometry aggregates are requested for an SL, a grid and a
  comparison arm
- **THEN** the response contains, for every admissible (T, D) of that grid,
  the median net change, the median net multiple over cells where the
  comparison arm is profitable, the share of cells better on net, PF and max
  drawdown together, and the median changes of PF, max drawdown and
  cumulative R.

#### Scenario: Unknown surface

- **WHEN** a route names a surface id that does not exist
- **THEN** the response is HTTP 404.

#### Scenario: Invalid surface

- **WHEN** a surface fails contract validation
- **THEN** its routes return a stable structured error naming the violation
  and the surface list marks it invalid.

### Requirement: Migration of existing EMA500 surfaces

An offline, idempotent migration script SHALL write `surface.json` for the
BTCUSDT.P / EMA500 surfaces `width_x_untouched_x_stop_x_ratio_4d` and
`width_x_untouched_x_stop_x_trailing_geometry_4d`, back up each `runs.csv`
before changing it, and add `cell_id`, `provenance`, `run_id` and
`run_manifest_sha256` without changing any existing column value.

#### Scenario: Historical surface

- **WHEN** the migration runs on `width_x_untouched_x_stop_x_ratio_4d`
- **THEN** every row gets `provenance` `engine`, keeps its existing `run_id`,
  and gets the `run_manifest_sha256` of the bundle the index resolves.

#### Scenario: Trailing surface

- **WHEN** the migration runs on
  `width_x_untouched_x_stop_x_trailing_geometry_4d`
- **THEN** rows matched to an existing Engine run get `provenance`
  `engine_confirmed_replay` and that run's identity, all other replay rows get
  `provenance` `replay`, and Engine runs without a matching replay row are
  added as `engine` rows.

#### Scenario: Re-running the migration

- **WHEN** the migration runs a second time
- **THEN** it produces byte-identical files.
