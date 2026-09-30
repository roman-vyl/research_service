## Context

- Strategy Engine baseline: `main` `07ff911` (PR #21). Wire contract of
  `managed` in `/range-batch` and `/range`: `strategy_serialization.py::_serialize_managed_projection`.
  Normative text: `strategy_engine/openspec/specs/historical-managed-projection-v1/spec.md`,
  including "Composite phase transitions are projected as paths" and
  "Path attribution parity".
- Research base: branch `historical-managed-projection-v1` @ `3167831`.
  It is 4 commits over `main` `5018ec8` and 0 behind. It already has
  `ManagedTradeState`, `ManagedRuleSet`, the incremental
  `advance_managed_trade_state`, fail-closed resolution and the explicit
  legacy oracle opt-in.
- Reference consumer for paths semantics:
  `strategy_engine/tests/test_ema_pullback_historical_managed_projection.py::_path_met`.
- Reference event semantics:
  `strategy_engine/src/strategy_engine/strategies/ema_pullback/managed.py::_evaluate_managed_replay_core`.
- Hard constraint (owner): no growth of expensive Strategy Engine work
  and no growth of CPU for existing (atomic) runs. Research's own
  lifecycle CPU may grow, because it replaces Engine replay work.

## Goals / Non-Goals

Goals: decode and execute the final contract generically; restore
`managed_policy_enabled` semantics; keep a meaningful event trace;
commit reproducible parity and performance gates; merge.

Non-goals: any Strategy Engine change; retiring `/managed-replay`;
batch stream isolation; new managed semantics.

## Decisions

### D1. Three-way XOR on the phase rule, generic path DTOs

`ManagedPhaseTransitionRuleDTO` gains `paths: tuple[ManagedTransitionPathDTO, ...] | None = None`.
Its validator requires exactly one of: `condition_id`;
(`distance_id` and `trade_metric`); `paths` (non-empty). All new DTOs
are `frozen=True, extra="forbid"`:

- `ManagedTransitionThresholdDTO(distance_id, trade_metric)`
- `ManagedTransitionTermDTO(condition_id | (distance_id, trade_metric))`,
  exactly one
- `ManagedTransitionAtLeastDTO(k >= 1, terms non-empty, k <= len(terms))`
- `ManagedTransitionPathDTO(path_id, condition_id | None, thresholds, at_least | None)`

`HistoricalManagedProjectionDTO` additionally validates that every
`condition_id` and `distance_id` referenced by any rule, path, threshold
or term exists in `conditions` or `distances`. A dangling reference
fails decode, which keeps the existing fail-closed behaviour, instead
of raising `KeyError` mid-loop.

Atomic rules keep their exact current shape. Engine omits `paths` for
them, so their bytes are unchanged.

### D2. One shared phase-rule evaluator

A module-level function
`_phase_rule_met(rule, projection, side, metrics, index) -> tuple[bool, str | None]`
is used by both `advance_managed_trade_state` (production) and
`build_managed_policy_timeline_from_projection` (oracle). Order of
checks: `condition_id`, then `distance_id`, then `paths`, so atomic
rules pay no extra cost. Path semantics, per Engine spec:

- the path's `condition_id`, if present, must be true for the trade side;
- every threshold must hold: `metrics[trade_metric] >= distances[distance_id][index]`,
  and `None` (NaN on the wire) is false;
- `at_least`, if present, must count at least `k` true terms, where a
  market term reads its condition and a trade term compares like a
  threshold;
- the rule fires on the first true path in order and returns its
  `path_id`.

Cost: O(paths x terms) per open bar, only while the trade's phase is
below the rule's target, and only for candidates that have paths.

### D3. Stop attribution mirrors `managed.py`

`managed.py` updates `active_stop_price`/`active_stop_rule_id` only when
`active_stop_price is None or abs(tightened - active) > 1e-8`. The
branch sets the rule id to the chosen candidate on every bar, and the
price to `tightened` even for sub-`1e-8` moves. With several stop rules
this can re-label the active stop without the price moving, which
diverges `TradeRecord.exit_rule_id`. Both the incremental and the eager
path adopt Engine's rule. The 203-trade corpus had one stop rule, which
is why it never showed up.

### D4. Gating before implementation choice

`_open_managed_state` returns `(None, None)` first when
`managed_replay_provider is None`. That is the existing signal that the
caller did not request managed execution (`managed_policy_enabled=False`
or a non-managed run). The remaining order is unchanged: projection
present and no opt-in means local incremental; opt-in means legacy
oracle; projection absent and no opt-in means fail closed.

### D5. Local managed events from the incremental consumer

`advance_managed_trade_state` takes an optional keyword `event_sink`
(a list) and appends the events produced on that bar to it. When it is
`None`, no events are built, and existing callers keep their signature.

Ownership: events are observations of state transitions that the
generic projection consumer has already produced. They are not a
second implementation of Strategy Engine policy or event semantics.
Each event is emitted at the point where the consumer's own state
changes: `_phase_rule_met` fired a transition; the stop selection
actually changed the active stop (D3); the take selection changed the
profile; a generic runtime rule is armed. Strategy Engine stays the
owner of policy, and Research only reports what happened while
executing the projection contract.

| event | observed when | fields |
|---|---|---|
| `phase_changed` | each phase rule that fires (several per bar possible, in rule order) | `rule_id`, `from_phase`, `to_phase`, `price = mfe_price`, `metadata = {"path_id": ...}` for paths, else `{}` |
| `active_stop_updated` | the D3 update actually happens | `rule_id`, `price = new active stop`, `metadata = {"effective_from_bar": index + 1}` |
| `active_take_updated` | profile changes | `rule_id`, `metadata = {"take_profile": profile, "effective_from_bar": index + 1}` |
| `runtime_exit_triggered` | every bar a runtime rule is armed | `rule_id`, `price = bar close`, `metadata = {"exit_kind": canonical kind of exit_class, "effective_from_bar": index + 1}` |

Every event carries `time_ms`/`bar_index` of the source bar and
`position_id`/`side`. `component_id` is `None`, because the contract
carries none by design.

Event-only prices are diagnostic derivations and MUST NOT participate
in policy decisions: `phase_changed.price` is the MFE price derived
from Research's own execution state (entry price, best price, side),
and `runtime_exit_triggered.price` is the bar close observed in the
`MarketFrame`. Neither is part of the projection contract.

`run_projection_execution_loop` takes an optional `managed_event_sink`
and passes it through. `MaterializeBacktestProjectionOutcome` passes the
same `managed_policy_events` list the legacy provider fills, and only
when managed execution was requested. The artifact
contract (`research_managed_policy_events.v1`) and API are unchanged.
`advance_managed_trade_state` takes a `close` argument for the runtime
event price.

Event horizon. The projection loop runs exit arbitration at bar open
first; if the position closes on bar N, its state is discarded and
`advance_managed_trade_state(N)` is not called. So:

- closed position with `exit_bar_index = N`: local events cover bars
  `entry_bar_index .. N - 1`;
- position still `open` at the end of the requested range: local events
  cover bars `entry_bar_index ..` the last market bar, which is also the
  end of the legacy `/managed-replay` evaluation range.

`/managed-replay` always evaluates to the end of the range, so for a
closed position the legacy trace also contains events after its exit.
The parity harness applies the horizon in D6.

Cost: one list allocation per bar and appends only on change or armed
runtime bars. No extra passes.

### D6. Parity harness (`scripts/managed_projection_parity.py`)

Operator-run, against a live Strategy Engine and Market Data Service
(URLs from arguments or settings). For each candidate file (strategy
spec plus execution/accounting/range), it runs `RunSingleInstanceBacktest`
twice: OLD (`allow_legacy_managed_replay_fallback=True`) and NEW
(default). Engine calls are counted through a thin counting wrapper
around the `StrategyEnginePort`.

It compares:

- every `TradeRecord` field, except the per-run labels
  (`trade_id`/`position_id`/`instance_id`/run ids);
- the `TradeAccountingResult` summary and candidate metrics;
- managed events, per position, over the D5 horizon: for a closed
  position, OLD events with `bar_index < exit_bar_index`; for a
  position open at the end of the range, all OLD events through the
  last bar of the evaluation range. Both are compared with all NEW
  events of that position, on (`bar_index`, `event_type`,
  `rule_id`, `from_phase`, `to_phase`, `price`, `metadata.path_id`,
  `metadata.take_profile`).

Allowed diagnostic differences, reported separately and never counted
as failures: `exit_component_id`, the component suffix of
`exit_reason`, the `exit_kind` literal on runtime exits (NEW carries
the canonical kind of `exit_class`), event `component_id`, and event
`metadata` keys other than those compared above.

It asserts NEW `managed_replay_calls == 0`, and OLD
`managed_replay_calls ==` the number of positions for which managed
execution was initialized (counted by the harness at the provider). It
additionally reports whether that equals the number of opened trades;
for the required corpus it must. It writes a JSON
report and exits non-zero on any failure.

Required corpus, on Engine `07ff911`: one atomic candidate (the EMA500
RSI87 Stage-1 shape from the archived 5.2) and one composite candidate
(owner case: `(ADX5 > 35 OR (ADX1h > 25 AND DI 1h)) AND MFE >= threshold → proven`),
both sides enabled.

### D7. Performance harness (`scripts/managed_projection_benchmark.py`)

Operator-run. Runs a batch (`RunBatchExperiment`) or single candidates
over several natural windows (low / medium / high trade count). Trade
counts are not constructed artificially. Records per workload: trade
count; Research-side HTTP calls per endpoint (`/range`, `/range-batch`,
`/managed-replay`) from the counting wrapper; Research process CPU
(`time.process_time`); Engine process CPU (delta of `ps -o cputime= -p <pid>`
when `--engine-pid` is given, portable Linux/macOS); total CPU; wall
time. Optional `--with-oracle` also runs OLD for the same workload.

Acceptance (hard):
- NEW `/managed-replay` calls = 0 on every workload;
- Engine evaluation calls per candidate do not depend on trade count
  (1 `/range-batch` per batch, or 1 `/range` per single run);
- NEW median wall time < OLD median wall time per workload, over at
  least 3 paired OLD/NEW runs (`--with-oracle --repeats N`, N >= 3). No
  minimum speed-up percentage is required.

Recorded, not gated: Engine CPU, Research CPU and total CPU per
workload. A total-CPU regression is acceptable only if the report
explains its bound. Research CPU alone is not a criterion.

### D8. Merge

After D6 and D7 pass on the owner's command, the branch (existing 4
commits plus this change) merges into `main` through a PR, only on the
owner's command.

## Risks / Trade-offs

- Event parity depends on Engine event rules staying as they are in
  `07ff911`. If Engine changes them later, the parity harness will
  flag it.
- D3 changes `exit_rule_id` on multi-stop-rule candidates relative to
  the branch. It is a fix toward the oracle, and the harness verifies it.
- Live gates need the owner's Engine, MDS and data. They are not run by
  CI; unit tests cover the logic.
