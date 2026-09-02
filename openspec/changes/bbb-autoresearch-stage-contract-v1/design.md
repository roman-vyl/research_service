## Context

See `proposal.md` for motivation. Current quality-aware state v2 binds a phase to metric roles but
stores only a loose `strategy_context`; an execution plan embeds a complete batch request, and the
supervisor validates the canonical request shape without knowing which strategy differences the
scientific stage permits. Supervisor-brokered execution, immutable request/receipt binding,
canonical artifact verification, worker/executor environment separation, and v1/v2 quality
semantics already exist and should be reused.

The checked-in Strategy Specification Reference from Subtask 1 remains navigation only. Raw-spec
semantics and component parameter schemas remain owned by Strategy Engine and its live Composer
Catalog through Research Service. The stage contract must therefore bind semantic dimensions to a
validated concrete starting strategy without becoming a second general-purpose strategy schema.

## Goals / Non-Goals

**Goals:**

- Make an A→B session reproducible from one validated immutable strategy snapshot.
- Reject every candidate mutation outside the active typed semantic dimensions before compute.
- Keep Phase A a configured measurement procedure and B1/B2 independent controls.
- Make B3 causally unavailable until B1/B2 close, but never scientifically mandatory.
- Preserve worker ownership of experimental values, topology, trade-offs, and negative conclusions.
- Preserve exact legacy contracts and all existing brokered-execution/recovery guarantees.

**Non-Goals:**

- A generic mutation/patch/query language or reusable strategy-diff framework.
- A canonical evaluator metric change, successful-trade-count derivation, or metric recomputation.
- Automatic uplift thresholds, stage-success inference, parameter selection, or B3 scheduling.
- Phase C, asymmetric exit research, B4 touch-history research, HTF/RSI/ADX/filter expansion.
- Strategy Engine, MDS, accounting, execution, sizing, backtest, or production evaluator changes.

## Decisions

### 1. Opt-in enclosing contracts, not expansion of v2

Controlled A→B sessions use:

- `bbb_autoresearch_state.v3`;
- `bbb_autoresearch_execution_plan.v2`;
- `bbb_autoresearch_iteration.v3`;
- `bbb_autoresearch_journal.v3`;
- nested `bbb_autoresearch_stage_contract.v1`.

State v3 encloses the existing v2 quality policy/assessment semantics and adds stage-specific
durability. Plan v2 binds the proposed batch to stage/reference identity before request freeze.
Iteration/journal v3 carry stage disposition and evidence references without weakening the v2
research-quality assessment. Existing receipt/control versions can remain unchanged because their
plan/request hashes already transitively bind the new fields.

Alternative: add optional fields to v2. Rejected because exact versioned contracts and old-session
recovery would become ambiguous.

### 2. Validate then snapshot the operator-supplied starting fixture

The controlled session template references one operator-approved fixture plus its expected research programme. Init
loads it as a complete `DeployableStrategyInstance`, resolves the configured semantic bindings
against the current Research-proxied live component catalog, and submits the complete instance
through the existing Research configuration-validation application path. Only after both checks
pass does init create the session directory.

Initialization also resolves the declared TP and SL component/instance identities against the
validated starting strategy. Missing, duplicate, ambiguous, wrongly typed, or mismatched exit
bindings fail before the session directory exists. Width/lookback prototypes carry explicit
operator-supplied immutable values for every non-mutable parameter. The catalog confirms component
availability plus parameter names, types, and constraints; catalog defaults are never used as
implicit research configuration.

State stores a normalized resolved copy and SHA256, not merely the fixture path. Bootstrap records
fixture path/source hash and resolved hash for provenance. No worker participates in initialization.
Validation failure or unavailable canonical dependencies leaves no partially runnable session.

Alternative: read the fixture on every iteration. Rejected because repository changes would mutate
the scientific control of an active session.

### 3. Use typed semantic bindings, not raw mutable paths

The immutable stage contract exposes only three enum values:

```text
symmetric_measurement_geometry
anchor_stack_width
untouched_anchor_lookback
```

