## Context

Companion to `strategy_engine`'s `compact-strategy-evaluation-boundary-v1`.
**This is a revision, not the original document.** The original design
targeted a flat sparse `StrategyDecisionEvent` (point-query consumption,
`entries`+`stop_ready`, no exit-profile handling) — that Engine-side
shape was shipped but never consumed on this repo (tasks below were not
started), and a second, deeper audit (old BBB execution core vs current
Research consumer map vs the live `strategy_engine ↔ strategy_runtime`
boundary) found it would have reintroduced a real trading-semantics
defect: Research's execution loop has never implemented locked-exit-
profile semantics, and the flat contract removes even the possibility
of adding it. This revision targets the companion change's corrected
`HistoricalExecutionProjection` model instead. Persistence-split and
diagnostics-ownership sections below are unaffected by the semantic
correction (packaging concerns, not execution semantics) and are carried
forward unchanged.

## Semantic gap this revision closes (audit summary)

- **Locked exit profile — not implemented today.** Grepped `execution/
  *.py`: zero references to exit-profile selection logic. `execution/
  protection.py:19`/`execution/static_exits.py:29` read only the
  top-level `signal_exit`/`stop_loss_ratio`/`take_profit_ratio`/
  `stop_ready` keys of Engine's evaluation — the `always_on` exit set,
  unconditionally, for every trade. Engine's current (superseded) dense
  contract already exposes `profile_long`/`profile_short`/`by_profile.*`
  — Research has simply never read them.
- **Old BBB reference semantics** (both its vectorbt/Numba path and its
  managed execution loop): an exit profile is locked once at entry,
  held fixed for the trade's life, and signal-exit/SL-TP lookups on
  later bars are indexed by the *locked* profile — never the profile
  active on the current bar.
- **The live `strategy_engine ↔ strategy_runtime` boundary already
  implements the correct pattern** and is the reference to port:
  Engine is stateless per call; on `live-entry` it returns
  `locked_exit_profile` once; Runtime captures it and round-trips it
  back on every subsequent `open-trade` call. This plan ports that
  "caller holds the locked value" pattern to the historical execution
  loop — it does not touch the live boundary itself.
- **Exit attribution — same gap.** Research's execution loop never reads
  `component_evidence`/`rule_evidence`; `TradeRecord.exit_reason`/
  `exit_rule_id`/`exit_component_id` are populated today by a coarse,
  always-on-only categorization inside Research, not old-BBB-equivalent
  per-rule attribution.

## Consumption: `HistoricalExecutionProjection`, not flat point-query events

Supersedes this document's original "point-query against sparse events"
framing (which is still correct as a *lookup pattern*, but the object
being looked up is corrected):

- **Executable entry opportunities** replace dense `entries`+`stop_ready`
  point-queries. Each opportunity carries `locked_exit_profile` (the
  profile active at that bar — the value Research locks in if it treats
  this bar as the real entry) and attributed `initial_stop`/
  `initial_take` (`{ratio, attribution: ExitAttribution} | null` — see
  companion `strategy_engine` capability for `ExitAttribution` shape and
  leg-nullability rule).
- **Per-side, per-profile signal-exit event lists** replace the flat
  `signal_exit[side][bar]` point-query. Once Research has locked a
  profile for an open position, subsequent-bar lookups are against that
  one profile's own event list — not a current-bar-profile value.
- `stop_loss_ratio`/`take_profit_ratio` remain read **only at the entry
  bar** (now sourced from the entry opportunity's `initial_stop`/
  `initial_take`, not a dense per-bar array), cached on
  `PositionState`, never re-read — this part of the original per-field
  losslessness proof is unaffected by the correction.

## `PositionState.locked_exit_profile` (the core Research-side fix)

`PositionState` lives in `domain/execution.py` (not `execution/
protection.py` — that module holds the resolution *function*,
`resolve_initial_protection`, not the state type; corrected from an
earlier draft of this document that cited the wrong module).

