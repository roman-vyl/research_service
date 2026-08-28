## Why

Companion to `strategy_engine`'s `compact-strategy-evaluation-boundary-v1`
(read that proposal first — it covers the wire-contract proofs this
change consumes). A cross-repo audit found the current persisted-run
artifact conflates four things with no shared consumer into one dense
object: an execution contract, a diagnostic trace, a persistence
artifact, and an HTTP DTO. Concretely, today:

- `strategy_evaluation.json` persists `StrategyEvaluationResult`, whose
  `raw` field is the entire original Engine JSON response body —
  including `features`/`contexts`, which have no typed field of their
  own and exist *only* inside `raw`. Every typed field
  (`entries`/`exit_policy`/`component_evidence`) is therefore also
  duplicated a second time inside `raw`.
- `result.json` (`SingleInstanceBacktestResult`) embeds the same
  `strategy_evaluation` object again — the same dense payload is
  JSON-encoded twice per run.
- `ReadResearchRuns`/`application/backtests/read_artifacts.py` (the sole
  path behind every "open a run" BFF call: detail, summary, trades,
  metrics) deserializes this entire object via Pydantic on every call,
  while only ever touching `strategy_evaluation.market` and
  `accounting.trades` — confirmed by grep, zero other field access.
- `application/diagnostics/projection.py` is the **only** consumer of
  `component_evidence`/`raw.features`/`raw.contexts` repo-wide, reading
  them on demand, per single persisted run, never for N candidates
  simultaneously.
- No current model validator or OpenSpec requirement mandates that these
  fields be co-located with the canonical trades/accounting result.
  `research-run-artifacts-v1`'s "Bundle completeness" requirement
  already treats the Strategy Engine evaluation as its own file,
  separate from `result.json` — the double-embedding inside
  `result.json` is a code choice, not a spec requirement.
  `research-diagnostics-projection-v1`'s "Strategy semantics source"
  requirement only says diagnostic data must come from "the persisted
  Strategy Engine evaluation, not recomputed" — satisfied identically
  whether that evaluation is one dense file or a lean execution-contract
  file plus a separate diagnostic artifact.

This is a deliberate contract change, not a compatibility shim: today's
`research-diagnostics-projection-v1` implicitly forces every one of N
candidates in a research batch to produce and persist a full dense
diagnostic artifact that is almost never opened. That is the wrong
invariant for a batch-discovery workflow, and it is the reason fixing
`/range-batch`'s transport alone would not make research batches cheap —
every candidate would still pay the mandatory dense-diagnostics cost
regardless of how batch orchestration is fixed.

## What Changes