During init, each semantic dimension is resolved against the validated fixture/catalog into a
typed binding containing its component role, stable `component_id`, stable `instance_id` where
applicable, and catalog-confirmed parameter name(s). Symmetric geometry binds the validated static
TP and SL instances as one paired dimension. These bindings are frozen in state and are not a
generic caller-authored path language.

Supervisor comparison locates components by stable identity rather than array position, normalizes
the strategy document, projects out only fields owned by the stage's allowed bindings, and requires
the remaining documents to be identical. It separately requires all identity/component identity
fields to match even if a malformed binding attempted to include them.

Alternative: persist JSONPath/JSON Pointer allowlists. Rejected because array positions and spec
layout leak into the research contract and create an unbounded mutation DSL.

### 4. Freeze one programme with four typed stages

`bbb_autoresearch_stage_contract.v1` is deliberately programme-specific:

| Stage | Reference | Allowed dimensions | Availability |
| --- | --- | --- | --- |
| `A_BASELINE` | naked starting strategy | configured `symmetric_measurement_geometry` only | initial |
| `B1_WIDTH` | naked strategy + one completed A geometry | `anchor_stack_width` only | after complete A reference line |
| `B2_LOOKBACK` | naked strategy + one completed A geometry | `untouched_anchor_lookback` only | after B1 closes |
| `B3_WIDTH_X_LOOKBACK` | naked strategy + one completed A geometry | width + lookback | after B1 and B2 close; optional |

The contract is not a general FSM configuration language. These stages and permitted dimensions
are schema enums with fixed relationships. Future B4/C work requires a future reviewed contract.

### 5. Model measurement geometries with one distance value

The operator-configured stage contract stores geometries as unique `geometry_id` plus one canonical
distance value in the unit required by the bound exit components. One value represents the pair;
there is no separate operator TP and SL value that could disagree. Candidate validation confirms
both resolved exit instances equal that value.

Phase A accepts exactly one candidate for one configured geometry per canonical experiment. Its
durable reference record binds geometry, experiment/candidate/run IDs, artifact/receipt evidence,
market-data hash, canonical `realised_trade_count`, and canonical `win_rate`. All configured
geometries must have accepted references before A can close. No infrastructure comparison selects
one geometry.

Alternative: let workers propose arbitrary equal TP/SL values. Rejected because Phase A is a
measurement control, not autonomous exit search.

### 6. Make each B experiment name one reference

Plan v2 contains a required `stage_context` for v3 sessions:

```text
active_stage
starting_strategy_sha256
geometry_id                 # batch actions after/within A as applicable
reference_strategy_sha256
allowed_semantic_dimensions
prerequisite_disposition_refs
```

For B batches, `geometry_id` resolves to exactly one accepted Phase A record. The supervisor builds
the applicable reference from the frozen naked snapshot plus that geometry and verifies every
candidate against it. A batch cannot contain several geometry families. Request and plan hashes
then preserve the binding through execution/recovery.

Alternative: group several matched geometry families in one batch. Deferred because it complicates
candidate/reference identity without adding evidence needed for the first harness proof.

### 7. Keep stage closure as evidence-backed worker judgment

Iteration v3 adds a stage disposition with values:

```text
in_progress
characterized
terminally_rejected
```

and canonical/analysis/prior-assessment evidence references using existing evidence shapes. The
worker decides the disposition. The supervisor verifies that references are valid, the stage
matches the frozen plan, and mechanical prerequisites hold. It does not derive closure from win
rate, trade count, topology, or quality assessment.

For a closing disposition, validity means more than validating the `EvidenceRef` shape. A
`canonical_metric` reference must resolve to a candidate and metric in the authoritative canonical
result for the iteration; a `prior_assessment` reference must identify a retained assessment
iteration in state; and an `analysis_artifact` reference must resolve to the retained analysis
artifact for that iteration without escaping its namespace. The supervisor performs only these
referential-integrity checks and does not evaluate the scientific strength of the evidence.

