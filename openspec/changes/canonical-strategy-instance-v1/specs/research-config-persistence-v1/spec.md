## MODIFIED Requirements

### Requirement: Atomic filesystem persistence

`config/save` SHALL persist a valid draft under
`<configs_root>/<strategy_id>/<experiment_id>.json` using a temporary
file, an `fsync`, and an atomic rename. The selected `experiment_id` for
the `strategy_id` SHALL be persisted the same way in a per-root selection
file.

#### Scenario: Saving a valid draft

- **WHEN** `POST /api/research/config/save` succeeds
- **THEN** the file exists at
  `<configs_root>/<strategy_id>/<experiment_id>.json` and that config
  becomes the strategy's selected experiment.

### Requirement: Unsafe identifier rejection

`strategy_id` SHALL be rejected unless it names a strategy registered in
Strategy Engine's registry. `experiment_id` SHALL be rejected when it is
empty, is `.` or `..`, or contains characters outside `[A-Za-z0-9._-]`.

#### Scenario: Path-traversal experiment_id

- **WHEN** a request supplies `experiment_id=".."` or a value containing a
  path separator
- **THEN** the request is rejected before any filesystem access.

### Requirement: State listing and selection

`GET /configs/state` SHALL list saved configs for a `strategy_id`, report
the currently selected `experiment_id` and its path when one is
selected, and include the selected draft when it can be loaded.
`PUT /configs/selected` SHALL change the selection for a `strategy_id` to
an existing saved config and SHALL then return the same state shape as
`GET /configs/state`.

#### Scenario: Switching selection

- **WHEN** `PUT /api/research/configs/selected` names an existing saved
  config for the `strategy_id`
- **THEN** the response's `selected_experiment_id` and `draft` reflect
  the newly selected config.
