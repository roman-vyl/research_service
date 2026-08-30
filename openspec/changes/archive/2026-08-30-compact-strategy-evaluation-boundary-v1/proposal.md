## Why

Companion to `strategy_engine`'s `compact-strategy-evaluation-boundary-v1`
(read that proposal first — it covers the wire-contract proofs and the
corrected semantic model this change consumes). A cross-repo audit found
the current persisted-run artifact conflates four things with no shared
consumer into one dense object: an execution contract, a diagnostic
trace, a persistence artifact, and an HTTP DTO. Concretely, today:

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

**A second, deeper audit** (old BBB monolith execution core vs. current
Research consumer map vs. the live `strategy_engine ↔ strategy_runtime`
boundary) found a more serious gap than transport: **Research's
execution loop today never implements locked-exit-profile semantics at
all.** It reads only the `always_on` exit set from Engine's evaluation
(`execution/protection.py:19`, `execution/static_exits.py:29` — the
top-level `signal_exit`/`stop_loss_ratio`/`take_profit_ratio`/
`stop_ready` keys only), unconditionally, for every trade — never the
`profile_long`/`profile_short`/`by_profile.*` fields Engine's current
dense contract already exposes. Old BBB's execution core (both its
vectorbt/Numba path and its managed execution loop) locks an exit
profile at entry and holds it for the trade's life, indexing signal-
exit/SL-TP state by that locked profile on every later bar — a real
trading-semantics behavior Research has never reproduced, not a
performance question. Exit attribution (`rule_id`/`component_id`/
`exit_kind`/`layer`) has the same gap: Research's execution loop never
reads Engine's `component_evidence`/`rule_evidence` at all.

This is a deliberate contract change, not a compatibility shim: today's
`research-diagnostics-projection-v1` implicitly forces every one of N
candidates in a research batch to produce and persist a full dense
diagnostic artifact that is almost never opened — the wrong invariant
for a batch-discovery workflow. And today's execution loop's silent
always-on-only behavior is not a baseline to preserve — it is the
specific defect this change and its companion exist to fix, restoring
old-BBB semantics rather than the currently-degraded ones.

## Status: superseding the shipped consumption plan

This change's original consumption plan (point-query against Engine's
dense `entries`/`exit_policy`, unchanged always-on-only execution
semantics) was never implemented on this branch — the companion
`strategy_engine` change shipped its wire contract, but this repo's
tasks 1-6 (below) were not started. This proposal now targets the
corrected `HistoricalExecutionProjection` model from the companion
change instead of the superseded dense/sparse-flat model; no rework of
already-shipped Research code is needed because none was shipped yet.

## Master Plan reference

This proposal is Spec Freeze (**I0**) of a 9-checkpoint cross-repo master
plan. I0 is OpenSpec-only in both repos. I3 (Research consumer
foundation), I4 (Research execution parity — `locked_exit_profile` on
`PositionState`, attribution restoration), I5 (N=1 end-to-end proof,
joint with `strategy_engine`), I6 (persistence/diagnostics split), I7
(coordinated single-instance-only cutover, joint), I8 (batch lifetime,
joint, only after I7) are separate, future authorizations; this
proposal does not authorize any of them.

### Why I5 is a mandatory safety gate, not a formality