```
entry_opportunity (side, locked_exit_profile, initial_stop, initial_take)
  → Research fill
  → resolve_initial_protection(entry_opportunity, fill)  # ONCE, at fill
  → PositionState(side, locked_exit_profile, initial_protection, ...)

every subsequent open bar:
  stop/take check: against PositionState.initial_protection already
    stored at fill time — NOT re-looked-up from the projection
  signal-exit check only:
    position.locked_exit_profile
      → HistoricalExecutionProjection.signal_exit_events[side][locked_profile]
      → candidates for THAT profile, never today's active profile
```

The initial-protection resolution is entry-bar-only, matching the
reference model exactly — it is not re-queried on later bars under any
circumstance. Only signal-exit lookup is per-bar and profile-keyed;
protection-level checking on later bars uses the values already stored
at fill time.

This is the Research-side half of the reference pattern already proven
on the live boundary: Engine has no trade-lifecycle state, so it can
only ever report "what's the profile at this bar" (via
`locked_exit_profile` on each opportunity) — it cannot itself guarantee
a value is honored across a trade's later bars. Research, which does own
trade-lifecycle state (`PositionState`), is where "hold this value fixed
until exit" actually gets enforced, exactly as `strategy_runtime`
already enforces it for live trades via the round-tripped value.

## Attribution restoration (hard invariant, not preserved-as-is)

`TradeRecord`/execution-events output gains `rule_id`/`component_id`/
`exit_kind`/`layer` sourced from Engine's attributed `initial_stop`/
`initial_take`/signal-exit-candidate data. This explicitly **replaces**
today's coarse always-on-only categorization — it is not a preserve-
current-behavior packaging change. The companion change's deterministic
multi-rule/tied-distance resolution (old-BBB-compatible) is the
attribution Research must reproduce; Research does not invent its own
resolution independently.

## Persistence split (unaffected by the semantic correction — unchanged)

Target artifact shape (replacing today's `strategy_evaluation.json` +
double-embedded `result.json`):

```
result.json
  canonical Research result: identity, provenance, accounting, trades, ...
  (references its evaluation by run_id/market_data_hash — no re-embedding)

strategy_evaluation.json
  compact HistoricalExecutionProjection + provenance
  (persisted once)

diagnostics.json  [only when explicitly generated]
  features, contexts, component_evidence, potential_entries
```

No current invariant blocks this split: `SingleInstanceBacktestResult`'s
own model validator checks only `instance_id`/`market` cross-equality —
zero reference to `entries`/`exit_policy`/`component_evidence`/`raw`.
`research-run-artifacts-v1`'s "Bundle completeness" requirement already
treats the evaluation as its own file. This section is unchanged from
the original design — packaging is independent of the semantic
correction above, and is safe to implement only after I5 (Master Plan)
proves parity, per the "Migration order" replacement below.

## Diagnostics become explicit and optional (unchanged)

```
run/candidate exists (compact projection + canonical result already persisted)
  → user/caller requests diagnostics for that run
  → Research calls Strategy Engine's diagnostic-evaluation entrypoint
    for the same immutable strategy + market_data_hash/range
  → Research persists the result as diagnostics.json for that run_id
  → subsequent diagnostics reads use that persisted artifact
```

"No read-time upstream calls" is preserved for the read path; generation
is a distinct write-path operation. Unchanged from the original design.

## bar_index invariant — Research's fail-closed side (unchanged)

Every projection element's `bar_index` indexes exactly the canonical
range described by that response's own `market_data_hash`/`bar_count`.
Research SHALL fail closed if: `market_data_hash` mismatch; `bar_count`
mismatch; declared range mismatch; any `bar_index` outside
`[0, bar_count)`. Unchanged from the original design.

## Diagnostic-evaluation generation — ownership and provenance (unchanged)

Research owns requesting/persisting; Strategy Engine owns computing.
Research reads the run's already-stored provenance, calls Engine's
diagnostic-evaluation entrypoint, fails closed on provenance mismatch
before persisting `diagnostics.json`. Unchanged from the original
design.

## Batch consequence — separate, binding phase, gated behind I7 (revised gating, same technical analysis)

