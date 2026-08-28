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
