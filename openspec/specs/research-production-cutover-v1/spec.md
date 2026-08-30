# research-production-cutover-v1 Specification

## Purpose

Define I7's coordinated single-instance production cutover: the final
`/range` v2 contract, Research's v2 consumer wiring, canonical
persistence, and the fail-closed, jointly-deployed compatibility/
rollback contract between Strategy Engine and Research Service.
## Requirements
### Requirement: I7 scope — single-instance production cutover only

I7 of the `compact-strategy-evaluation-boundary-v1` Master Plan SHALL
switch the real, live single-instance historical execution path
(`RunSingleInstanceBacktest` → `PersistSingleInstanceBacktest`-equivalent
persistence) to the already-proven (I5/I6) `HistoricalExecutionProjection
v2` contract and target persistence shape. I7 is a coordinated,
atomic, cross-repo production behavior change — unlike I5/I6, which
were proof-only and touched no production code, I7 IS the production
cutover those gates exist to authorize.

I7 SHALL NOT:

- start I8's batch lifetime redesign, or change `/range-batch`'s wire
  contract, execution path, or persisted artifact shape in any way;
- change Strategy Runtime or any live-facing contract (`/live-entry`,
  `/open-trade`, `/managed-replay`);
- introduce new business/trading semantics beyond what I0–I6 already
  proved (I7 wires already-proven facts into production, it does not
  compute new ones);
- make Strategy Engine compute fills, fees, PnL, equity, or trades —
  Research remains sole owner of execution/accounting/persistence, as
  it already is today.

#### Scenario: I7 does not touch batch

- **WHEN** I7's cutover is implemented
- **THEN** `/strategy-evaluations/range-batch`'s wire contract,
  `application/experiments/run_batch.py`'s execution path, and its
  persisted artifact shape are all unchanged
- **AND** `MaterializeBacktestOutcome`/`PersistSingleInstanceBacktest`
  (see "Shared batch/single-instance infrastructure" below) continue to
  serve batch exactly as they do today.

### Requirement: Final production `/range` contract

After I7, Strategy Engine's `POST /strategy-evaluations/range` route
SHALL serve `contract_version: "strategy_evaluation_execution.v2"`
(the `HistoricalExecutionProjection` envelope, already normatively
fixed by `strategy_engine`'s `strategy-research-execution-contract-v1`
capability) as its only response shape. `POST /strategy-evaluations/
range/diagnostics` (dense diagnostics) is unaffected — it already
returns a separate contract today and stays that way.

**This cutover SHALL NOT be implemented by changing what
`EvaluateStrategyRange.execute()` returns.** Confirmed via code:
`EvaluateStrategyRangeBatch` calls this exact same `.execute()` method
per candidate inside its own loop, and `/strategy-evaluations/range-
batch`'s route serializes its outcomes with the unchanged sparse `.v1`
serializer. Changing `execute()`'s return shape would silently switch
`/range-batch` to `.v2` too, violating "I7 does not touch batch" above.
The correct shape (normative in `strategy_engine`'s own
`strategy-research-execution-contract-v1`): `/range`'s route handler
SHALL call a NEW, separate application-service method
(`EvaluateStrategyRange.execute_projection()` or equivalent), while
`/range-batch`'s route handler SHALL keep calling the existing,
completely unmodified `EvaluateStrategyRange.execute()` — which
therefore remains reachable via HTTP, through `/range-batch`, not
merely retained as private in-process code. `evaluate()`/
`StrategyRangeResult` (the original dense contract) remain private/
unrouted, unaffected by I7 either way.

`StrategyEvaluator`'s Protocol (`strategy_engine/strategies/ports.py`)
gains one additive method returning `HistoricalExecutionProjection`
(calling the already-shipped, already-proven `_evaluate_frame_native` +
`build_historical_execution_projection`, I1) — the exact production
counterpart of I5.A's proof-only script, now reachable via the real
route (only through the new method, not through `execute()`/
`evaluate_execution()`) instead of only in-process.

#### Scenario: Production /range serves v2 after cutover

- **WHEN** a real request is sent to `POST /strategy-evaluations/range`
  after I7
