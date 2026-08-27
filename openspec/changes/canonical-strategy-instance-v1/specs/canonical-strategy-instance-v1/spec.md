## Purpose

Define the single canonical strategy-instance JSON contract shared
unmodified by Composer, Research Service, and Strategy Runtime: the
identity subset that determines `instance_id`, the deployable document
built flat on top of it, and the deterministic identity derivation that
ties every instance across those three systems back to the same
identity.

## ADDED Requirements

### Requirement: Canonical strategy-instance identity subset

A strategy instance's identity SHALL be determined by exactly four
fields: `strategy_id`, `ticker`, `base_timeframe`, and `raw_spec`. No
other field SHALL be treated as part of strategy-instance identity.

#### Scenario: Minimal identity subset

- **WHEN** a strategy instance's identity is expressed
- **THEN** it consists of exactly `strategy_id`, `ticker`,
  `base_timeframe`, and `raw_spec`, and no other field identifies the
  instance.

### Requirement: Deployable strategy-instance document

The canonical deployable strategy-instance document SHALL be a flat JSON
object containing the identity subset plus a sibling `enabled` field:
`{enabled, strategy_id, ticker, base_timeframe, raw_spec}`. `enabled`
SHALL be deployment/activation metadata and SHALL NOT be part of the
identity subset. Toggling `enabled` SHALL NOT create a new strategy
instance and SHALL NOT change `instance_id`.

#### Scenario: Toggling enabled preserves identity

- **WHEN** a deployable document's `enabled` field is changed from
  `false` to `true` (or vice versa) with every other field unchanged
- **THEN** the document's derived `instance_id` is unchanged.

#### Scenario: Composer stores and edits enabled

- **WHEN** Composer produces a deployable strategy-instance document
- **THEN** the document includes an `enabled` field that Composer can
  store and let the user edit.

### Requirement: Research backtest semantics independent of enabled

Research Service validation and backtest execution SHALL NOT depend on a
strategy instance's `enabled` value. A deployable instance with
`enabled=false` SHALL be fully validatable and backtestable using its
identity subset.

#### Scenario: Disabled instance is backtestable

- **WHEN** a backtest is requested for a strategy instance whose
  deployable document has `enabled=false`
- **THEN** Research Service validates and runs the backtest exactly as it
  would for an otherwise-identical instance with `enabled=true`.

### Requirement: Derived instance identity

`instance_id` SHALL NOT be a stored or caller-editable field of the
canonical strategy instance. It SHALL be computed deterministically from
the identity subset (`strategy_id`, `ticker`, `base_timeframe`,
`raw_spec`) using the derivation already implemented by Strategy Runtime
(`derive_strategy_instance_id`), and every caller that needs an
`instance_id` SHALL compute it with that same derivation.

#### Scenario: Identical instances derive identical identity

- **WHEN** two callers (for example Research Service and Strategy Runtime)
  each derive an `instance_id` for the same identity-subset values
- **THEN** both derive the exact same `instance_id`.

#### Scenario: Caller supplies instance_id explicitly

- **WHEN** a caller submits a canonical strategy instance with an explicit
  `instance_id` field
- **THEN** the field is rejected, not silently accepted or ignored.

### Requirement: Operational state excluded

`risk_multiplier` SHALL be Strategy Runtime live-position operational
state. Unlike `enabled`, it SHALL NOT appear in the canonical deployable
document or in any Composer- or Research-facing strategy-instance
representation.

#### Scenario: risk_multiplier absent from canonical instance

- **WHEN** a canonical strategy instance produced by Composer or accepted
  by Research Service is inspected
- **THEN** it has no `risk_multiplier` field.

### Requirement: Legacy identity fields retired

`family`, `variant`, and `strategy_version` SHALL NOT be part of the
canonical strategy-instance contract or of any Research-service-facing or
Composer-produced strategy-instance representation.

#### Scenario: family superseded by strategy_id

- **WHEN** a strategy instance is expressed in canonical form
- **THEN** it carries `strategy_id` and carries no separate `family`
  field.

#### Scenario: variant has no successor

- **WHEN** a strategy instance is expressed in canonical form
- **THEN** it carries no `variant` field, and no other field takes over
  `variant`'s prior role.

#### Scenario: strategy_version dropped

- **WHEN** a strategy instance is expressed in canonical form
- **THEN** it carries no `strategy_version` field.

### Requirement: One identity across live and backtest

A canonical strategy instance accepted by Research Service for a backtest
and a canonical strategy instance deployed to Strategy Runtime for live
evaluation SHALL be the same object type, and identical identity-subset
values SHALL yield the identical `instance_id` in both contexts.

#### Scenario: Same instance, both contexts

- **WHEN** the same `strategy_id`/`ticker`/`base_timeframe`/`raw_spec`
  values are submitted to Research Service for a backtest and deployed to
  Strategy Runtime for live evaluation
- **THEN** both contexts derive the identical `instance_id` for that
  instance.

### Requirement: Deployable document is Runtime-consumable as-is

A Composer-produced deployable strategy-instance document SHALL be
structurally identical to what Strategy Runtime's deployment-file loader
accepts, requiring no field renaming or strategy-semantic transformation
to become a valid Runtime deployment file. Persisting it into Runtime's
actual deployment directory is a separate, out-of-scope deployment-
boundary concern — this requirement covers document compatibility only,
not transport or filesystem integration.

#### Scenario: Composer output is directly loadable

- **WHEN** a Composer-produced deployable strategy-instance document is
  placed into Strategy Runtime's deployment directory unchanged
- **THEN** Runtime's deployment-file loader accepts it as a valid
  deployment, with no field rename or transformation applied first.
