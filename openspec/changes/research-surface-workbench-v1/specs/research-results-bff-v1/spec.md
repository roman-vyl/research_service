## ADDED Requirements

### Requirement: Index-backed run reads

Every read route under `/api/research/runs/{run_id}` (detail, summary, trades,
metrics, signal trace, chart events, managed-policy events, diagnostics) SHALL
locate the run bundle through the run index, so runs stored outside the flat
primary layout are served like any published run. The routes SHALL accept an
optional `manifest_sha256` query parameter that selects one copy exactly.
Manifest verification of the located bundle SHALL apply unchanged.

#### Scenario: Historical run stored in a canonical folder

- **WHEN** `/api/research/runs/{run_id}` names a run whose only copy is
  `<extra_root>/<test>/runs/<batch>/candidates/<run_id>/`
- **THEN** the response is projected from that bundle exactly as for a run in
  the primary root.

#### Scenario: Ambiguous run id

- **WHEN** a read route names a run id whose copies have different manifests
  and no `manifest_sha256` is given
- **THEN** the response is HTTP 409 with error code `run_ambiguous` listing the
  candidate manifest hashes.

#### Scenario: Qualified read

- **WHEN** a read route passes `manifest_sha256` of one existing copy
- **THEN** the response is projected from that copy.

### Requirement: List scope unchanged

`GET /api/research/runs` and `GET /api/research/runs/latest` SHALL keep listing
only runs in the primary artifacts root.

#### Scenario: Indexed canonical runs are not listed

- **WHEN** the runs list is requested
- **THEN** runs that exist only in extra index roots do not appear in it.
