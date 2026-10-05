# Research Managed Policy Consumption v1 Specification

## Purpose

Define how Research Service consumes Strategy Engine's managed-replay
policy artifacts into execution candidates.
## Requirements
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

### Requirement: Effective timing

A managed decision created at the end of bar N MUST NOT be executable on
bar N and MUST become effective only at `effective_from_time_ms`.

#### Scenario: Decision effective on a later bar

- **WHEN** a managed decision's `effective_from_time_ms` is the open time of
  bar N+1
- **THEN** that decision is not used for arbitration on bar N.

### Requirement: Managed stop execution

A managed stop MUST fill at exactly its current level whenever the bar
reached it (`low ≤ level` for long, `high ≥ level` for short), under the
same continuous-market model as the initial stop. A bar that opens
beyond the managed stop MUST NOT fill at the open.

#### Scenario: Managed stop gapped through at open

- **WHEN** the bar open price is already beyond the current managed stop
- **THEN** the managed-stop candidate fills at the stop level, not the
  open.

#### Scenario: Managed stop intrabar touch

- **WHEN** the bar open has not crossed the managed stop but the bar's
  range touches it
- **THEN** the managed-stop candidate fills at the stop level.

### Requirement: Runtime exits

Runtime exit rules active for the inherited bar MUST become close-price
candidates with the legacy candidate class derived from `exit_kind`.

#### Scenario: Runtime exit rule active

- **WHEN** a runtime exit rule is active for the bar under the inherited
  managed state
- **THEN** a close-price candidate is created whose candidate class is
  derived from that rule's `exit_kind`.

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

### Requirement: Projection contract decoding

Research Service MUST decode the Strategy Engine
`HistoricalManagedProjection` wire contract of baseline `07ff911`. A
`phase_transition` rule MUST carry exactly one of: `condition_id`;
(`distance_id`, `trade_metric`); a non-empty `paths` list. Each path
carries `path_id`, an optional `condition_id`, `thresholds`
(`distance_id`, `trade_metric`), an optional `entry_changes` list
(`series_id`, `op`, `value`), and an optional `at_least` (`k`,
`terms`, where each term has exactly one of `condition_id`,
(`distance_id`, `trade_metric`) or `entry_change`). Unknown fields, a
violated XOR, or a `condition_id`/`distance_id`/`series_id` reference
missing from `conditions` or `distances` MUST fail decoding.

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

#### Scenario: Path without entry changes unchanged

- **WHEN** a path carries no `entry_changes` key and no term carries an
  `entry_change`
- **THEN** Research decodes and resolves it exactly as before this
  change.

### Requirement: Generic path resolution

Research Service MUST resolve a `paths` rule generically: a path is
true on a bar if and only if its `condition_id` (if any) is true for
the trade side, every threshold holds (`trade_metric >= distance`, with
a null distance false), every entry change holds (requirement
"Entry-anchored change terms"), and its `at_least` (if any) has at
least `k` true terms. The rule MUST fire on the first true path in
order, and the path's `path_id` MUST be attributed. Research MUST NOT
branch on a component name, component ID, or strategy parameter.

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

### Requirement: Trade metric `mfe_r`

Research SHALL support `trade_metric: "mfe_r"` in the managed projection,
for atomic phase rules, composite thresholds and `at_least` terms. The
metric SHALL be

`|mfe_price - reference_entry_price| / initial_risk`

compared with `>=` against the projection's distance series, where
`initial_risk = |reference_entry_price - initial stop level|` is taken
from the position's initial protection at entry.

- `initial_risk` SHALL be frozen at entry and SHALL be the same value on
  every bar of the trade, in the eager timeline builder and in the
  incremental advance (it SHALL be carried through every state
  transition, not recomputed from a moved stop).
- A position with no initial stop, or with a non-positive initial risk,
  SHALL never meet an `mfe_r` threshold.
- Dispatch SHALL remain on `trade_metric`; Research SHALL NOT read a
  component id.

#### Scenario: Threshold in multiples of initial risk

- **GIVEN** a long position entered at 100 with initial stop 98 and an
  `mfe_r` threshold of 3
- **WHEN** the best price reaches 106
- **THEN** the phase rule SHALL fire on that bar
- **AND** the short mirror (entry 100, stop 102, best 94) SHALL fire on
  the same bar index.

#### Scenario: Initial risk survives state advance

- **WHEN** the incremental advance steps a trade through bars
- **THEN** its phases SHALL equal the eager timeline's phases bar for
  bar.

#### Scenario: No initial stop

- **WHEN** the position has no initial stop
- **THEN** an `mfe_r` rule SHALL never fire.

### Requirement: Entry-anchored change terms

An entry change `{series_id, op, value}` SHALL be evaluated for a
position whose entry fill is on bar `e` as follows: on bar `i`, it holds
iff `distances[series_id][i]` and `distances[series_id][e]` are both
non-null and `distances[series_id][i] − distances[series_id][e] <op>
value`.

- `op` SHALL be one of `>=`, `>`, `<=`, `<`; any other value, or a
  non-finite `value`, SHALL fail decoding.
- The anchor `distances[series_id][e]` SHALL be the same on every bar of
  the trade.
- The eager timeline builder and the incremental advance SHALL evaluate
  it identically.
- An entry-change term in `at_least` SHALL count as one term.
- Dispatch SHALL remain on the wire shape; Research SHALL NOT read a
  component id or a feature name.

#### Scenario: Rise from the entry value

- **GIVEN** a position entered on bar 10 and a series with value 21 on
  bar 10 and 26 on bar 13
- **WHEN** a path requires an entry change with `op` `>=` and `value` 5
- **THEN** the path SHALL be true on bar 13 and false on bars 10 to 12
  where the series is below 26.

#### Scenario: Entry bar

- **WHEN** `op` is `>=`, `value` is 0 and the series is non-null on the
  entry bar
- **THEN** the term SHALL hold on the entry bar.

#### Scenario: Null anchor

- **WHEN** the series is null on the entry bar
- **THEN** the term SHALL never hold for that position.

#### Scenario: Entry change inside N-of-M

- **WHEN** an `at_least` with `k = 2` has an entry-change term, an
  `mfe_pct` term and a market term, and only the entry change and the
  market term hold
- **THEN** the path SHALL be true.

#### Scenario: Incremental advance

- **WHEN** the incremental advance steps a position through bars of a
  projection with entry changes
- **THEN** its phases and attributed paths SHALL equal the eager
  timeline's bar for bar.