- **THEN** the response's `contract_version` is exactly
  `"strategy_evaluation_execution.v2"`
- **AND** the response body is a `HistoricalExecutionProjection`
  envelope, not the sparse `.v1` shape.

#### Scenario: /range-batch keeps reaching the sparse .v1 path via HTTP

- **WHEN** a real request is sent to `POST /strategy-evaluations/
  range-batch` after I7
- **THEN** it is still served via `EvaluateStrategyRange.execute()` →
  `evaluate_execution()` → `serialize_strategy_evaluation_execution()`,
  exactly as before I7
- **AND** this HTTP path to the sparse `.v1` shape remains reachable —
  it is not reduced to private/unrouted code by I7.

### Requirement: Research v2 consumer wiring

`StrategyEnginePort` (`ports/strategy_engine.py`) SHALL gain a method
returning `HistoricalExecutionProjectionDTO` (the real production
counterpart of I5.A's proof-only `parse_historical_execution_projection`
call), implemented by `HttpStrategyEngineClient` calling the
now-v2-serving `/strategy-evaluations/range` route. This method SHALL
be additive to the port — `evaluate_range`/`evaluate_range_batch`
(returning the legacy `StrategyEvaluationResult` shape) SHALL NOT be
removed, since `/range-batch` still needs `evaluate_range_batch`'s
existing shape (out of I7 scope, see "I7 does not touch batch").

#### Scenario: Research decodes the real v2 route response unmodified

- **WHEN** `RunSingleInstanceBacktest` calls the new port method against
  the real, cut-over `/range` route
- **THEN** the response decodes through the real, already-shipped
  `parse_historical_execution_projection`/`validate_projection_
  alignment`/`HistoricalExecutionProjectionIndex.build` (I3) with no
  field coercion — this is the same round-trip I5.A already proved
  in-process, now exercised over the real live route for the first
  time.

### Requirement: Shared batch/single-instance infrastructure stays batch-shaped

`MaterializeBacktestOutcome` and `PersistSingleInstanceBacktest`
(`application/backtests/materialize_backtest_outcome.py`/`artifacts.py`)
are used TODAY by both `RunSingleInstanceBacktest` (single-instance) AND
`application/experiments/run_batch.py` (batch, per-candidate). Because
I7 SHALL NOT change batch's execution path or persisted shape, I7 SHALL
NOT modify these two classes in place. Instead:

