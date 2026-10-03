## ADDED Requirements

### Requirement: Surface tab

The Research Workbench SHALL provide a "Surface" tab in the order
`Chart | Surface | Reports | Strategy Composer`. The Surface tab is a
visualisation of an Experiment's ready-made result table: it SHALL provide an
Experiment selector built from the Experiment list, and for the selected
Experiment the views declared by its manifest `view` descriptor (controls,
heatmap, optional aggregated map), metric selection, filters, and, when the
manifest declares `arms`, baseline/difference. It SHALL NOT recompute any trading
metric, read HTML, or look at runs on disk. It SHALL NOT require a selected run
and SHALL be reachable while no run is selected.

#### Scenario: Open the tab without a run

- **WHEN** the user opens the Surface tab and no run is selected
- **THEN** the Experiment selector and the declared view are shown.

#### Scenario: Request only what is displayed

- **WHEN** the user fixes an initial stop
- **THEN** the results request is filtered by the dimension id (`sl`) to that value
  and the full table is not requested.

### Requirement: Manifest-declared views

The Surface tab SHALL build its views from the manifest `view` descriptor
(x and y dimension ids, the dimensions exposed as controls, default metric,
optionally one dimension id for a filmstrip of small heatmap copies, and for an
aggregated map the dimensions aggregated over) and SHALL NOT offer
arbitrary choice of axes. An Experiment without a `view` descriptor SHALL be
reported as not viewable.

#### Scenario: Trailing filmstrip

- **WHEN** the trailing width × lookback view declares a filmstrip over the
  trigger dimension
- **THEN** a row of small heatmaps, one per trigger value at the selected
  distance, is shown and selecting one sets the trigger control.

#### Scenario: Ratio experiment

- **WHEN** an Experiment declares one view with width and lookback axes and
  controls for SL and TP ratio, and no arms
- **THEN** only that view, metric selection and filters are shown.

### Requirement: Explicit units

Every dimension control and readout SHALL show the dimension's unit. For a
dimension with several grids, the readout SHALL show the value in the active
grid's unit and its conversion to the other unit at the selected initial stop
(`ATR = R × SL`). Tooltips SHALL show both units.

#### Scenario: R grid readout

- **WHEN** the R grid is active with SL 5 ATR and trigger 7R
- **THEN** the readout shows `7R` and `= 35 ATR at SL 5`.

### Requirement: Metric filters

The tab SHALL support any number of conditions `metric ≥ value` or
`metric ≤ value` over declared metrics and, when `arms` are declared, over their
differences to the baseline arm. All conditions SHALL apply together (AND). Points
that fail any condition SHALL be shown greyed out and a counter SHALL show passing
points.

#### Scenario: Two conditions

- **WHEN** the user sets `PF ≥ 1.3` and `short net ≥ 0`
- **THEN** only points meeting both keep their colour and the counter shows their
  number out of all points.

### Requirement: One point model and cell details

Every result row SHALL be treated identically as a point with coordinates,
metrics and an optional `run_id`; the frontend SHALL NOT distinguish point kinds.
Clicking a point SHALL show its details (coordinates, metrics, declared
provenance) as local view state; this selection SHALL NOT be derived from or
written to `selectedRunId`. For a point with a `run_id`, the details SHALL offer
an action that calls the existing run selection with that `run_id` and opens the
Chart. For a point without a `run_id`, the details SHALL state that no detailed
Engine run is available and offer no such action. Provenance SHALL be shown from
the declared provenance, never inferred from `run_id`.

#### Scenario: Point with a run

- **WHEN** the user clicks a point with a `run_id` and chooses to open the run
- **THEN** `selectedRunId` becomes that `run_id` and Chart and Reports load it
  through their existing path.

#### Scenario: Point without a run

- **WHEN** the user clicks a point without a `run_id`
- **THEN** its metrics are shown, `selectedRunId` is unchanged, and no open
  action is offered.

### Requirement: Surface boundary to the workbench

The only link between the Surface tab and the rest of the workbench SHALL be the
existing run selection with a `run_id`. The Surface tab SHALL NOT import chart or
chart-runtime modules, and SHALL NOT read or write chart, report or trade/bar
focus state. Its own state (selected Experiment, metric, controls, filters,
selected point) SHALL be local to the Surface view; it SHALL persist while the
user switches between Chart, Surface and Reports. The Surface view SHALL render
outside the run-loading gate so that it works while no run is selected.

#### Scenario: Surface → Chart → Surface

- **WHEN** the user sets controls, opens a run in the Chart, and returns to Surface
- **THEN** the same Experiment, controls and filters are shown.

### Requirement: Legacy run dropdown

The context-bar run dropdown SHALL be hidden in production builds and kept in the
code as legacy, marked as a candidate for removal. The context bar SHALL show the
selected run id as read-only text. Historical runs SHALL NOT be added to
`/api/research/runs` or to the dropdown for the purpose of the context bar.

#### Scenario: Production context bar

- **WHEN** the workbench runs with default settings
- **THEN** the context bar shows the selected run id as text and no run dropdown.

### Requirement: Startup without a selected run

The workbench SHALL start with `selectedRunId` equal to null and SHALL NOT call
`/api/research/runs` at startup. Chart and Reports SHALL show an explicit idle
state ("Open a run from the Surface tab") instead of the loading view while no
run is selected. Existing Composer behaviour SHALL remain functional after the
removal of startup `/api/research/runs` loading.

#### Scenario: Fresh start

- **WHEN** the workbench loads without a `run` parameter
- **THEN** no run is selected, no run list is requested, and Chart and Reports
  show the idle state.

#### Scenario: Composer after a backtest

- **WHEN** the user runs a backtest from the Composer
- **THEN** the resulting run is selected and shown as before.

#### Scenario: Failed load stays selected

- **WHEN** the selected run fails to load and the user presses Retry
- **THEN** the same `run_id` is requested again and stays selected.