Technical analysis unchanged from the original design: `RunBatchExperiment`'s
per-candidate loop is already correct on the Research side; what's not
fixed is that `EvaluateStrategyRangeBatch.execute`/`/range-batch`'s
response still holds N results simultaneously before that loop starts.
**Gating revised**: this is now explicitly the Master Plan's I8, which
does not start until I7 (single-instance production cutover) is proven
— not merely "after the sparse contract lands," which was this
document's original, looser gating.

## Parity means (revised to match companion change)

`time_ms` remains dropped, so byte-identical full-artifact comparison is
never the bar. Parity is proven when, for the same input:

- executable-entry-opportunity bars/sides match, and `locked_exit_
  profile` is correct at every opportunity (I2-level, Engine alone) —
  and, end to end (I5), the locked profile is correctly held fixed
  across each real trade's life once `PositionState` captures it;
- initial stop/take — ratio and rule/component attribution — are
  identical, including under the deterministic multi-rule tie-break;
- signal-exit candidates under the locked profile are identical for
  every subsequent bar a position is open;
- exit attribution (`rule_id`/`component_id`/`exit_kind`/`layer`) is
  identical on the resulting `TradeRecord`/execution events, trade-for-
  trade;
- the resulting `TradeRecord` sequence is identical and accounting
  totals are exact;
- provenance is semantically equal (`market_data_hash`, `bar_count`,
  `config_hash`, `instance_id`).

The profile-transition adversarial scenario (a trade enters under one
profile, the market's current profile drifts to a different one while
the position stays open) is mandatory parity evidence at I5 — not
optional, not satisfiable by re-running an always-on-only spec.

## I5 implementation strategy (Explore findings, this revision)

Normative requirements live in the `research-historical-execution-
parity-v1` capability; this section records the architectural choices
Explore established, and why each reference is independent (not a
self-comparison), so a future implementer does not have to re-derive
them from this chat.

