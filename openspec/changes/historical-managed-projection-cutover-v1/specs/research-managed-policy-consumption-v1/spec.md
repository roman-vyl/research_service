## MODIFIED Requirements

### Requirement: Policy ownership

Research Service MUST consume managed policy semantics from Strategy
Engine (ownership boundary: `research-service-boundaries-v1`). For
historical execution, the source MUST be the candidate-wide
`HistoricalManagedProjection` delivered with the `/range` or
`/range-batch` projection. Research executes it locally per trade and
never interprets strategy parameters or component identities. The
per-trade `/managed-replay` artifact MUST be used only as an explicit
oracle (`allow_legacy_managed_replay_fallback=True`), never as the
default historical path.

#### Scenario: Managed candidate source

- **WHEN** a managed exit candidate is built for an open position in a
  historical run
- **THEN** its phase, stop, and take-profile values come from Research's
  local execution of the Strategy Engine `HistoricalManagedProjection`
- **AND** no `/managed-replay` request is issued for that position.

#### Scenario: Oracle opt-in

- **WHEN** a caller constructs the backtest with
  `allow_legacy_managed_replay_fallback=True`
- **THEN** managed values for every position come from a per-trade
  `/managed-replay` artifact, even if the projection carries `managed`.

### Requirement: Attribution

Rule IDs, component IDs, and exit kinds available in the managed policy
source MUST be preserved on Research execution candidates. When the
source is the `HistoricalManagedProjection`, rule IDs MUST be preserved,
component IDs MUST be absent (the contract carries none), and the exit
kind MUST be the canonical kind of the rule's `exit_class`.

#### Scenario: Candidate attribution

- **WHEN** a managed candidate is built from a Strategy Engine event that
  carries a rule ID, component ID, or exit kind
- **THEN** those identifiers are copied onto the Research execution
  candidate unchanged.

#### Scenario: Projection attribution

- **WHEN** a managed candidate is built from the local execution of a
  `HistoricalManagedProjection`
- **THEN** its rule ID equals the projection rule's `rule_id`
- **AND** its component ID is absent.

## ADDED Requirements

### Requirement: Projection contract decoding

Research Service MUST decode the Strategy Engine
`HistoricalManagedProjection` wire contract of baseline `07ff911`. A
`phase_transition` rule MUST carry exactly one of: `condition_id`;
(`distance_id`, `trade_metric`); a non-empty `paths` list. Each path
carries `path_id`, an optional `condition_id`, `thresholds`
(`distance_id`, `trade_metric`), and an optional `at_least` (`k`,
`terms`, where each term has exactly one of `condition_id` or
(`distance_id`, `trade_metric`)). Unknown fields, a violated XOR, or a
`condition_id`/`distance_id` reference missing from `conditions` or
`distances` MUST fail decoding.

#### Scenario: Composite rule decodes

- **WHEN** Strategy Engine sends a `phase_transition` rule with
  `condition_id`, `distance_id` and `trade_metric` null and a `paths`
  list
- **THEN** Research decodes it without error.

#### Scenario: Atomic rule unchanged

- **WHEN** Strategy Engine sends an atomic `phase_transition` rule
  without a `paths` key
- **THEN** Research decodes it exactly as before this change.

#### Scenario: Dangling reference rejected

- **WHEN** a path threshold references a `distance_id` absent from
  `distances`
- **THEN** decoding fails with an upstream contract error.

### Requirement: Generic path resolution

Research Service MUST resolve a `paths` rule generically: a path is
true on a bar if and only if its `condition_id` (if any) is true for
the trade side, every threshold holds (`trade_metric >= distance`, with
a null distance false), and its `at_least` (if any) has at least `k`
true terms. The rule MUST fire on the first true path in order, and
the path's `path_id` MUST be attributed. Research MUST NOT branch on a
component name, component ID, or strategy parameter.

#### Scenario: First path wins

- **WHEN** paths `fast` and `htf` are both true on the same bar
- **THEN** the transition is attributed to `fast`.