`A_BASELINE` can close only after every configured reference mechanically exists. B1/B2 may close
as `characterized` or `terminally_rejected`. B2 becomes available after B1 closes. B3 becomes
available only after both B1 and B2 close, but the worker may instead write an evidence-backed
terminal conclusion. `terminally_rejected` is a stage disposition, not an infrastructure failure or
automatic whole-session stop.

Alternative: automatically advance after a numeric uplift or a fixed iteration count. Rejected
because it would turn the supervisor into a research algorithm.

### 8. Reuse brokered execution and recovery

Stage validation occurs after plan contract validation but before `_freeze_plan` and before any
execution intent. Once frozen, the plan/request hashes bind the stage context, reference hashes,
and candidate specs. Existing execution receipt, canonical artifact verification, fresh
interpretation, output guards, journal/state atomicity, and ambiguous-execution fail-closed recovery
remain authoritative.

On restart, v3 validation reconstructs the same reference from the state snapshot and checks all
frozen hashes. It never rereads the repository starting fixture or current stage defaults. A valid
receipt resumes interpretation without a duplicate batch.

### 9. Map A/B stages onto existing quality roles

The v3 template binds:

- `A_BASELINE` → `descriptive_baseline`;
- `B1_WIDTH` and `B2_LOOKBACK` → `structural_entry`;
- `B3_WIDTH_X_LOOKBACK` → `structural_interaction`.

Phase A requires the existing canonical trade count and win rate as its compact reference facts.
Other economics remain descriptive. Each B assessment compares uplift/sample/topology/side and
concentration evidence against the exact referenced geometry. No new threshold, score, winner,
successful-trade-count field, or later promotion semantic is introduced.

## Risks / Trade-offs

- [The fixture becomes stale against the live Engine catalog] → Init re-resolves bindings and runs
  canonical config validation; stale fixtures fail before session creation.
- [Semantic resolver code can drift from component schemas] → Bind by component/instance identity,
  confirm parameter names and explicit operator-owned immutable values against live `params_schema`,
  freeze resolved bindings, and cover missing, duplicate, reordered, or ambiguous instances with
  fail-closed tests. Never infer a research value from a catalog default.
- [A worker declares a stage characterized too early] → Preserve that decision and its evidence as
  worker-owned scientific judgment; do not compensate with hidden numeric supervisor thresholds.
- [State v3 increases durable contract surface] → Keep the nested stage contract narrow, use exact
  schemas/manual validators, and leave v1/v2 paths unchanged.
- [Multiple Phase A experiments use different market universes] → Persist canonical market-data and
  window identities per reference; comparisons remain valid only when existing comparability and
  shared-universe requirements are satisfied.
- [One geometry per experiment increases iteration count] → Accept the operational cost for simpler
  provenance and mutation enforcement in v1.

## Migration Plan

1. Land schemas, validators, fixture, typed binding resolver, and deterministic tests without
   changing v1/v2 session behavior.
2. Add v3 initialization and fail before directory creation when catalog/config validation fails.
3. Add plan/iteration/journal v3-aware stage validation and durable state advancement.
4. Update the controlled template, worker guidance, EMA methodology wording, README/status output,
   and test fixtures.
5. Run contract, brokered-flow, recovery, full verification, and strict OpenSpec validation.
6. Start a brand-new HOST smoke session; existing sessions are not migrated or reused.

Rollback removes v3 session creation while leaving already-created v3 evidence readable through
the versioned schemas/status tooling. It does not rewrite v3 sessions into v2.

## Open Questions

- The exact ticker/timeframe, component IDs, instance IDs, parameter names, and distance units must
  be taken from the operator-approved current canonical strategy and live catalog before the
  controlled harness session is initialized. Their absence does not block implementation of the
  contract machinery; it blocks that session's initialization. They are fixture data, not new
  Stage Contract semantics.
- The initial configured geometry IDs/distances belong to the session template. The agreed smoke
  line may use A-2/A-3/A-4, but their exact canonical parameter encoding must follow the live exit
  component schema rather than be guessed in OpenSpec.