**Lane A oracle**: Research's own existing, unmodified legacy path —
`RunSingleInstanceBacktest`/`MaterializeBacktestOutcome` calling
`execution/loop.py::run_unified_execution_loop` (via `execution/entry.
py`/`execution/protection.py`/`execution/static_exits.py`, fed by
`adapters/http/strategy_engine_client.py::evaluate_range`'s legacy
`.v1` contract). Independent because it is a materially different
implementation of entry/protection/candidate-collection than the new
`execution/projection_entry.py`/`projection_static_exits.py`/
`projection_loop.py` (I4) — the two paths share only `execution/
unified_exits.py`'s arbitration primitives and `accounting/service.
py::account_execution_loop`, neither of which is what Lane A is
proving. Valid only for an always-on canonical spec (it has no
`locked_exit_profile` concept at all) — this is exactly why Lane B
needs a different oracle.

**Lane B oracle**: extend `strategy_engine`'s already-established
verbatim old-BBB reference (`tests/_old_bbb_exit_attribution_reference.
py`, `roman-vyl/_bbb_new_gen` commit
`cddc83663911f646c9bcf2ecfb37b3bed6f4b1d4`) to a full trade-lifecycle
simulator — entry, locked-profile capture, profile-drift-aware signal
lookup, exit, attribution — built from literal old-BBB functions, never
by calling `execution/projection_*.py` or the legacy path (the legacy
path is not independent evidence for locked-profile behavior, since it
does not implement it).

**Engine new-path invocation**: no new Engine production code is
needed. `EmaPullbackRangeEvaluator._evaluate_frame_native(request)`
(the same native pipeline `evaluate_execution` already calls) produces
`(frame, evaluation)`; `build_historical_execution_projection` is
called with the identical provenance derivation `evaluate_execution`
already uses (`strategy_id=request.strategy.strategy_id`, `config_
hash=strategy_config_hash(request.strategy)`, `market_data_hash=frame.
market_data_hash`, `bar_count=len(frame.time_ms)`) — both already
shipped, I1-proven functions, called in-process, no route involved.

**Transport-equivalent mechanism**: no `v2` serializer exists in
Strategy Engine's shipped code yet (confirmed by Explore: only the
`.v1` `serialize_strategy_evaluation_execution` exists, `adapters/http/
strategy_serialization.py`). I5 needs a proof-only serializer in
`strategy_engine` mirroring that function's exact structure but for the
`v2` shape already normatively fixed in `strategy-research-execution-
contract-v1` (commit `dae5b4e`) — not production/route code, analogous
to `strategy_engine`'s own `scratch/parity_proof.py` precedent there (a
real-MDS, throwaway measurement script, not `src/`). Because Strategy
Engine and
Research Service are separate processes, this proof is necessarily
two-phase and file-mediated: an Engine-side script writes a real `v2`
JSON envelope to a file; a Research-side script reads that file and
feeds it, unmodified, to `parse_historical_execution_projection`. Exact
file paths/directory layout are an I5 implementation decision, not
fixed by this design document.

**Research downstream reuse**: `ResolveBacktestWindow`/`full_available`
window resolution (`history_window.py`, unchanged — used by *both*
lanes' *both* paths so every path resolves the identical `market_data_
hash`/range from the same real MDS call, never independently
re-resolved) and `account_execution_loop`/`TradeAccountingResult`/
`TradeRecord` (`accounting/`, unchanged). Only the execution source
changes: `run_projection_execution_loop` (I4) instead of `run_unified_
execution_loop` for the new path.

**MDS/`full_available` mechanism**: `ResolveBacktestWindow.execute(
range_policy="full_available")` — `MarketDataPort.get_bounds`/`audit_
range`, exactly Research's existing production mechanism, matching the
precedent already used by `strategy_engine`'s own prior `full_available`
measurement (`scratch/parity_proof.py`, `GET /v1/streams/{ticker}/
{timeframe}/bounds` against a real local MDS at `127.0.0.1:8080`,
675,986 bars measured for `BTCUSDT.P`/`5m` at that time — the range
grows over time, so I5 re-resolves it at run time rather than pinning
that historical bar count).

**Parity comparison surface**: enumerated exactly, field-by-field, in
`research-historical-execution-parity-v1`'s "Zero-diff comparison
surface" requirement — sourced from `EntryFill`/`PositionState`/
`InitialProtection`/`ExitFill`/`TradeRecord`/`TradePathMetrics`/
`TradeAccountingResult`, all already-shipped models, no new fields
introduced. Explore confirmed there is no long/short-split aggregate at
N=1 scope in this codebase (`application/experiments/candidate_summary.
py`'s split is a batch-only artifact) — I5 does not invent one.
Tolerance: exact equality throughout, except reusing (not introducing)
`strategy_engine` I1's own `eps = 1e-9 * max(1.0, abs(value))` where a
wire `ratio: float` itself is compared, before its one-time Decimal
conversion.

**Harness location**: split across repos, bridged by a materialized
JSON file (not a live HTTP call, not shared process memory) — a
Strategy Engine proof-only script and a Research Service proof-only
script/acceptance test. Neither location nor file layout is normative;
the capability spec fixes behavior, not paths.

## Master Plan reference (supersedes the old "Migration order" section)

This design is I0 (Spec Freeze). Full checkpoint definitions live in the
coordinator's approved master plan; this repo's tasks.md carries the
Research-relevant checkpoints as actionable tasks. Summary of what
`research_service` owns:

- **I3** — new DTO/parser for the `HistoricalExecutionProjection` shape
  plus indexed lookup structures (`entry_by_bar`,
  `signal_candidates_by(side, locked_profile, bar_index)` or
  equivalent). No production cutover of Research's *historical*
  execution loop (the `/range`-driven backtest path — distinct from any
  live/Runtime-facing path, which this repo has no relationship to).
- **I4** — `PositionState.locked_exit_profile` + attribution
  restoration in the execution loop, proven against the same profile-
  sensitive adversarial scenario as Engine's I2, at the Research
  execution-loop level.
- **I5** — joint with `strategy_engine`: one real `full_available` N=1
  run, old/reference semantics vs. the new path, zero diffs on the full
  "Parity means" list above, including the profile-transition
  adversarial case.
- **I6** — persistence/diagnostics split (the sections above), safe
  only once I5 is green.
- **I7** — joint coordinated cutover, **single-instance `/range` only**.
  `/range-batch` may gain schema compatibility if technically necessary
  but is not thereby production-approved.
- **I8** — batch lifetime, joint, only after I7.

## I6 implementation strategy (Explore findings, this revision)

Normative requirements live in the `research-run-artifact-parity-v1`
capability; this section records what EXPLORE found in both
repositories' actual code, so a future implementer does not have to
re-derive it.

**Old BBB's Run model** (`roman-vyl/_bbb_new_gen@cddc836`,
`research/strategies/ema_pullback/execution/results.py`): one Run
produces three files under `research/results/`:
`runs/<run_id>.json` (full report: `run_id`, `created_at`,
`report_schema_version`, `family`, `symbol`, `timeframe`, `candles`,
`data_range{from_open_time_ms,to_open_time_ms}`, `variants_count`,
`trade_quality_config`, `path_diagnostics_config`, `variants[]` — each
variant carries `strategy_spec`, `metrics` (long/short/total
`SideMetrics` + sharpe + max_drawdown + open_trades + optional
breakdowns), `component_counters`, and the full `trade_records[]`);
`runs/<run_id>.summary.json` (`build_compact_report_payload`: the same
shape with `trade_records`/`candles`/`ohlcv`/`component_events`/
`trade_management_events`/`signal_trace`/`trace` stripped, replaced by
counts); `latest.json` (identical content to the current run's full
report — a pointer, not separate content). Per-trade fields
(`extract_trade_records`): `direction`, `status`, `entry_time_ms`,
`exit_time_ms`, `entry_price`, `exit_price`, `size`, `pnl`,
`return_pct`, `exit_reason`, `gross_pnl`, `fees_paid`,
`gross_return_pct`, `exit_group`, `exit_profile`, `exit_component_id`,
`exit_instance_id`, `exit_kind`, `entry_idx`, `exit_idx`, `hold_bars`,
`hold_minutes`, `entry_profile`, `active_exit_profile`,
`entry_context_state`, plus `build_trade_quality_diagnostics`'s
path-quality fields. No separate execution-event stream, no separate
strategy-evaluation/projection artifact, no manifest file, no content
hash per file — old BBB is a monolith with no wire boundary to
provenance-hash.

**Current Research Run model** (`application/backtests/artifacts.py::
PersistSingleInstanceBacktest`): one Run persists eight files:
`request.json`, `strategy_evaluation.json` (today the legacy dense
`StrategyEvaluationResult`; post-I6 the canonical
`HistoricalExecutionProjection`, per `research-run-artifacts-v1`),
`execution_events.json` (`ExecutionEvent[]`), `trades.json`
(`TradeRecord[]`), `metrics.json` (a `TradeAccountingResult` subset),
`managed_policy_events.json`, `result.json` (the full
`SingleInstanceBacktestResult`, currently re-embedding the evaluation —
post-I6, references it by identity instead), `manifest.json`
(`RunArtifactManifest`: contract versions, per-file sha256/size,
`market_data_hash`, `created_at_utc`). `run_id` is Research-generated
(`f"run_{uuid.uuid4().hex}"`, `materialize_backtest_outcome.py::
_generate_run_id`) — a random UUID, not a function of Run content.

**Old BBB ↔ new Research field mapping, scoped to the common-facts
comparison surface only** (`research-run-artifact-parity-v1`'s "Common-
facts comparison surface" requirement — this is deliberately NOT a
full field-union mapping of both systems' entire artifact models; rows
marked "out of cross-system scope" exist on one or both sides but are
not diffed against each other, per that requirement):

| Old BBB | New Research | In common-facts surface? |
|---|---|---|
| `trade_records[]` (per-trade, entry+exit together) | `trades.json` (`TradeRecord[]`) + `execution_events.json` | yes — entry facts read from the `entry_filled` event and `TradeRecord`'s `entry_*` fields |
| `entry_idx`/`exit_idx` | `entry_bar_index`/`exit_bar_index` | yes |
| `exit_instance_id` | `exit_rule_id` | yes |
| `exit_component_id` | `exit_component_id` | yes |
| `exit_kind` | `exit_kind` | yes |
| `exit_profile` | `PositionState.locked_exit_profile` (I4) | yes, where the spec is profile-sensitive |
| `pnl`/`gross_pnl`/`fees_paid`/`return_pct` | `net_pnl`/`gross_pnl`/`fees_paid`/`net_return_pct` | yes |
| `hold_bars` | `hold_bars` | yes |
| `build_trade_quality_diagnostics` MFE/MAE fields | `TradePathMetrics.mfe_*`/`mae_*` | yes (only the quantities both sides compute the same way) |
| `VariantMetrics.total` | `TradeAccountingResult` (`realised_trade_count`, `gross_pnl`, `fees_paid`, `net_pnl`) | yes |
| `<run_id>.summary.json` | `metrics.json` | yes, as a sanity cross-check that each side's own summary agrees with its own trades |
| `exit_group`, `profile_breakdown`/`exit_reason_breakdown`/`fee_diagnostics`/`bounce_counter_breakdown`/`quality_flag_breakdown` (old BBB optional breakdowns) | — | **out of cross-system scope** — derived/optional, not diffed |
| `hold_minutes`, `active_exit_profile`, `entry_context_state` | `hold_ms`, `exit_layer`, `TradePathMetrics.capture_ratio`/`giveback_*` | **out of cross-system scope** — computed by only one side |
| `run_id`/`created_at`, `symbol`/`timeframe`/`candles`/`data_range` | `run_id`, `manifest.json`, `instance_id`/`config_hash`/`market_data_hash`/market identity | **out of cross-system scope** — new-side fields verified for internal correctness only, per "New-side provenance/storage fields are verified, not cross-compared"; old BBB has no wrapper-identity/hash equivalent to compare them to |

**Frozen-input mechanism**: `ResolveBacktestWindow` (`application/
backtests/history_window.py`), already shipped, already the mechanism
I5 reuses — resolves `full_available`/`explicit_range` exactly once via
`MarketDataPort.get_bounds`/`audit_range`, producing one
`ResolvedBacktestWindow{market, market_data_hash, expected_bar_count,
audit}`. No new MDS interface needed for I6 either.

**Old BBB proof-input adapter**: old BBB never calls Research's
`MarketDataPort` — it loads candles directly from its own local store
(`data_engine.store.Db`, via `execution/data_loader.py::
load_candles_once`) into a `pandas.DataFrame` shaped by
`ema_smoke_helpers.py::candles_to_ohlcv_dataframe`
(`open_time_ms`-indexed, `open`/`high`/`low`/`close`/`volume`
columns). The I6.A proof-only harness SHALL construct that exact
DataFrame shape directly from the one resolved `MarketFrame.candles`
Research's own pipeline used — bypassing `load_candles_once`/`Db`
entirely for this proof — never letting old BBB open its own DB
connection and independently resolve "the same" range. This changes
nothing in old BBB's production architecture; it is a proof-only
adapter function, analogous to how I5.A's Engine-side script calls
`build_historical_execution_projection` directly rather than through
`/range`.

**Diagnostic-only vs execution-semantic** (for "No silent loss of
common-surface content through the diagnostics split"): feature series,
context data, component evidence, and potential-entry traces
(`research-diagnostics-projection-v1`'s existing scope) are
diagnostic-only — old BBB has no equivalent separately-persisted
concept (it recomputes everything from the monolith's live pipeline
state on demand), and neither side needs them for the common-facts
comparison. Every "yes" row in the field-mapping table above is
execution-semantic and IS in the common-facts comparison surface —
I6's diagnostics split does not touch any of it.

## Out of scope for this change

- Exact wire/API shape of the diagnostic-generation request/route
  (ownership/provenance fixed; route/schema detail deferred to I3/I6
  implementation planning).
- Any change to indicator math, accounting math, or fee/PnL computation
  logic (the *inputs* to attribution/exit-selection change; how
  fees/PnL are computed once an exit is determined does not).
- Exact transport/call-pattern mechanics for I8's per-candidate release
  phase.
- Any change to Strategy Runtime or live-facing contracts — Research has
  no direct relationship to that boundary; noted here only to confirm
  this change does not touch it indirectly.
