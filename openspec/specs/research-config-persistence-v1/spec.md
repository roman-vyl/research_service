# Research Config Persistence v1 Specification

## Purpose

Define the Research-owned Workbench strategy-config save/list/select
surface: serialization, atomic filesystem persistence, listing, selection,
and corrupt-file isolation. Strategy Engine remains the sole semantic
validator for strategy instances (`research-config-validation-v1`).

## Requirements

### Requirement: Preserved routes

The service SHALL expose `POST /api/research/config/serialize`,
`POST /api/research/config/save`, `GET /api/research/configs/state`, and
`PUT /api/research/configs/selected`.

#### Scenario: Route surface

- **WHEN** the OpenAPI schema is inspected
- **THEN** all four routes are present under `/api/research/`.

### Requirement: Validation before persistence

`config/serialize` and `config/save` SHALL run draft validation first and
SHALL return the validation errors, without serializing or persisting, when
the draft is invalid.

#### Scenario: Saving an invalid draft

- **WHEN** `POST /api/research/config/save` is called with a draft that
  fails validation
- **THEN** the response reports the validation errors and no file is
  written.

### Requirement: Deterministic serialization

`config/serialize` SHALL accept `format=json|yaml` and SHALL return a
deterministic textual serialization of a valid draft in the requested
format.

#### Scenario: Serializing a valid draft

- **WHEN** a valid draft is serialized twice with the same format
- **THEN** both serializations are byte-identical.

### Requirement: Atomic filesystem persistence

`config/save` SHALL persist a valid draft under
`<configs_root>/<family>/<experiment_id>.json` using a temporary file, an
`fsync`, and an atomic rename. The selected `experiment_id` for the family
SHALL be persisted the same way in a per-root selection file.

#### Scenario: Saving a valid draft

- **WHEN** `POST /api/research/config/save` succeeds
- **THEN** the file exists at
  `<configs_root>/<family>/<experiment_id>.json` and that config becomes the
  family's selected experiment.

### Requirement: Unsafe identifier rejection

`family` SHALL be rejected unless it is one of the supported families.
`experiment_id` SHALL be rejected when it is empty, is `.` or `..`, or
contains characters outside `[A-Za-z0-9._-]`.

#### Scenario: Path-traversal experiment_id

- **WHEN** a request supplies `experiment_id=".."` or a value containing a
  path separator
- **THEN** the request is rejected before any filesystem access.

### Requirement: State listing and selection

`GET /configs/state` SHALL list saved configs for a family, report the
currently selected `experiment_id` and its path when one is selected, and
include the selected draft when it can be loaded. `PUT /configs/selected`
SHALL change the selection for a family to an existing saved config and
SHALL then return the same state shape as `GET /configs/state`.

#### Scenario: Switching selection

- **WHEN** `PUT /api/research/configs/selected` names an existing saved
  config for the family
- **THEN** the response's `selected_experiment_id` and `draft` reflect the
  newly selected config.

### Requirement: Corrupt-file isolation

A saved file that fails to parse or fails schema validation on load SHALL
still appear in the `config/state` listing, SHALL NOT be returned as the
loaded draft, and SHALL NOT be executed.

#### Scenario: A saved file is corrupted on disk

- **WHEN** `GET /configs/state` lists a family whose selected file is
  unparseable
- **THEN** the entry still appears in the config list, but `draft` is
  absent rather than a partially loaded or guessed value.