I3 and I4 (unit/fixture-level, `test_i3_*`/`test_i4_execution_parity.py`)
already prove the new consumer/execution code is internally correct
against synthetic and hand-built adversarial fixtures. Neither proves it
against real Strategy Engine computation at real historical scale, nor
against data that neither the builder's own author nor the execution
loop's own author constructed by hand. I5 (`research-historical-
execution-parity-v1`, added by this revision) closes that gap: real
Engine computation, a real serialized `v2` envelope, the real Research
parser, and an independent (not self-comparing) reference, on both a
real `full_available` run and the profile-sensitive adversarial
scenario. I6 (persistence shape change) and I7 (production route
cutover) are explicitly gated on I5 passing — reshaping the persisted
artifact or cutting production traffic over to a path whose real-data
correctness has only been unit-tested would be premature. I5 remains a
proof-only checkpoint: it does not itself change Strategy Engine's
`/range` route, Research's production `/range` consumer, `/range-batch`,
persistence, or accounting math (see `research-historical-execution-
parity-v1`'s "Production routes and batch remain out of scope"
requirement) — passing it authorizes I6/I7 to be proposed next, it does
not perform them.

### I5 vs. I6: two different parity gates, not one

I5 proves **computational/execution semantic parity**: on the same
market input, old/legacy semantics and the new Strategy Engine →
`HistoricalExecutionProjection` → Research execution path produce
identical entry facts, locked profile, initial protection, signal-exit
behavior, exit, attribution, accounting, `TradeRecord`, path metrics,
aggregate execution/accounting facts, and provenance. I5 does not
require a persisted Run artifact bundle to exist.

I6 additionally proves a **persisted-artifact regression proof**
(`research-run-artifact-parity-v1`, added by this revision): after I5
passes, the common execution/accounting/trade/path/summary facts I5
already proved correct still agree, trade for trade, between old BBB's
Run output and Research's persisted Run artifact bundle, produced from
the same frozen real-market dataset and an equivalent canonical
strategy configuration. This is deliberately narrower than a full
structural-equality proof of both systems' entire Run artifact models:
new-side-only provenance/storage fields (`run_id`, `manifest.json`,
`instance_id`/`config_hash`/`market_data_hash`) are verified for their
own internal correctness, not diffed against old BBB, which has no
equivalent fields to compare them to. This is I6's own separate
proof-only gate; it is not folded into I5, and I5's own capability is
not expanded to cover persisted artifacts.

## What Changes (target model, I3+ implementation)

- **Consume Strategy Engine's `HistoricalExecutionProjection`**
  (companion change) — executable entry opportunities (with
  `locked_exit_profile` and attributed initial stop/take), per-side
  per-profile signal-exit event streams (with attribution) — instead of
  dense `entries`/`exit_policy` arrays or the flat sparse-event draft
  the companion change's first shipped contract used. `Materialize
  BacktestOutcome`/`execution/loop.py`/`execution/entry.py`/
  `static_exits.py`/`protection.py` consume the new projection shape.
- **Add `locked_exit_profile` to `PositionState`.** Captured once, at
  fill time, from the matching `entry_opportunity`. Held fixed for the
  position's entire life. Every subsequent open bar, signal-exit/SL-TP
  candidate lookup is keyed by `position.locked_exit_profile`, never by
  whichever profile is active on the current bar. This mirrors the live
  `strategy_engine ↔ strategy_runtime` boundary's existing, correct
  pattern (Engine stateless, caller holds and round-trips the locked
  value) — ported to the historical path, not redesigned.
- **Restore old-BBB attribution semantics on `TradeRecord`/execution
  events.** `exit_reason`/`exit_rule_id`/`exit_component_id`/
  `exit_kind`/`exit_layer` populated from Engine's attributed initial-
  protection/signal-exit-candidate data, not synthesized as a coarse
  always-on-only category as today. This is a hard invariant (per the
  companion change's third correction): proving equal PnL without equal
  attribution content is not sufficient parity.
- **Stop embedding the Strategy Engine evaluation inside `result.json`.**
  `SingleInstanceBacktestResult` references its evaluation by identity
  rather than re-nesting the full object. The compact
  `HistoricalExecutionProjection` is persisted once, as its own
  artifact — packaging-only, safe only after I5 parity is proven (see
  Master Plan).
- **Stop retaining the raw Engine response body.** `raw=body` retention
  removed — no `raw` field exists once the mandatory contract carries no
  diagnostic data.
- **Make dense diagnostics a separate, optional, on-demand capability.**
  Unchanged from the original proposal: a run/candidate that needs
  diagnostics gets them via an explicit request to Strategy Engine's
  diagnostic-evaluation entrypoint, persisted as a separate artifact,
  fail-closed on provenance mismatch. `application/diagnostics/
  projection.py`'s "No read-time upstream calls" invariant is preserved
  for reading an already-generated artifact.
- **Batch settlement was a separate, binding follow-on phase (I8) —
  now complete.** `RunBatchExperiment`'s per-candidate loop was already
  correct on the Research side; the aggregation pattern that used to
  hold N results simultaneously during one `/range-batch` call is fixed:
  `/range-batch` streams a `.v2` sequence (one shared Engine-side
  market-data acquisition, sequential per-variant evaluation/emission),
  and `RunBatchExperiment` consumes it one candidate at a time,
  materializing/persisting/releasing each through the same canonical
  single-instance path before the next is produced. Confirmed
  constant-in-N peak RSS on both the Engine-process and Research-process
  side (N=1/2/4/11 benchmark, `I8_GATE_PASSED`).

## What Does Not Change

- No change to fee/PnL/equity computation math — only the shape of the
  data Engine hands Research, and the previously-missing locked-profile/
  attribution logic that consumes it. Restoring locked-profile semantics
  changes *which* exit rule applies on a given bar for a given trade
  (a real, intended behavior fix versus today's always-on-only
  execution) — it does not change how fills/fees/PnL are computed once
  an exit is determined.
- No change to `research-batch-experiments-v1`'s existing requirements.
- No change to the public `/api/research/backtests`/`/api/research/runs/
  ...` HTTP surface shape for callers that only read trades/metrics/
  summary.
- **No change to Strategy Runtime or any live-facing contract** —
  Research has no direct relationship to `strategy_runtime`'s live
  boundary (that's entirely within `strategy_engine`'s scope), stated
  here only to confirm this change does not indirectly touch it via any
  shared code path.
- Migration order is strictly gated (see Master Plan): no execution-loop
  rework before Engine's projection is proven correct (I2) on a
  profile-sensitive adversarial spec; no persistence-split work before
  N=1 end-to-end parity (I5); no batch work before I7's single-instance
  production cutover.

## Impact

- Affected capabilities: `research-run-artifacts-v1` (MODIFIED — bundle
  no longer double-embeds the evaluation, diagnostics no longer
  mandatory), `research-diagnostics-projection-v1` (MODIFIED — dense
  diagnostics become explicit/separately-generated, ownership and
  fail-closed provenance-match), `research-unified-execution-loop-v1`
  (MODIFIED — consumes `HistoricalExecutionProjection`, adds
  `locked_exit_profile`/attribution restoration requirements, checks
  `market_data_hash`/`bar_count`/range/`bar_index` instead of removed
  `time_ms`), `research-batch-experiments-v1` (no requirement changes —
  context only), `research-historical-execution-parity-v1` (ADDED —
  I5's N=1 end-to-end proof-only gate; a new capability, not a
  modification of production behavior).
- Affected code, I3+ (deferred, not part of this I0 proposal):
  `adapters/http/strategy_engine_client.py`, `domain/contracts.py`
  (consume the new projection shape), `execution/loop.py`,
  `execution/entry.py`, `execution/static_exits.py`,
  `execution/protection.py` (`PositionState.locked_exit_profile`,
  per-profile candidate lookup, attribution population),
  `application/backtests/strategy_contract.py`, `application/backtests/
  artifacts.py`, `application/backtests/read_artifacts.py`,
  `application/diagnostics/projection.py`, `application/experiments/
  run_batch.py` (unaffected in structure until I8).
