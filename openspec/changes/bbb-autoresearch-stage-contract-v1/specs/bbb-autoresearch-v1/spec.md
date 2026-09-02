## ADDED Requirements

### Requirement: Versioned A-to-B stage-contract session

An A→B research session SHALL use `bbb_autoresearch_state.v3` and SHALL durably contain an
immutable resolved starting-strategy snapshot, an immutable typed stage contract, the active stage,
configured measurement geometries, stage dispositions, and canonical evidence references. Exact
v1 and v2 sessions SHALL retain their existing contracts and behavior without silent migration.

#### Scenario: New controlled A-to-B session

- **WHEN** an operator initializes the controlled EMA-anchor A→B template
- **THEN** the resulting state is v3 and contains the complete immutable starting strategy and
  stage contract needed to validate every later plan without relying on chat history or the mutable
  repository fixture.

#### Scenario: Existing session remains exact

- **WHEN** a v1 or v2 session is loaded after v3 support is introduced
- **THEN** the supervisor validates and runs it under its original enclosing contract rather than
  adding stage-contract fields or migrating it implicitly.

### Requirement: Canonical starting strategy is validated and frozen

The controlled session template SHALL reference a complete operator-approved canonical
starting-strategy fixture.
Initialization SHALL resolve the fixture, validate it through the existing canonical
Research→Strategy Engine configuration-validation path, copy the validated strategy into session
state, and bind its content hash. The snapshot SHALL include strategy/ticker/timeframe identity,
the EMA100/EMA200/EMA500 stack, trigger, direction, setups, blockers, contexts, exits, risk,
component parameters, and every required component `instance_id`. A later fixture edit SHALL NOT
change an initialized session.
Initialization SHALL resolve the declared symmetric-geometry TP and SL component/instance targets
unambiguously against the validated starting strategy before creating the session directory.

#### Scenario: Valid starting fixture

- **WHEN** the checked-in fixture is a complete valid EMA-anchor strategy
- **THEN** initialization freezes the resolved validated document and its hash before any planning
  worker can create an experiment.

#### Scenario: Invalid or unavailable validation

- **WHEN** the fixture is incomplete, fails canonical configuration validation, or its required
  canonical validation dependency is unavailable
- **THEN** initialization fails closed and creates no runnable v3 session.

#### Scenario: Invalid bound exit identity

- **WHEN** a required TP/SL binding is missing, duplicated, ambiguous, or resolves to the wrong
  declared component/instance identity
- **THEN** initialization fails closed before creating any partial session directory.

#### Scenario: Operator fixture is not yet supplied during implementation

- **WHEN** the versioned stage-contract machinery is implemented before an operator-approved
  starting document is available
- **THEN** APPLY may complete, but initialization of the controlled v3 harness session fails closed
  until its template references that complete document.

#### Scenario: Fixture changes after initialization

- **WHEN** the repository fixture changes after a session has frozen its starting strategy
- **THEN** the active session continues to use its immutable snapshot and cannot adopt the new
  fixture implicitly.

### Requirement: Typed semantic mutation dimensions

The v1 A→B stage contract SHALL express mutation authority only with the semantic dimensions
`symmetric_measurement_geometry`, `anchor_stack_width`, and `untouched_anchor_lookback`. It SHALL
NOT expose a generic JSONPath, JSON Pointer, array-index, patch, or arbitrary field-mutation DSL.
The supervisor SHALL resolve each dimension to the applicable validated component instance in the
frozen strategy and SHALL treat every field not owned by an allowed dimension as immutable.
Every non-mutable parameter of a width/lookback component prototype SHALL have an explicit
operator-supplied immutable value. The live component catalog SHALL validate component and
parameter availability, names, types, and constraints, but its default values SHALL NOT supply
research semantics implicitly.
Strategy identity, ticker, timeframe, EMA periods, component IDs, all component `instance_id`
values, trigger/direction structure, and unrelated parameters SHALL never be mutable.

