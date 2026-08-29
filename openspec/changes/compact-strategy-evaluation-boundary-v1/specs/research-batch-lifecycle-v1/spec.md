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

**Corrective note**: an earlier revision of this requirement proposed
resolving this by having Research make N independent per-candidate
`/range` calls instead of one `/range-batch` call. That proposal was
blocked: Engine's `/range` route has no preloaded-`MarketFrame`
transport (confirmed via `EvaluateIndicatorRange._prepare()` —
`request.market_frame is None` on that path, so it always calls
`self._market_data.load_range(...)` itself). N independent `/range`
calls would therefore cause N separate Engine-side MDS reads (plus
Research's own one), not one shared acquisition — violating the
Master Plan's own shared-L0 invariant this requirement exists to
satisfy. See "Streamed shared-once acquisition" below for the
corrected design.

#### Scenario: Batch works against the real, live Engine after I8

- **WHEN** a real batch request runs against a live, current Strategy
  Engine instance after I8
- **THEN** every candidate's evaluation is obtained and parsed
  successfully (no `UpstreamServiceError` from a contract-version/shape
  mismatch), confirmed against the real running service, not only a
  test double.

### Requirement: Streamed shared-once acquisition

**L0** in this requirement means the one shared historical
`MarketFrame`/OHLC dataset every candidate in a batch evaluates
against — MDS is read exactly once per batch, and every candidate's
indicator/strategy computation runs against that same frame:

```
MDS
 ↓ once
L0 MarketFrame
 ├─ candidate A → indicators → strategy → projection
 ├─ candidate B → indicators → strategy → projection
 ├─ candidate C → indicators → strategy → projection
 └─ ...
```

`EvaluateStrategyRangeBatch.execute()` (`strategy_engine`) already
implements exactly this shape today, confirmed by reading it: it calls
`self._market_data.load_range(...)` exactly once, then loops
`request.variants` sequentially, passing that same `market_frame` into
each `StrategyRangeRequest` (`IndicatorRangeRequest._prepare()` reuses
a supplied `market_frame` instead of re-fetching — the transport this
requirement needs already exists). Its two real problems are: (1) the
loop calls the evaluator's old `.execute()` (`.v1`, sparse
`decision_events`) instead of the `.v2` projection path; (2) it
accumulates all N outcomes into one in-memory list
(`outcomes: list[BatchVariantOutcome]`) and returns them as a single
JSON response body — an N-evaluation aggregate held resident in Engine
(then again in Research after `_post_json` deserializes the whole
body), which is exactly what "no N-evaluation aggregate retained"
forbids.

I8 SHALL therefore cut `/strategy-evaluations/range-batch` over to a
new streamed `.v2` response, not the old buffered `.v1` aggregate:

- Engine SHALL acquire the shared `MarketFrame` exactly once per batch
  request (unchanged from today's `EvaluateStrategyRangeBatch`
  acquisition step).
- Engine SHALL evaluate each variant sequentially against that one
  frame, using the same native computation `evaluate_execution_
  projection` uses, and SHALL emit each variant's outcome (a
  `HistoricalExecutionProjection` `.v2` envelope, or a per-variant
  error object) as it is produced — streamed (e.g. newline-delimited
  JSON, one JSON object per line, HTTP chunked transfer), not
  accumulated into an array before the response is sent. Engine SHALL
  NOT hold more than one variant's projection/native-frame state
  resident at a time; each is serialized, written, and released before
  the next variant is evaluated.
- Research SHALL consume the response as a stream: for each line,
  decode it via `parse_historical_execution_projection` (or the
  per-variant error path), then immediately materialize → persist →
  release that one candidate (see "Batch execution/persistence migrate
  to the canonical single-instance path" below) before reading the
  next line. Research SHALL NOT buffer the full response body or the
  full decoded variant list before processing begins.
- A terminal failure of the shared acquisition step (before any
  variant is evaluated) SHALL fail the whole batch, exactly as today
  (`research-batch-experiments-v1`: "whole-experiment failures...
  propagate... no candidate loop starts, nothing is persisted"). A
  failure evaluating one variant (after acquisition succeeded) SHALL
  isolate only that variant — reported inline in the stream as that
  variant's error object — and SHALL NOT stop the stream or fail
  later variants.
- This retires `/range-batch`'s old sparse `.v1` aggregate response
  entirely — Research's batch consumer SHALL NOT depend on it in any
  form, closing the wire-incompatibility from "the real wire contract
  is broken today" above by construction, not by avoidance.

#### Scenario: One market fetch, N sequential in-process evaluations, no N-aggregate

- **WHEN** a batch of N candidates runs after I8
- **THEN** Strategy Engine calls its market-data port exactly once for
  the whole request
- **AND** it evaluates all N variants against that one `MarketFrame`,
  sequentially, within the same request/response lifecycle — not one
  Engine call per candidate
- **AND** at no point does Engine's process hold more than one
  variant's projection resident, and at no point does Research hold
  more than one variant's decoded projection resident before that
  candidate is materialized, persisted, and released.

#### Scenario: A single candidate's evaluation failure isolates only that candidate

- **WHEN** one variant's evaluation fails mid-stream (Engine-side
  strategy error, or a decode/materialize/persist failure on the
  Research side after a valid projection was received)
- **THEN** that candidate's row is reported `status: failed`
- **AND** the stream continues — every other candidate still evaluates,
  materializes, and persists, unaffected. Today's two separate
  isolation levels (a per-variant Engine error inside the old buffered
  response, vs. a per-candidate materialize/persist failure) collapse
  into one per-candidate isolation boundary in the new stream-consuming
  loop; `research-batch-experiments-v1`'s "Failure isolation"
  requirement does not mandate a specific error-level taxonomy, so this
  is an implementation-detail change, not a requirement violation.

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
