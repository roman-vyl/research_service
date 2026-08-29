## ADDED Requirements

### Requirement: I8 scope — batch lifetime redesign, only after I7

I8 of the `compact-strategy-evaluation-boundary-v1` Master Plan SHALL
redesign how `RunBatchExperiment` acquires and holds Strategy Engine
evaluation state across N candidates so that peak memory is
approximately constant in N, not linear — reusing the single-instance
projection path I7 already proved in production, not inventing new
execution/accounting semantics.

I8 SHALL NOT:

- change single-instance production behavior (`RunSingleInstanceBacktest`,
  `MaterializeBacktestProjectionOutcome`, `PersistSingleInstanceRun`,
  `ReadResearchRuns`) — I8 is additive to batch only, touching the
  existing single-instance path only insofar as batch is switched to
  call it;
- change Runtime or public indicator contracts;
- introduce new business/trading semantics beyond what I0–I7 already
  proved.

#### Scenario: I8 does not touch single-instance production behavior

- **WHEN** I8's batch redesign is implemented
- **THEN** `RunSingleInstanceBacktest`'s own execution/persistence
  behavior, request/response shapes, and artifact shape are unchanged.

### Requirement: /range-batch's real wire contract is broken today — I8 must not perpetuate it

EXPLORE for I8 found, against a real running Strategy Engine instance
(not a test double): `POST /strategy-evaluations/range-batch` returns
`contract_version: "strategy_evaluation_execution.v1"` with
`decision_events` (the sparse shape) for each variant's `result`.
Research's real production consumer
(`HttpStrategyEngineClient.evaluate_range_batch` →
`_parse_evaluation_result`) expects the OLDER dense shape
(`entries`/`exit_policy`/`component_evidence`) and raises
`UpstreamServiceError` attempting to parse the real sparse response —
confirmed by feeding a real captured `/range-batch` response through
the real parser. **`RunBatchExperiment` is not currently functional
against the live Engine stack** — this predates I8, was out of scope
for I7 (`/range-batch` explicitly untouched), and was never previously
confirmed against a real Engine response (existing batch tests only
exercise an in-process `FakeStrategyEngine`).

I8 SHALL fix this incompatibility as part of the lifecycle redesign —
not as a separate, deferred concern — since any lifecycle change to
batch necessarily touches how Research obtains each candidate's
evaluation, which is exactly where the incompatibility lives.

#### Scenario: Batch works against the real, live Engine after I8

- **WHEN** a real batch request runs against a live, current Strategy
  Engine instance after I8
- **THEN** every candidate's evaluation is obtained and parsed
  successfully (no `UpstreamServiceError` from a contract-version/shape
  mismatch), confirmed against the real running service, not only a
  test double.

### Requirement: Shared-once, per-candidate-isolated acquisition

I8 SHALL replace the single `/range-batch` call (which returns all N
candidates' evaluations in one response, held resident together) with
N independent per-candidate `HistoricalExecutionProjection` (`.v2`)
acquisitions via the already-proven, already-production `/range` route
and `StrategyEnginePort.evaluate_range_projection` — the same call
`RunSingleInstanceBacktest` makes today. Only market-data acquisition
(window resolution + the historical `MarketFrame` read) SHALL remain
shared once across the whole batch — Strategy Engine evaluation SHALL
NOT be shared or batched into one call.

This directly satisfies the Master Plan's own I8 framing ("the only
required property is shared market-frame acquisition, not necessarily
one HTTP response containing N evaluations") and eliminates the
`/range-batch` wire-incompatibility by construction: Research no longer
depends on `/range-batch`'s response shape at all for candidate
evaluation. `/strategy-evaluations/range-batch`'s Engine-side route MAY
remain present and unused by Research after I8 — its removal, if any,
is Strategy Engine's own I8 decision, not required by this requirement.

#### Scenario: One market fetch, N independent Engine calls

- **WHEN** a batch of N candidates runs after I8
- **THEN** `ResolveBacktestWindow`/the historical `MarketFrame` read
  each execute exactly once for the whole batch
- **AND** Strategy Engine's `/range` route is called exactly once per
  candidate (N times total), never once for all candidates.

#### Scenario: A single candidate's Engine failure isolates only that candidate

- **WHEN** one candidate's `/range` call fails (network error, upstream
  error, contract mismatch)
- **THEN** that candidate's row is reported `status: failed`
- **AND** every other candidate's acquisition/materialization/
  persistence proceeds unaffected — this is a strictly better failure
  isolation than today's single shared `/range-batch` call, whose
  failure fails the whole batch (`research-batch-experiments-v1`:
  "whole-experiment failures... the Engine `/range-batch` call itself").

Today's two separate isolation levels (Level 2: a per-variant Engine
error inside one shared `/range-batch` response; Level 3: a per-
candidate materialize/persist failure) collapse into a single
per-candidate try/isolate boundary after I8, since each candidate's
Engine acquisition is no longer a separate response field to inspect —
it is the same call that can fail for the same reasons materialize/
persist can. `research-batch-experiments-v1`'s "Failure isolation"
requirement (one candidate failure MUST NOT prevent later candidates
from running) does not require a specific error-level taxonomy, so this
collapse does not violate it — only implementation detail changes.