- `RunSingleInstanceBacktest` SHALL be wired to a NEW, single-instance-
  specific materialization path (consuming `HistoricalExecutionProjectionDTO`/
  `run_projection_execution_loop`/`account_execution_loop` — the exact
  chain I5/I6's proof scripts already exercised in-process) and a NEW,
  single-instance-specific persistence function producing the I6.D-shaped
  bundle.
- `MaterializeBacktestOutcome`/`PersistSingleInstanceBacktest` remain
  exactly as they are today, and become batch-only components after I7
  — still load-bearing (not deletable), just no longer reachable from
  the single-instance path.

This is not code duplication for its own sake — it is the mechanism by
which I7 achieves its "does not touch batch" invariant given these two
classes' current shared-code shape. A future I8 MAY choose to
reconcile or delete the batch-only legacy shape as part of its own
redesign; I7 does not decide that.

#### Scenario: Batch materialization is untouched by the single-instance cutover

- **WHEN** I7's single-instance cutover is implemented
- **THEN** `application/experiments/run_batch.py`'s calls to
  `MaterializeBacktestOutcome.execute`/`PersistSingleInstanceBacktest
  .execute` are unchanged in signature and behavior
- **AND** a batch run's persisted artifacts are byte-for-byte the same
  shape as before I7.

### Requirement: /runs reads only the canonical new shape — no legacy compatibility

`ReadResearchRuns`/`_documents()` (`application/backtests/
read_artifacts.py`) and its production read models (`SingleInstance
BacktestResult` parsing, `RunSummary`/`RunDetail`/`RunTrades`/
`RunMetrics`/`RunCompactSummary` construction) SHALL be cut over IN
PLACE to the canonical I6.D persistence shape as part of I7. There is
exactly one reader, one set of read models, and one `/runs` read path
after I7 — not two.

Normative for I7:

- `ReadResearchRuns` and its models SHALL be modified in place to parse
  and serve only the canonical I6.D `result.json` shape (identity
  subset + references, per "Production persistence cutover to the
  I6-proven shape" below).
- After I7, `/runs` (and every other consumer of `ReadResearchRuns`)
  SHALL read only canonical new-shape runs. Old, pre-cutover persisted
  run shapes are neither supported nor recognized — no code path
  SHALL sniff, detect, or branch on a run's shape.
- **No `contract_version` (or equivalent) field SHALL be added for
  shape discrimination purposes.** There is only one shape for this
  reader to know about.
- **No fallback, no separate legacy reader, no separate legacy store/
  namespace SHALL be introduced.** This is a genuine in-place cutover,
  not a parallel-path migration.
- Backward compatibility with runs persisted before I7 is explicitly
  NOT required — old-shape runs already on disk need not remain
  readable through `/runs` after this cutover.
- Batch execution and persistence (`MaterializeBacktestOutcome`/
  `PersistSingleInstanceBacktest`/`run_batch.py`) SHALL remain
  completely untouched through I7, per "Shared batch/single-instance
  infrastructure stays batch-shaped" — but because `ReadResearchRuns`
  itself is cut over in place, batch-persisted candidate artifacts
  produced between I7 and I8 are NOT guaranteed to be readable through
  the canonical `/runs` path in that window. This is an accepted,
  explicitly out-of-scope consequence of I7/I8's staged sequencing, not
  a defect I7 must paper over — I7 governs single-instance production
  only, and `/runs` read compatibility for batch artifacts is not part
  of its contract.
- I8, when it migrates batch execution/persistence onto the same
  canonical format, SHALL delete the old batch execution/persistence
  code (`MaterializeBacktestOutcome`/`PersistSingleInstanceBacktest`
  and whatever legacy shape they still produce) — at that point batch
  artifacts become canonical too and the accepted I7-to-I8 gap closes.

#### Scenario: /runs serves only canonical-shape runs after I7

- **WHEN** `/runs` (or any `ReadResearchRuns` consumer) is called after
  I7
- **THEN** it parses and returns only runs persisted in the canonical
  I6.D shape
- **AND** no code path attempts to detect or parse an old-shape run.

#### Scenario: No shape discrimination machinery

- **WHEN** I7's persistence cutover is implemented
- **THEN** the canonical `result.json` shape gains no field whose
  purpose is enabling shape discrimination
- **AND** there is no second/legacy reader, store, or namespace
  co-existing with `ReadResearchRuns` for this purpose.

#### Scenario: Batch-produced artifacts are not guaranteed readable between I7 and I8

- **WHEN** a batch candidate is persisted (via the unmodified batch
  path) after I7 but before I8
- **THEN** `/runs` is not required to be able to read it — this is an
  accepted consequence of batch not yet being migrated, not a defect
- **AND** I8's migration of batch onto the canonical format is what
  closes this gap, at which point the old batch execution/persistence
  code is deleted.

### Requirement: Production persistence cutover to the I6-proven shape

After I7, the single-instance persistence path SHALL write the I6.D
target shape `scripts/persist_and_verify_run.py` already proved
round-trip-correct: `strategy_evaluation.json` IS the real
`HistoricalExecutionProjection` (no longer the legacy dense shape);
`result.json` references `strategy_evaluation.json` (and
`trades.json`/`execution_events.json`) by identity — SHALL retain a
lightweight market-identity/provenance subset directly on `result.json`
(`ticker`/`timeframe`/`from_ms`/`to_ms`/`bar_count`/`market_data_hash`/
`instance_id`/`config_hash`) rather than re-embedding the full
projection, so existing summary-building code
(`read_artifacts.py::_summary`) does not need to open a second file for
basic run identity — this is the concrete resolution of "reference by
identity instead of re-embedding": the full dense strategy-fact payload
is not duplicated, a small identity subset is not the same thing as
re-embedding it. `trades.json`/`metrics.json`/`execution_events.json`/
`manifest.json` keep their current informational content exactly (I6.D
already proved this preserves every common-facts field).

This shape is what `ReadResearchRuns` is cut over in place to serve —
see "/runs reads only the canonical new shape — no legacy compatibility"
above. `RunSummary`/`RunDetail`/`RunTrades`/`RunMetrics`/
`RunCompactSummary` (`run_views.py`) SHALL continue to be built from
the same underlying facts they are today (trades/metrics/manifest) —
none of these BFF view types depend on the re-embedded evaluation
today (confirmed: `run_views.py` reads only `trades`/`metrics`/
`manifest`), so they require no shape change, only confirmation they
still build correctly from the new `result.json`.

#### Scenario: New-shape result.json still yields a correct run summary

- **WHEN** a run persisted under the I7 shape is read back through
  `ReadResearchRuns.detail`/`.compact_summary`/`.trades`/`.metrics`
- **THEN** every field those BFF views expose today is present and
  correct, sourced from `result.json`'s own identity subset plus
  `trades.json`/`metrics.json`/`manifest.json` — no BFF consumer
  regresses.

### Requirement: Diagnostics artifact generation must exist before cutover

`research-diagnostics-projection-v1` (amended in I0) already
normatively requires diagnostics to be read from a separately
persisted diagnostic artifact, generated only on explicit request —
never recomputed at read time, never read from the mandatory execution-
evaluation file. Today, NEITHER the diagnostic-artifact generator NOR
that read path exist: `application/diagnostics/projection.py` still
reads `result.strategy_evaluation.component_evidence`/`.raw`/`.entries`/
`.exit_policy` — fields that exist ONLY on the legacy dense
`StrategyEvaluationResult` shape I7 removes from `result.json`. I7
SHALL NOT ship the persistence cutover above without ALSO shipping,
in the same coordinated change:

1. a diagnostic-artifact generator (calls Engine's already-existing
   `evaluate_diagnostics`/`/strategy-evaluations/range/diagnostics` —
   unaffected by this cutover — and persists the result as its own
   artifact, scoped to the run's `run_id`, exactly as `research-
   diagnostics-projection-v1` already specifies); and
2. `application/diagnostics/projection.py` migrated to read from that
   generated artifact instead of `result.strategy_evaluation`.

Without both, `diagnostics/projection.py` would hard-fail against every
run persisted under the new shape — this is not a new invariant I7
introduces, it is the pre-existing I0 target finally being implemented,
surfaced as a hard prerequisite by EXPLORE before this capability was
written (not previously visible as a concrete blocker until the actual
field-level dependency was traced).

#### Scenario: Diagnostics still work for a newly persisted run

- **WHEN** diagnostics are explicitly requested for a run persisted
  under the I7 shape, after its diagnostic artifact has been generated
- **THEN** `diagnostics/projection.py` builds its response from that
  generated artifact
- **AND** it never reads `result.strategy_evaluation` for this purpose
  (that field no longer carries the dense data it used to).

#### Scenario: A run with no diagnostics generated yet behaves as already specified

- **WHEN** diagnostics are requested for an I7-shaped run that has no
  diagnostic artifact yet
- **THEN** the existing `research-diagnostics-projection-v1` behavior
  applies unchanged (a stable "not yet generated" response, no error,
  no fabricated/recomputed data).

### Requirement: Fail-closed compatibility, no silent dual-contract window

Because Engine's cut-over `/range` and Research's cut-over consumer are
mutually incompatible with their pre-cutover counterparts (an old
Research build cannot parse the new Engine response; a new Research
build's legacy-shape parser is never exercised against the new route),
I7 SHALL be deployed as a single coordinated, atomic release across
both repositories — never Engine-cutover-then-wait or Research-cutover-
then-wait. If Engine's route is cut over while Research still runs its
pre-I7 build, `RunSingleInstanceBacktest` SHALL fail closed (the
existing `UpstreamServiceError`/decode-failure path, not a silent
fallback to a different behavior) rather than silently degrade.

`/range-batch` continuing to serve `.v1` throughout I7 is not a "dual
contract" in the sense this requirement guards against: `/range` and
`/range-batch` are two different routes with two different, independent
consumers (`RunSingleInstanceBacktest` vs. `run_batch.py`), and neither
route's contract changes underneath its own already-matched consumer at
any point during or after I7's rollout. The invariant this requirement
guards is narrower and specific: no window SHALL exist where `/range`
serves one contract while its own consumer (`RunSingleInstanceBacktest`)
expects the other.

#### Scenario: A mismatched pre/post-I7 pairing fails closed, not silently

- **WHEN** Research's `HttpStrategyEngineClient` (any build) receives a
  `/range` response whose `contract_version` it does not recognize
- **THEN** decoding fails with an explicit error (`UpstreamServiceError`
  today, or the equivalent fail-closed path after I7) — it does not
  silently coerce, ignore extra/missing fields, or fall back to a
  different parsing strategy.

#### Scenario: /range-batch is not a dual-contract violation

- **WHEN** I7 is deployed and `/range-batch` still serves `.v1`
- **THEN** this is not evidence of an incomplete or unsafe cutover —
  `/range-batch` and `/range` are independent routes with independent,
  already-matched consumers, and I8 (not I7) owns any future change to
  `/range-batch`'s contract.

### Requirement: Regression gate — real Research → real Engine → execution → persistence, end to end

I7 SHALL NOT be considered complete until a real, live, coordinated
deployment of both repositories' I7 builds is exercised end to end
against a real Market Data Service and a real, running Strategy Engine
instance (not the in-process proof-only scripts I5/I6 used) — i.e. the
literal chain: `RunSingleInstanceBacktest` → real HTTP call to the
live, cut-over `POST /strategy-evaluations/range` → real
`HistoricalExecutionProjectionDTO` decode → `run_projection_execution_
loop` → `account_execution_loop` → the new persistence path → a BFF
read back of the persisted run. This is the one thing I5/I6's proof-only
scripts, by design, never exercised (both called Engine's evaluator
directly, in-process, specifically to avoid depending on a live route
that didn't serve `.v2` yet).

This gate does not re-prove execution correctness (I5 already did,
exhaustively, on real full-scale data) — it proves the two live
services' actual HTTP contract, deployment, and wiring are correct,
which is a distinct kind of risk (serialization mismatches, routing
misconfiguration, dependency-injection wiring bugs) I5/I6 could not
have caught by construction.

#### Scenario: Live E2E gate passes before I7 is marked complete

- **WHEN** the coordinated I7 builds are deployed to a real environment
  with a real Market Data Service and a real Strategy Engine instance
- **THEN** a real `RunSingleInstanceBacktest` request succeeds end to
  end, producing a persisted run bundle in the I7 shape
- **AND** that persisted run, read back through the BFF, reports
  trade/accounting facts consistent with I5's already-proven semantics
  for an equivalent scenario
- **AND** only after this passes is I7 marked complete — it is not
  satisfied by re-running I5/I6's in-process proof scripts again.

### Requirement: Rollback is coordinated, not independent per repository

Because of the fail-closed, mutually-incompatible contract pairing
above, rolling back I7 SHALL also be a coordinated, atomic action
across both repositories — rolling back only Engine's route (back to
`.v1`) while Research's build still expects `.v2` breaks
`RunSingleInstanceBacktest` in the fail-closed manner already specified,
not silently; the converse (rolling back Research alone) leaves
Research parsing `.v2` against nothing meaningful, equally fail-closed.
A rollback plan SHALL identify the exact paired commit/deploy
identifiers for both repositories that were live together, and revert
to that exact pair — not to "the previous version" of each repository
independently, which are not guaranteed to have been mutually
compatible at any point before this exact cutover pair.

#### Scenario: Rollback restores a previously-compatible pair, not two independent previous states

- **WHEN** I7 must be rolled back after deployment
- **THEN** both repositories are reverted together to the specific
  commit pair that was mutually compatible immediately before I7's
  cutover (the last pre-I7 state, where Engine served `.v1` and
  Research's consumer expected `.v1`)
- **AND** a rollback that reverts only one repository, or reverts each
  to a different point in its own history, is not an acceptable
  rollback procedure.

