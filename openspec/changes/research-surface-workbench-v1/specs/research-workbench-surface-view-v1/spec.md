## ADDED Requirements

### Requirement: Surface view

The Research Workbench SHALL provide a "Surface" tab in the order
`Chart | Surface | Reports | Strategy Composer`. The Surface view is the
interactive projection of an Experiment: it SHALL provide an Experiment
selector built from the Experiment list (grouped by ticker and anchor), controls
for the declared dimensions with the remaining dimensions fixed, a two-dimensional
heatmap, treatment/comparison/difference views over declared arms, metric
selection, filters, and aggregates computed in the frontend. It SHALL render any
Experiment generically from its manifest `result_schema` and result table and
SHALL NOT read HTML or the filesystem layout of runs. Its controls SHALL follow
what the manifest declares: every Experiment gets the generic two-dimensional
projection over any two declared dimensions with the others fixed, metric
selection and filters; baseline/difference views appear only when the manifest
declares `arms`; the geometry map and trigger filmstrip appear only when it
declares compatible multi-grid trigger/distance dimensions. An Experiment
without such declarations SHALL NOT be shown those controls. The view SHALL NOT
require a selected run.

#### Scenario: Open the tab without a run

- **WHEN** the user opens the Surface view and no run is selected
- **THEN** the Experiment selector and the projection are shown.

#### Scenario: Ratio experiment

- **WHEN** an Experiment declares ordinary dimensions and no arms or multi-grid
  dimensions
- **THEN** only the generic projection, metric selection and filters are shown.

#### Scenario: Request only what is displayed

- **WHEN** the user fixes an initial stop
- **THEN** the results request is filtered by the dimension id (`sl`) to that value and the full table is
  not requested.

### Requirement: Explicit units

Every dimension control and readout SHALL show the dimension's unit. For a
dimension with several grids, the readout SHALL show the value in the active
grid's unit and its conversion to the other unit at the selected initial stop
(`ATR = R × SL`). Tooltips SHALL show both units.

#### Scenario: R grid readout

- **WHEN** the R grid is active with SL 5 ATR and trigger 7R
- **THEN** the readout shows `7R` and `= 35 ATR at SL 5`.

### Requirement: Metric filters

The view SHALL support any number of conditions `metric ≥ value` or
`metric ≤ value` over declared metrics and over their differences to the
baseline arm. All conditions SHALL apply together (AND). Rows that fail any
condition SHALL be shown greyed out; a counter SHALL show passing rows; the
geometry map SHALL offer the share of rows passing the filters.

#### Scenario: Two conditions

- **WHEN** the user sets `PF ≥ 1.3` and `short net ≥ 0`
- **THEN** only rows meeting both keep their colour and the counter shows their
  number out of all rows.

### Requirement: Single selected-run identity

`selectedRunId` SHALL remain the only selected-run identity of the workbench.
Clicking a row with a `run_id` SHALL call the existing run selection with that
`run_id` and nothing else; clicking the already selected run SHALL change
nothing. A row SHALL be shown selected exactly when its `run_id` equals
`selectedRunId`; the Surface view SHALL NOT keep a selected-run or selected-row
state. Clicking a row without a `run_id` SHALL NOT change `selectedRunId` and
SHALL state that no detailed Engine run is available for it. Row provenance
SHALL be shown from the declared provenance, never inferred from `run_id`.

#### Scenario: Row with a run

- **WHEN** the user clicks a row with a `run_id`
- **THEN** `selectedRunId` becomes that `run_id` and Chart and Reports load it
  through their existing path.

#### Scenario: Row without a run

- **WHEN** the user clicks a row without a `run_id`
- **THEN** `selectedRunId` is unchanged and an inline note says no detailed
  Engine run is available.

#### Scenario: Highlight follows the selected run

- **WHEN** `selectedRunId` equals the `run_id` of a visible row
- **THEN** that row is highlighted, however the run was selected.

### Requirement: Surface state survives tab switches

The selected Experiment and the view's controls SHALL be held outside the
Surface view and outside the run-selection context and SHALL persist across tab
switches.

#### Scenario: Surface → Chart → Surface

- **WHEN** the user selects an Experiment and controls, opens Chart, and returns
- **THEN** the same Experiment, controls and `selectedRunId` are shown.

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
state ("Select a row in the Surface view") instead of the loading view while no
run is selected. A `run` query parameter in the page URL SHALL set the initial
`selectedRunId`, and the URL SHALL be updated when the selected run changes. The
Composer SHALL select the run returned by a backtest directly, without re-reading
the run list.

#### Scenario: Fresh start

- **WHEN** the workbench loads without a `run` parameter
- **THEN** no run is selected, no run list is requested, and Chart and Reports
  show the idle state.

#### Scenario: Reload keeps the run

- **WHEN** a run was selected and the page is reloaded
- **THEN** the same `run_id` is selected from the URL and loaded.

#### Scenario: Failed load stays selected

- **WHEN** the selected run fails to load and the user presses Retry
- **THEN** the same `run_id` is requested again and stays selected.

### Requirement: Run-specific transient state

When `selectedRunId` changes, inspection state of the previous run (selected
trade, selected bar, trade focus, viewport focus, trace and bar diagnostics)
SHALL NOT carry over; the new run SHALL get the existing default trade focus.
The Surface view SHALL NOT write any of this state.

#### Scenario: Switch from run A to run B

- **WHEN** the user focused a trade and bar of run A and then clicks a row of
  run B
- **THEN** after run B loads, trade and bar focus are run B's defaults, as after
  a selection through any existing path.

### Requirement: Chart isolation

The Surface view SHALL NOT import chart or chart-runtime modules, SHALL NOT read
or mutate chart runtime state or caches, and SHALL NOT enable chart heavy I/O.
Switching between the Surface tab and other tabs SHALL NOT unmount the Chart
pane. Selecting a run from the Surface view before the Chart tab was ever
opened SHALL load only the run report requests.

#### Scenario: Selection before Chart was opened

- **WHEN** the Chart tab has never been opened and the user selects a row with a
  `run_id`
- **THEN** only run detail, trades, metrics and managed-policy-events requests
  are made, and no market, signal-trace or chart-events request.

#### Scenario: Tab switch without run change

- **WHEN** the user switches Chart → Surface → Chart without changing the run
- **THEN** the Chart pane is not remounted and makes no additional market
  requests.
