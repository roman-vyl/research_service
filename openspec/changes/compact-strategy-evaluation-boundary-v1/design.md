## Context

Companion to `strategy_engine`'s `compact-strategy-evaluation-boundary-v1`
— that change defines the sparse `StrategyDecisionEvent`/
`StrategyEvaluationExecution` wire shape and proves it lossless
per-field. This document covers the Research-side consumption,
persistence, and diagnostics-split consequences.

## Consumption: point-query against sparse events

The companion change's design doc proves every current dense-array
consumer on the Research side already reads via point-query, not dense
scan:

- `entries`/`stop_ready` — read once per bar, only while flat
  (`execution/entry.py`).
- `signal_exit` — read once per bar, only while a position is open
  (`execution/static_exits.py`).
- `stop_loss_ratio`/`take_profit_ratio` — read **only at the entry bar**,
  cached on `PositionState.initial_protection`, never re-read
  (`execution/protection.py::resolve_initial_protection`).

Consuming the sparse event list instead of dense arrays means: for a
given `bar_index`, look up whether a `StrategyDecisionEvent` exists at
that index (e.g. via a dict keyed by `bar_index`, or a sorted list with
binary search) — the same call sites, the same point-query pattern,
just against a sparse structure instead of a dense array. This is
provably the same information reaching the same consumers; it is not a
behavior change to execution/accounting logic.

`time_ms` is dropped from the contract entirely (companion change).
`TradeRecord.entry_time_ms`/`exit_time_ms` already come from Research's
own `MarketFrame.candles[bar_index].open_time_ms`, never from Engine's
copy — this removes a source that was already unused for that purpose.
`strategy_contract.py`'s existing validation-only equality check against
Engine's `time_ms` is removed along with the field it checked; nothing
downstream loses information it was actually using.

## Persistence split

Target artifact shape (replacing today's `strategy_evaluation.json` +
double-embedded `result.json`):

```
result.json
  canonical Research result: identity, provenance, accounting, trades, ...
  (references its evaluation by run_id/market_data_hash — no re-embedding)

strategy_evaluation.json
  compact execution evaluation: decision_events, provenance
  (the sparse contract from the companion change, persisted once)

diagnostics.json  [only when explicitly generated — see below]
  features, contexts, component_evidence, potential_entries
```

No current invariant blocks this split (verified this session, not
assumed): `SingleInstanceBacktestResult`'s own model validator checks
only `instance_id`/`market` cross-equality between
`strategy_evaluation`/`execution`/`accounting` — zero reference to
`entries`/`exit_policy`/`component_evidence`/`raw`.
`research-run-artifacts-v1`'s "Bundle completeness" requirement already
treats the evaluation as its own file; it does not require `result.json`
to re-embed it. Splitting removes a code-level choice
(`SingleInstanceBacktestResult.strategy_evaluation` field forcing
re-embedding, `PersistSingleInstanceBacktest.execute` writing the whole
model to `strategy_evaluation.json` and again inside `result.json`), not
a spec requirement.

`ReadResearchRuns` (`application/backtests/read_artifacts.py`) currently
deserializes the entire dense object via Pydantic on every "open a run"
call while only ever touching `strategy_evaluation.market` and
`accounting.trades` (confirmed by grep — zero other field access across
every BFF call site: detail, summary, trades, metrics). Once the
evaluation is lean (no dense fields), this stops being a meaningful cost
regardless; the split also lets call sites that only need `market` avoid
touching the (now separate) diagnostic artifact at all.

## Diagnostics become explicit and optional

Current `research-diagnostics-projection-v1` implicitly requires every
persisted run to already carry dense diagnostic data, because
`application/diagnostics/projection.py` reads it from "the persisted
Strategy Engine evaluation." This change makes diagnostics generation an
explicit, separate write-path action:

```
run/candidate exists (compact evaluation + canonical result already persisted)
  → user/caller requests diagnostics for that run
  → Research calls Strategy Engine's diagnostic-evaluation entrypoint
    (companion change task 3.2) for the same immutable
    strategy + market_data_hash/range
  → Research persists the result as diagnostics.json for that run_id
  → subsequent diagnostics reads use that persisted artifact
```

This is a genuine, deliberate change to `research-diagnostics-
projection-v1`'s implicit contract, not a compatibility shim — stated
explicitly per the coordinator's instruction not to preserve the current
mandatory-dense-diagnostics shape for compatibility's sake.

**"No read-time upstream calls" is preserved, not violated.** That
existing requirement governs the diagnostics *read* path (signal-trace,
chart-events) — it still holds: reading an already-generated
`diagnostics.json` makes no upstream call. The generation step above is
a distinct, new write-path operation this change introduces; it is not
"a diagnostics projection request calling upstream," it's "a request to
materialize a diagnostic artifact that a projection can later read
without calling upstream."

## Batch consequence (no new batch execution model)

`RunBatchExperiment.execute` (already correct since
`batch-candidate-canonical-summary-v1`: shared window/Engine-call once,
then a truly sequential per-candidate materialize→persist→release loop)
needs no structural change. Its cost profile changes as a direct
consequence of the evaluation contract shrinking from O(bars) to
O(events) and diagnostics becoming opt-in: N candidates' combined
`/range-batch` response shrinks from N × (dense per-bar payload) to N ×
(sparse event list), and no candidate pays the diagnostic-generation
cost unless explicitly requested. This is the old-BBB shape restored
with the correct service boundary:

```
OLD BBB:      native calculator state → execution, same process
THIS CHANGE:  native calculator state → compact decision events → HTTP → execution in Research
TODAY:        native calculator state → box entire universe into strings → giant JSON → reconstruct → use tiny subset
```

## Migration order (binding, matches companion change)

1. Single-instance `full_available` N=1 parity proof first (byte-
   identical trades/accounting/exit-reasons/provenance, old contract vs
   new). Measure CPU/RSS/body size.
2. Only then does `/range-batch` adopt the same compact contract.
3. Re-run the N=1/2/4/11 memory harness from the earlier diagnostic pass
   this session; confirm approximately constant memory in N.

## Out of scope for this change

- Exact wire/API shape of the new diagnostic-generation request/route
  (a real design decision, deferred to implementation planning).
- Any change to indicator math, accounting math, or fee/PnL semantics.
- `/range-batch` transport mechanics beyond "consumes the same compact
  contract" — no streaming/incremental-response design proposed here.
