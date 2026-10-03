## ADDED Requirements

### Requirement: Surface tab

The Research Workbench SHALL provide a "Surface" tab that does not require a
selected run. It SHALL let the user pick a surface and show a width × lookback
heatmap for the selected values of the remaining axes, an arm selector
(treatment, comparison, difference), a comparison-arm selector, a metric
selector, a filmstrip over the trigger axis, and a T × D geometry map of
aggregates.

#### Scenario: Open the tab without a run

- **WHEN** the user opens the Surface tab and no run is selected
- **THEN** the surface picker and heatmap are shown.

### Requirement: Explicit units

Every axis control and readout SHALL show the unit of the value. For grids in
ATR or R, the readout SHALL also show the value converted to the other unit at
the selected initial stop (`ATR = R × SL`). Tooltips SHALL show trigger and
distance in both units.

#### Scenario: R grid readout

- **WHEN** the R grid is selected with SL 5 ATR and trigger 7R
- **THEN** the trigger readout shows `7R` and `= 35 ATR at SL 5`.

### Requirement: Metric filters

The tab SHALL support any number of conditions of the form
`metric ≥ value` or `metric ≤ value` over the cell metrics and over the
differences to the comparison arm. All conditions SHALL apply together (AND).
Cells that fail any condition SHALL be shown greyed out in the heatmap and the
filmstrip, a counter SHALL show passing cells, and the geometry map SHALL offer
the share of cells passing the filters as an aggregate.

#### Scenario: Two conditions

- **WHEN** the user sets `PF ≥ 1.3` and `short net ≥ 0`
- **THEN** only cells meeting both keep their colour and the counter shows
  their number out of all cells.

### Requirement: Cell to run navigation

Clicking a cell that has a linked run SHALL select that run by `run_id`,
loading it with its `run_manifest_sha256` qualifier, and SHALL switch to the
Chart tab. Clicking a `replay` cell SHALL NOT change the selected run and SHALL
show that the result is a replay without an Engine run, with the cell's
coordinates and metrics. Every cell SHALL carry a visible provenance mark.

#### Scenario: Engine cell

- **WHEN** the user clicks a cell with `provenance` `engine`
- **THEN** the workbench selects the linked run and shows it in the Chart tab.

#### Scenario: Replay cell

- **WHEN** the user clicks a cell with `provenance` `replay`
- **THEN** the selected run stays unchanged and an inline note states that no
  Engine run exists for this cell.
