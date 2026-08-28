## Status

None of this file's tasks were started (confirmed: `execution/*.py`
today still reads only Engine's `always_on` exit set via the pre-
existing dense contract; no work against the companion change's first
shipped sparse contract happened on this repo). This revision (I0)
replaces the task list wholesale with the corrected model's checkpoints
— there is no shipped-and-now-superseded Research code to rework, unlike
the companion `strategy_engine` change.

## Master Plan checkpoints (I0-I8, this revision)

Cross-repo master plan, 9 gated checkpoints, shared with `strategy_
engine`'s task list. Only **I0 (this task list revision itself)** is
authorized right now. Every checkpoint below requires explicit go-ahead
after its predecessor's gate is confirmed.

- [x] **I0 — Spec Freeze.** This revision: `proposal.md`/`design.md`/
      this file corrected to consume `HistoricalExecutionProjection`
      (executable entry opportunities with `locked_exit_profile` and
      attributed initial stop/take, per-profile-indexed signal-exit
      events), add `PositionState.locked_exit_profile`, add the
      attribution-restoration invariant, revise "Parity means", confirm
      no live-boundary relationship. No application code. Gate:
      `openspec validate --strict` green; spec deltas alone are enough
      to derive I3's DTO/parser shape and I4's execution-loop rework
      without re-reading the audit report.
- [ ] **I2 dependency note.** I3/I4 below cannot start meaningfully
      before `strategy_engine`'s I1/I2 land (Research needs a real
      projection shape to consume and a proven-correct builder to trust)
      — this is a cross-repo ordering constraint, not a task in this
      repo, recorded here so it isn't missed.
- [x] **I3 — Research: Consumer Foundation (no production cutover).**
      New DTO/parser for `HistoricalExecutionProjection`
      (`domain/contracts.py`), plus indexed lookup structures built at
      load time (`entry_by_bar`, `signal_candidates_by(side,
      locked_profile, bar_index)` or equivalent — implementation detail,
      not dictated by wire shape). `adapters/http/strategy_engine_
      client.py` parses the new shape; `raw=body` retention removed.
      Research's *historical* execution loop (the `/range`-driven
      backtest path) is not switched over yet — this task only proves
      Research can parse/index a real projection response correctly.
      Gate: unit tests, correct indexing behavior, no route/production
      change.
- [ ] **I4 — Research: Execution Parity (the decisive Research-side
      gate).** `execution/protection.py`'s `PositionState` gains
      `locked_exit_profile` (captured once at fill time from the
      matching `entry_opportunity`) and enough initial-protection
      identity to reproduce old-BBB attribution. `execution/static_
      exits.py`/`execution/entry.py`/`execution/loop.py` reworked so
      every subsequent open bar's signal-exit/SL-TP candidate lookup is
      keyed by `position.locked_exit_profile`, never current-bar
      profile. `TradeRecord`/execution-events gain `rule_id`/
      `component_id`/`exit_kind`/`layer` attribution sourced from
      Engine's projection, replacing today's coarse always-on-only
      categorization. Managed policy (`execution/managed_policy.py`)
      unaffected — confirmed zero overlap with range-evaluation
      consumption today. Gate: execution unit/integration tests
      reproduce old-BBB semantics on the same profile-sensitive
      adversarial scenario as `strategy_engine`'s I2, at the execution-
      loop level (locked profile held correctly across a profile-drift
      scenario; correct attribution on the resulting `TradeRecord`).
- [ ] **I5 — N=1 End-to-End Proof (joint with `strategy_engine`, the
      single most important gate in this plan).** One real
      `full_available` BTCUSDT.P/5m run, old/reference semantics vs. the
      new Engine→Research path end to end. Full "Parity means" list in
      design.md, including the profile-transition adversarial case
      through the full real pipeline (not just Engine-level as in I2).
      Gate: zero semantic diffs on both the always-on spec and the
      profile-sensitive adversarial spec. Nothing past this point starts
      until this is green.
- [ ] **I6 — Persistence / Diagnostics Split.** Now safe (parity
      proven): `strategy_evaluation.json` becomes the canonical
      `HistoricalExecutionProjection`; `result.json` references it by
      identity instead of re-embedding; `raw=body` retention removed
      (already done in I3, confirm still true); diagnostics become the
      separate, explicitly-generated artifact designed in "Diagnostics
      become explicit and optional"/"Diagnostic-evaluation generation"
      in design.md. Preserve content: `trades.json`, `metrics.json`,
      `execution_events.json`, `result.json`, manifest, lightweight
      run/batch summaries keep their current informational content —
      deduplication is not information loss. Gate: run artifact bundle
      still contains everything I5 verified was needed; no consumer
      (BFF routes, diagnostics projection) regresses; `research-run-
      artifacts-v1`/`research-diagnostics-projection-v1` requirements
      (as amended in I0) hold.
- [ ] **I7 (Research's share) — Coordinated Cutover, single-instance
      only.** Switch Research's *historical* `/range` consumption to
      the I3-I6 path, coordinated with `strategy_engine`'s same-
      checkpoint work (old Research cannot parse the new contract, must
      land together). `/range-batch` consumption is explicitly out of
      scope for this cutover's production-approval — I8 owns that. Gate:
      N=1 production path green end to end against the live stack;
      joint with `strategy_engine`'s Runtime regression fence (this repo
      has no direct Runtime relationship, so nothing here to regress,
      but the joint gate still requires that fence green before this
      checkpoint is considered complete).
- [ ] **I8 (Research's share) — Batch Lifetime Redesign.** Only after
      I7. Change the aggregation pattern so N candidates' evaluations
      are never held resident simultaneously in either process, while
      retaining shared-L0 acquisition — coordinate the exact mechanism
      with `strategy_engine`'s I8 (transport/call-pattern is an
      implementation decision, not fixed by I0). Re-litigate whether
      `/range-batch` as one large request/response is even the right
      shape, per the Master Plan — not just its aggregation timing.
      `RunBatchExperiment`/`_settle_candidate`'s existing per-candidate
      loop needs re-confirmation, not assumed structural change. Gate:
      N=1/2/4/11 benchmark, peak RSS approximately constant in N.

## Spec

- [ ] `openspec archive compact-strategy-evaluation-boundary-v1` only
      after the full Master Plan (I0-I8, joint with `strategy_engine`)
      is complete.