#### Scenario: Mixed market and trade

- **WHEN** a path's market condition is true but its MFE threshold is
  not yet met
- **THEN** the path is false on that bar.

#### Scenario: Trade-only N-of-M

- **WHEN** an `at_least` with `k = 2` has three trade terms and exactly
  two hold
- **THEN** the path is true.

### Requirement: Managed execution gating

When the caller did not request managed execution
(`managed_policy_enabled=False`, so no managed provider), Research
Service MUST NOT apply managed policy, whether or not the projection
carries `managed`.

#### Scenario: Managed disabled with a managed projection

- **WHEN** `managed_policy_enabled` is false and the projection carries
  `managed`
- **THEN** positions execute without managed stop, take or runtime-exit
  candidates, exactly as on the legacy path.

### Requirement: Local managed event trace

On the projection path, Research Service MUST emit `ManagedPolicyEvent`s
as observations of the state transitions its generic projection
consumer produced: `phase_changed` when a phase rule fires,
`active_stop_updated` when the active stop actually changes,
`active_take_updated` when the take profile changes, and
`runtime_exit_triggered` when a runtime rule is armed. Events MUST NOT
be a separate implementation of Strategy Engine policy. Event-only
prices (the MFE price on `phase_changed`, the bar close on
`runtime_exit_triggered`) are diagnostic derivations from Research
execution state and the `MarketFrame`, and MUST NOT participate in
policy decisions. Events MUST be persisted in the unchanged
`research_managed_policy_events.v1` artifact. An executed managed
position MUST NOT yield an empty trace when its state changed.

#### Scenario: Phase change recorded

- **WHEN** a position moves from `initial_risk` to `proven` through
  path `htf` on bar N
- **THEN** the trace contains a `phase_changed` event at bar N with
  that rule ID, `from_phase` `initial_risk`, `to_phase` `proven`, and
  `metadata.path_id` `htf`.

#### Scenario: Stop update recorded only on change

- **WHEN** the tightened stop moves by no more than `1e-8`
- **THEN** no `active_stop_updated` event is emitted and the active
  stop rule ID is unchanged.

### Requirement: OLD-vs-NEW parity gate

The repository MUST contain a reproducible, operator-run parity harness.
It runs the same candidate through the legacy oracle and the projection
path, and compares all `TradeRecord` fields except run-scoped labels,
the accounting summary, candidate metrics, and managed events over an
explicit horizon: for a closed position, events with `bar_index` below
its exit bar index; for a position open at the end of the range, events
through the last bar of the evaluation range. The legacy run MUST issue
exactly one `/managed-replay` call per position for which managed
execution was initialized. It reports allowed diagnostic differences
separately. It MUST cover at least one atomic and one composite managed
candidate against the canonical Strategy Engine baseline.

#### Scenario: Open position at end of range

- **WHEN** a position is still open at the last bar of the requested
  range
- **THEN** the harness compares its events through that last bar and
  does not exclude the position.

#### Scenario: Parity pass

- **WHEN** the harness runs a managed candidate
- **THEN** it reports zero non-allowed differences
- **AND** the projection run shows zero `/managed-replay` calls.

### Requirement: Performance gate

The repository MUST contain a reproducible, operator-run performance
harness. It records, per workload, the trade count, Research-side call
counts per Strategy Engine endpoint, Engine CPU, Research CPU, total
CPU and wall time. The hard criteria are: zero `/managed-replay` calls
on the projection path; Engine evaluation calls independent of trade
count; and, where the oracle is run, a median projection-path wall time
below the median oracle wall time over at least 3 paired runs per
workload. On a high-trade-count window the oracle MAY be stopped and
recorded as a wall-time lower bound; the projection-path wall time MUST
then be below that bound. Research CPU alone MUST NOT be an acceptance
criterion.

#### Scenario: Trade count grows

- **WHEN** workloads with low, medium and high trade counts run on the
  projection path
- **THEN** `/managed-replay` calls stay zero
- **AND** Engine evaluation calls per candidate stay constant.