#### Scenario: Allowed semantic change

- **WHEN** a candidate differs from its stage reference only in the value represented by an active
  allowed semantic dimension
- **THEN** the supervisor may accept the plan for canonical execution after all other contract
  checks pass.

#### Scenario: Unlisted or identity change

- **WHEN** a candidate changes an unrelated field, an EMA period, ticker/timeframe, component ID,
  `instance_id`, trigger, direction, or another field outside its active semantic dimensions
- **THEN** the supervisor rejects the plan fail-closed before canonical execution.

#### Scenario: Explicit fixed prototype parameters

- **WHEN** initialization resolves a width or lookback prototype
- **THEN** all non-mutable parameter values come from the immutable operator contract and are
  validated against the catalog, and changing any such fixed value is rejected before execution.

### Requirement: Phase A establishes configured symmetric references

`A_BASELINE` SHALL use the naked frozen starting strategy and an operator-configured non-empty set
of uniquely identified symmetric measurement geometries. Each geometry SHALL have equal TP and SL
distance and SHALL be measured as exactly one candidate in its own canonical experiment. The worker
SHALL NOT add a new geometry, use an asymmetric geometry, or change any non-geometry strategy
field. An accepted Phase A reference SHALL durably bind `geometry_id`, exact geometry, canonical
experiment/candidate/run identity, market-data hash, `realised_trade_count`, and `win_rate`. Phase
A SHALL NOT choose or promote a preferred geometry.

#### Scenario: Configured A geometry is measured

- **WHEN** the worker plans the configured geometry `A-3` representing 3/3 on the naked strategy
- **THEN** the sole candidate remains otherwise identical to the frozen starting strategy and the
  accepted reference records canonical trade count and win rate for `A-3`.

#### Scenario: Asymmetric or invented geometry

- **WHEN** a Phase A plan uses unequal TP/SL distances or a geometry ID/value absent from the
  immutable session contract
- **THEN** the supervisor rejects the request before canonical execution.

#### Scenario: Reference line completion

- **WHEN** every configured geometry has one accepted canonical Phase A reference
- **THEN** the worker may close Phase A and request B1 without the supervisor ranking those
  geometries or selecting a winner.

### Requirement: B experiments are matched to one Phase A geometry

Every B1, B2, or B3 batch SHALL reference exactly one completed Phase A `geometry_id`. The
supervisor SHALL require every candidate in that experiment to reproduce the exact symmetric exit
geometry bound to that reference and SHALL reject cross-geometry comparison. One experiment SHALL
NOT combine multiple geometry families.

#### Scenario: Matched comparison

- **WHEN** a B1 experiment references `geometry_id=A-3`
- **THEN** every candidate retains the exact 3/3 geometry recorded by A-3 and may vary only the
  semantic dimensions permitted for B1.

#### Scenario: Geometry mismatch

- **WHEN** a B candidate or comparison claim uses a geometry different from its referenced Phase A
  record, or one batch contains candidates from several geometry families
- **THEN** the supervisor rejects the plan fail-closed before execution.

### Requirement: Independent B1 and B2 mutation boundaries

`B1_WIDTH` SHALL construct every candidate from the naked starting strategy plus one referenced
Phase A geometry and SHALL permit only `anchor_stack_width` to vary. `B2_LOOKBACK` SHALL independently
construct every candidate from that same naked starting strategy plus one referenced Phase A
geometry and SHALL permit only `untouched_anchor_lookback` to vary. A width value discovered or
tested during B1 SHALL NOT leak into B2.

#### Scenario: Width-only B1

- **WHEN** B1 tests an anchor-stack-width response
- **THEN** the supervisor accepts only candidates whose difference from the naked matched-geometry
  reference is the resolved width dimension.

#### Scenario: Naked reset for B2

- **WHEN** the session enters B2 after B1
- **THEN** candidates are rebuilt from the naked matched-geometry reference, width is baseline or
  disabled exactly as in the starting strategy, and only the resolved lookback dimension varies.