### Requirement: Per-candidate release — peak memory constant in N

I8 SHALL restructure `RunBatchExperiment` so that at most one
candidate's `HistoricalExecutionProjectionDTO`/execution/accounting
state is resident at a time: acquire → materialize → persist → release,
before the next candidate's acquisition begins. This mirrors old BBB's
per-candidate release discipline (Master Plan context) and is now
achievable because I1–I7 already removed the per-candidate payload
bloat (`HistoricalExecutionProjection`'s sparse shape vs. the original
dense per-bar arrays) that made constant-memory batch unattainable
before.

Batch candidates SHALL continue to execute in strict request order,
one at a time — I8 does not introduce concurrency; the memory fix is
about not holding N candidates' state simultaneously, not about
parallelism.

#### Scenario: N=1/2/4/11 benchmark — peak RSS approximately constant in N

- **WHEN** the same candidate specification is run as a batch of size
  1, 2, 4, and 11
- **THEN** peak process RSS during the run is approximately constant
  across all four sizes (not linear in N) — this is I8's acceptance
  gate, matching the design already stated in the existing
  `compact-strategy-evaluation-boundary-v1` design docs.

#### Scenario: Sequential order preserved

- **WHEN** a batch of N candidates runs after I8
- **THEN** they still execute, and their acquire/materialize/persist/
  release cycle still completes, in exact request order — unchanged
  from `research-batch-experiments-v1`'s existing "Sequential execution
  order" requirement.

### Requirement: Batch execution/persistence migrate to the canonical single-instance path

I8 SHALL switch `RunBatchExperiment`'s per-candidate materialization and
persistence from `MaterializeBacktestOutcome`/`PersistSingleInstanceBacktest`
(legacy dense shape, batch-only since I7) to
`MaterializeBacktestProjectionOutcome`/`PersistSingleInstanceRun` (the
canonical I6.D-shaped components I7 built for single-instance) —
batch's persisted artifacts become canonical-shaped and immediately
readable through `ReadResearchRuns` (I7's in-place cutover), closing the
accepted I7-to-I8 gap `research-production-cutover-v1` documented
("batch-produced artifacts are not guaranteed readable between I7 and
I8").

Once this migration lands, `MaterializeBacktestOutcome`/
`PersistSingleInstanceBacktest` SHALL have no remaining production
caller and SHALL be deleted — per `research-production-cutover-v1`'s
own stated intent ("I8, when it migrates batch execution/persistence
onto the same canonical format, SHALL delete the old batch execution/
persistence code").

`research-batch-experiments-v1`'s "Authoritative per-candidate path"
requirement SHALL be read, after I8, as referring to
`MaterializeBacktestProjectionOutcome`/`PersistSingleInstanceRun` — a
MODIFIED delta updates the requirement text itself; the underlying
invariant (no batch-specific execution/accounting logic, a successful
row summarizes an already-persisted canonical run) is unchanged.

#### Scenario: Batch runs are readable through the canonical BFF path

- **WHEN** a batch candidate completes successfully after I8
- **THEN** its persisted run is in the canonical I6.D shape and is
  readable through `ReadResearchRuns`/`GET /runs/{run_id}` exactly like
  a single-instance run — no separate batch-run reader exists.

#### Scenario: Legacy batch-only components are deleted, not left dormant

- **WHEN** I8's migration is complete and its regression gate passes
- **THEN** `MaterializeBacktestOutcome`/`PersistSingleInstanceBacktest`
  are removed from the codebase, not left as unused dead code — the
  batch-only exemption these two classes had since I7 no longer applies
  once nothing calls them.

### Requirement: Regression gate

I8 SHALL NOT be considered complete until, in addition to the N=1/2/4/11
RSS benchmark:

- `research-batch-experiments-v1`'s existing requirements (candidate
  validity, sequential execution order, failure isolation, batch output
  shape, atomic immutable batch artifacts, `BatchSideSummary` shape) all
  still hold, re-verified against the new acquisition/materialization
  path;
- a real batch request, run against a live, current Strategy Engine
  instance (not a test double), succeeds end to end for N>1 candidates,
  each producing a canonical-shaped, independently readable run;
- Single-instance production behavior (I7) is unaffected — confirmed by
  the existing single-instance test suite and live E2E gate passing
  unmodified.

#### Scenario: I8 complete only when both gates pass

- **WHEN** I8 is proposed as complete
- **THEN** both the N=1/2/4/11 constant-RSS benchmark and a real
  live-Engine batch run (N>1) have passed
- **AND** neither substitutes for the other — a passing benchmark on
  fake/mocked evaluations does not prove the real wire contract works,
  and a single successful live run does not prove memory is constant
  in N.