- **Consume Strategy Engine's new sparse decision-event contract**
  (`strategy_engine`'s companion change) instead of dense per-bar
  `entries`/`exit_policy` arrays. `MaterializeBacktestOutcome`/
  `execution/loop.py`/`execution/entry.py`/`static_exits.py`/
  `protection.py` are updated to read point-queries against the sparse
  event list instead of dense array indexing — this is the same
  information at the same call sites, proven lossless per-field in the
  companion change's design doc, not a behavior change.
- **Stop embedding the Strategy Engine evaluation inside `result.json`.**
  `SingleInstanceBacktestResult` references its evaluation by identity
  (e.g. `run_id`/`market_data_hash`) rather than re-nesting the full
  object. The compact execution evaluation (now sparse, per the
  companion change) is persisted once, as its own artifact.
- **Stop retaining the raw Engine response body.** `raw=body` retention
  on the Research HTTP client is removed — there is no `raw` field left
  to populate once the mandatory contract no longer carries diagnostic
  data.
- **Make dense diagnostics a separate, optional, on-demand capability.**
  `component_evidence`/`features`/`contexts`/`potential_entries` are no
  longer produced or persisted as a side effect of every backtest.
  Instead: a run/candidate that needs diagnostics gets them via an
  explicit request, which calls Strategy Engine's new diagnostic-
  evaluation entrypoint (companion change, task 3.2) for the same
  immutable strategy + `market_data_hash`/range, and persists the result
  as its own separate diagnostic artifact. `application/diagnostics/
  projection.py`'s existing "No read-time upstream calls" invariant is
  preserved for *reading* an already-generated diagnostic artifact — the
  generation step is a new, distinct write-path operation, not part of
  the read path that invariant governs.
- **Batch settlement gets a separate, binding follow-on phase — not an
  automatic consequence of the sparse contract alone.**
  `RunBatchExperiment`'s existing shared-L0 + per-candidate
  materialize/persist/release loop (already correctly sequential since
  `batch-candidate-canonical-summary-v1`) is Research-side and already
  fine. What is **not** automatically fixed by Engine's sparse contract:
  `EvaluateStrategyRangeBatch.execute` still accumulates all N
  `BatchVariantOutcome`s before returning, and the `/range-batch` HTTP
  response still covers all N variants in one payload — each variant's
  payload shrinks from ~700MB to ~KB-scale, but N of them are still held
  simultaneously during that one call. A distinct, binding phase (the
  companion change's migration-order step 3) changes the aggregation
  pattern itself — per-candidate evaluate→deliver/settle→release, never
  N held resident simultaneously, shared-L0 retained — and only after
  that phase does batch memory become approximately constant in N. No
  new batch *execution model* is introduced (batch still evaluates
  through the same single-evaluation contract, no separate strategy
  semantics of its own) — but the *aggregation/transport pattern* is a
  real, separate piece of work, not free.

## What Does Not Change

- No change to accounting/execution semantics, trade simulation logic,
  or fee/PnL computation — only the shape of the data Engine hands
  Research to drive that logic, proven lossless per-field in the
  companion change.
- No change to `research-batch-experiments-v1`'s existing requirements
  (candidate validity, sequential order, failure isolation, atomic
  artifacts, the `batch-candidate-canonical-summary-v1` summary fields)
  — batch behavior is unchanged; its cost profile improves in two
  stages: per-candidate payload size shrinks immediately once Engine's
  sparse contract lands, and simultaneous-N memory is bounded only once
  the separate per-candidate evaluate→deliver/settle→release phase
  (companion change) also lands.
- No change to the public `/api/research/backtests`/`/api/research/runs/
  ...` HTTP surface shape for callers that only read trades/metrics/
  summary — those never touched the dense fields (confirmed by audit).
  Callers that read signal-trace/chart-events now go through the new
  on-demand diagnostics-generation flow instead of always finding
  diagnostics already present.
- Migration order matches the companion change: single-instance parity
  must be proven first — identical `TradeRecord` sequence, exact
  accounting, exact exit reasons, semantically-equal provenance (not a
  byte-identical full artifact diff, since `time_ms` is intentionally
  removed) — between old and new contract on a real `full_available`
  N=1 evaluation, before `/range-batch` adopts the same contract, and
  before the per-candidate release phase is attempted.

## Impact

- Affected capabilities: `research-run-artifacts-v1` (MODIFIED —
  bundle no longer double-embeds the evaluation, diagnostics no longer
  mandatory), `research-diagnostics-projection-v1` (MODIFIED — dense
  diagnostics become an explicit, separately-generated artifact rather
  than an always-present part of every run, with an explicit ownership
  and fail-closed provenance-match requirement), `research-unified-
  execution-loop-v1` (MODIFIED — "Aligned inputs" now checks
  `market_data_hash`/`bar_count`/range/`bar_index` range instead of the
  removed `time_ms` array), `research-batch-experiments-v1` (no
  requirement changes — cited for context only, since its existing
  sequential/failure-isolation contract is what the per-candidate
  release phase builds on, without a new batch execution model).
- On-demand diagnostic-evaluation generation: ownership and provenance
  contract fixed by this proposal (design.md) — Research owns
  requesting/persisting diagnostics, calling Strategy Engine's
  diagnostic-evaluation entrypoint (companion change) with the run's own
  stored provenance, and fails closed if the response's provenance
  doesn't match. Route/schema implementation detail is deferred to task
  4.1; ownership is not left open.
- Affected code (implementation deferred, not part of this proposal):
  `adapters/http/strategy_engine_client.py` (`evaluate_range`/
  `evaluate_range_batch`, drop `raw=body`, consume sparse events),
  `domain/contracts.py` (`StrategyEvaluationResult` split into a lean
  execution-contract type + separate diagnostic type),
  `execution/loop.py`, `execution/entry.py`, `execution/static_exits.py`,
  `execution/protection.py` (point-query against sparse events),
  `application/backtests/strategy_contract.py` (`_validate_side_series`
  and friends — validation against sparse events, not dense-length
  assertions), `application/backtests/artifacts.py`
  (`PersistSingleInstanceBacktest` — stop double-encoding, reference not
  re-embed), `application/backtests/read_artifacts.py`
  (`ReadResearchRuns` — read only what each call site needs),
  `application/diagnostics/projection.py` (read from the new separate
  diagnostic artifact), `application/experiments/run_batch.py`
  (unaffected in structure — benefits automatically once the underlying
  evaluation is cheap).