#### Scenario: B1 setting leaks into B2

- **WHEN** a B2 candidate retains a width mutation from B1
- **THEN** the supervisor rejects the plan before canonical execution regardless of its expected
  scientific value.

### Requirement: B3 is causally available but optional

`B3_WIDTH_X_LOOKBACK` SHALL be unavailable until the worker has independently closed B1 and B2 as
either `characterized` or `terminally_rejected` through accepted, evidence-referenced iteration
results. Once both dispositions are durable, B3 MAY be selected by the worker when it provides a
scientifically justified discriminating experiment; it SHALL NOT be an automatic or mandatory
transition. B3 candidates SHALL start from the naked matched-geometry reference and may vary only
`anchor_stack_width` and `untouched_anchor_lookback`.

#### Scenario: Premature interaction request

- **WHEN** a worker requests B3 before both independent investigations have durable closing
  dispositions
- **THEN** the supervisor rejects the causal-order violation before execution.

#### Scenario: Optional justified interaction

- **WHEN** B1 and B2 are closed and the worker explains why their interaction has information value
- **THEN** B3 becomes a permitted next stage and the supervisor enforces only its mutation,
  geometry, evidence, and contract boundaries.

#### Scenario: No interaction is justified

- **WHEN** B1 and B2 are closed but the worker concludes that B3 has no justified information value
- **THEN** the session may preserve a terminal `NO_STABLE_EDGE` or other applicable evidence-backed
  conclusion without executing B3.

### Requirement: Stage disposition remains scientific worker output

The worker SHALL decide parameter values, ranges, topology, boundary refinement, sample adequacy,
thinning trade-offs, side scope, whether an independent dimension is sufficiently characterized or
terminally rejected, and whether B3 is justified. The supervisor SHALL validate the disposition's
contract shape and canonical evidence references and persist it mechanically; it SHALL NOT compute
uplift thresholds, select an optimum, infer scientific closure from metrics, rank candidates, or
force B3.
For `characterized` and `terminally_rejected`, the supervisor SHALL additionally verify that every
disposition evidence reference resolves to an available authoritative source: a candidate and
metric in the current canonical result, an exact retained prior-assessment iteration in state, or
the retained iteration analysis artifact. A syntactically valid but nonexistent candidate, metric,
prior iteration, or arbitrary/escaping analysis path SHALL fail closed. This verification SHALL
NOT assess evidence strength or derive the disposition.

#### Scenario: Fabricated closing evidence

- **WHEN** a closing stage disposition cites a nonexistent candidate or metric, a prior iteration
  absent from retained state, or an arbitrary analysis path
- **THEN** the supervisor rejects it without interpreting the scientific conclusion.

#### Scenario: Worker closes a flat B1 response

- **WHEN** the worker reports an evidence-backed `terminally_rejected` B1 disposition after a flat
  or unstable response
- **THEN** the supervisor persists the negative finding and permits the causal transition to B2
  without reinterpreting the response or demanding a profitable width.

#### Scenario: Highest win rate is isolated

- **WHEN** one candidate has the highest win rate but the worker reports thinning or unsupported
  topology
- **THEN** the supervisor performs no automatic selection and enforces only the stage contract and
  existing quality/evidence requirements.

### Requirement: Stage-contract recovery is deterministic

Frozen stage identity, semantic mutation dimensions, starting/reference strategy hash, referenced
geometry ID, and prerequisite dispositions SHALL be bound before supervisor-owned execution and
revalidated on recovery. Existing request/receipt/interpretation recovery semantics SHALL remain
unchanged, and retry or restart SHALL NOT change the stage reference or mutation authority.

#### Scenario: Crash after stage-valid execution

- **WHEN** a v3 batch has a valid frozen request and execution receipt but interpretation is not
  committed
- **THEN** recovery reuses the same execution and stage bindings, retries only interpretation, and
  does not resolve a different strategy reference or geometry.
