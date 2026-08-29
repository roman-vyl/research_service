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
- [x] **I2 dependency note.** I3/I4 below cannot start meaningfully
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
- [x] **I4 — Research: Execution Parity (the decisive Research-side
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
      single most important gate in this plan).** Normative requirements:
      `research-historical-execution-parity-v1`. Nothing past this point
      (I6/I7/I8) starts until this is green. Sub-tasks:
  - [x] **I5.A — Proof harness foundation.** `strategy_engine`-side
        proof-only `v2` envelope serializer (mirrors `strategy_
        serialization.py::serialize_strategy_evaluation_execution`'s
        structure for the `v2` shape; not `src/`, not route-wired) and
        the in-process invocation of `EmaPullbackRangeEvaluator._
        evaluate_frame_native` + `build_historical_execution_projection`
        that feeds it. Research-side proof-only script/acceptance test
        that reads the resulting JSON file, decodes it via the real
        `parse_historical_execution_projection`/`validate_projection_
        alignment`/`HistoricalExecutionProjectionIndex.build`, and can
        drive `run_projection_execution_loop`. No production code
        changes on either side.
  - [ ] **I5.B — Lane A reference + new path.** Real `full_available`
        `BTCUSDT.P`/`5m`, canonical always-on spec, resolved once via
        `ResolveBacktestWindow` and shared by both paths. Reference:
        existing legacy `run_unified_execution_loop` (unmodified). New
        path: the I5.A harness → `run_projection_execution_loop` →
        `account_execution_loop` (unmodified).
  - [ ] **I5.C — Lane B profile-sensitive proof.** Independent old-BBB
        trade-lifecycle reference (extends `strategy_engine`'s I2
        verbatim reference to a full lifecycle — entry/lock/drift/exit/
        attribution) vs. the same I5.A harness → new path, on the
        profile-sensitive adversarial spec (I2's scenario shape).
        Includes the mandatory negative-control evidence (locked vs.
        current-profile interpretation diverge) -- current-profile
        evidence sourced proof-only from Engine's native evaluation/the
        old-BBB reference, never from the `.v2` wire or read by the new
        execution path itself.
  - [ ] **I5.D — Semantic diff engine.** Structured comparison over the
        "Zero-diff comparison surface" fields (entry, locked profile,
        initial protection + attribution, signal stream while open,
        exit + attribution, `TradeRecord`, `TradeAccountingResult`,
        provenance) — exact equality throughout except the one carried-
        over Engine `ratio` epsilon (see design.md).
  - [ ] **I5.E — Real full_available acceptance run.** Execute I5.B and
        I5.C against real Market Data Service data (not `FakeMarketData`
        fixtures), matching the precedent set by `strategy_engine`'s
        `scratch/parity_proof.py`. Record results (bar count, diff
        count, wall time) analogous to that precedent's own reporting.
  - [ ] **I5.F — Regression fences / final gate.** Confirm during I5
        work: Strategy Engine `/range`/`/range-batch` unchanged;
        Research's production `/range` consumer
        (`RunSingleInstanceBacktest`) still calls the legacy `.v1`
        contract; no persistence/diagnostics/accounting-formula changes;
        Runtime untouched. Gate: I5.B and I5.C both report zero semantic
        diffs.
- [ ] **I6 — Persistence / Diagnostics Split + Persisted-Artifact
      Regression Proof.** Normative requirements: `research-run-
      artifact-parity-v1` (new capability, this revision) plus the
      already-normative `research-run-artifacts-v1`/`research-
      diagnostics-projection-v1` (amended in I0). Nothing past this
      point (I7/I8) starts until this is green. A practical regression
      proof over the narrow common-facts surface, not a full
      structural-equality/canonicalizer project — see the capability
      spec's "deliberately NOT a complete canonicalizer" note. Sub-tasks:
  - [ ] **I6.A — Frozen-input/reference harness foundation.**
        Proof-only old-BBB input adapter: construct
        `candles_to_ohlcv_dataframe`'s exact DataFrame shape directly
        from the one `ResolveBacktestWindow`-resolved `MarketFrame
        .candles` Research's own pipeline used — bypassing old BBB's
        `execution/data_loader.py::load_candles_once`/`data_engine
        .store.Db` entirely for this proof. No new MDS interface, no
        change to old BBB's production data-loading architecture.
  - [ ] **I6.B — Common-facts field mapping.** Codify the field-mapping
        table in design.md's "I6 implementation strategy" section
        (`entry_idx`↔`entry_bar_index`, `exit_instance_id`↔
        `exit_rule_id`, etc.) — scoped only to the closed common-facts
        list in `research-run-artifact-parity-v1`, not a full field
        union of both systems.
  - [ ] **I6.C — New-side provenance/storage field verification.**
        Implement the internal-correctness checks from "New-side
        provenance/storage fields are verified, not cross-compared":
        `manifest.json` file hashes match persisted bytes,
        `market_data_hash`/market identity match the frozen dataset,
        `instance_id`/`config_hash` match `derive_strategy_instance_id`.
        No cross-system comparison, no canonicalizer, no
        nondeterministic-metadata allowlist machinery.
  - [ ] **I6.D — Persistence/diagnostics split.** `strategy_evaluation
        .json` becomes the canonical `HistoricalExecutionProjection`;
        `result.json` references it by identity instead of
        re-embedding; `raw=body` retention removed (already done in
        I3, confirm still true); diagnostics become the separate,
        explicitly-generated artifact designed in "Diagnostics become
        explicit and optional"/"Diagnostic-evaluation generation" in
        design.md. Preserve content per "No silent loss of common-
        surface content through the diagnostics split": `trades.json`,
        `metrics.json`, `execution_events.json`, `result.json`,
        manifest, lightweight run/batch summaries keep their current
        informational content — deduplication/relocation is not
        information loss.
  - [ ] **I6.E — Common-facts regression proof.** Two checks: (1)
        cross-system, old-BBB reference (via I6.A's adapter) vs. the
        persisted new-side Run, on the common-facts surface only,
        trade for trade; (2) persistence read-back, the in-memory
        `SingleInstanceBacktestResult` vs. the same facts read back
        from `trades.json`/`metrics.json`/`execution_events.json`
        after persisting. Includes the same profile-sensitive
        adversarial scenario I5/I2 already established, at the
        persisted-artifact level this time.
  - [ ] **I6.F — Regression / completeness gate.** Confirm: no consumer
        (BFF routes, diagnostics projection) regresses; run artifact
        bundle still contains everything I5 verified was needed;
        `research-run-artifacts-v1`/`research-diagnostics-projection-v1`
        requirements hold; no common-facts field silently dropped by
        the diagnostics split. Gate: I6.E's both checks report zero
        diffs on both the canonical always-on Run and the profile-
        sensitive adversarial Run.
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
