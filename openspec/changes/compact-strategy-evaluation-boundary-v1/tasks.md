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
- [x] **I5 — N=1 End-to-End Proof (joint with `strategy_engine`, the
      single most important gate in this plan).** Normative requirements:
      `research-historical-execution-parity-v1`. Nothing past this point
      (I6/I7/I8) starts until this is green. **I5_GATE_PASSED.** Sub-tasks:
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
  - [x] **I5.B — Lane A reference + new path.** Real `full_available`
        `BTCUSDT.P`/`5m` (676,246 bars), genuinely profile-insensitive
        spec (`scripts/fixtures/lane_a_always_on_ema_pullback_spec.json`
        -- all exit rules under `always_on`, empty per-profile exit
        lists, so legacy Research's current-profile-only reference is
        valid evidence for it -- real entry/setup/HTF-context machinery
        kept), resolved once and shared by both paths. Reference:
        existing legacy `run_unified_execution_loop` (unmodified). New
        path: the I5.A harness → `run_projection_execution_loop` →
        `account_execution_loop` (unmodified). Result: 8317 vs. 8317
        closed trades, **zero diffs** on Lane A's full comparison surface
        per `research-historical-execution-parity-v1`'s corrected
        per-lane scoping -- every `TradeRecord` field both sides produce
        (entry/exit bar/time/price, `quantity`, `entry_notional`/`exit_
        notional`, `gross_pnl`/`entry_fee`/`exit_fee`/`fees_paid`/`net_
        pnl`, `gross_return_pct`/`net_return_pct`, `equity_before`/
        `equity_after`, `hold_bars`/`hold_ms`, `exit_candidate_type`/
        `exit_reason`/`exit_layer`), every `TradePathMetrics` field
        (`path`), and every `TradeAccountingResult` field (`initial_
        equity`, `realised_trade_count`, `open_position_count`, `gross_
        pnl`, `fees_paid`, `net_pnl`, `final_equity`) -- all identical to
        the last decimal digit. Attribution fields (`exit_rule_id`/
        `exit_component_id`/`exit_kind`) differ (legacy always `None`,
        structurally -- the legacy reference never populated them, the
        pre-existing gap I4 restored on the new path) -- reported
        informationally, explicitly excluded from Lane A's pass/fail per
        the corrected spec (`exit_layer` IS compared normally and
        matches).

        **Corrective note**: an earlier attempt used the shared
        profile-sensitive spec for Lane A too and found 6934 vs. 6928
        trades. Localized precisely (position index 1366, entry bar
        133504): legacy exited via the flattened current-bar-profile
        `signal_exit` field one bar before the new path's
        locked-profile-correct stop-loss exit -- i.e., the exact
        locked-profile-vs-current-profile defect this migration exists
        to fix, exposed by using a reference mechanism
        (`research-historical-execution-parity-v1` already documents as
        "valid only for an always-on-only spec") against a spec it
        cannot validate. Not a defect in the new path; fixed by scoping
        Lane A to the genuinely profile-insensitive fixture above and
        moving all profile-sensitive exit configuration to I5.C.
  - [x] **I5.C — Lane B profile-sensitive proof.** Independent old-BBB
        trade-lifecycle reference (`scripts/_old_bbb_lifecycle_
        reference.py` -- verbatim OHLC-gap/fill mechanics from
        `_bbb_new_gen@cddc836`, extended to a full entry/lock/drift/
        exit/accounting lifecycle in `scripts/lane_b_parity_proof.py`)
        vs. the same I5.A-shaped new path, on
        `scripts/fixtures/lane_b_profile_sensitive_ema_pullback_spec
        .json` (three distinct profile SL/TP/signal-exit
        configurations, same real entry/setup/HTF machinery as Lane A).
        Real MDS window (60,001 bars): 556 vs. 556 closed trades, zero
        diffs on Lane B's own comparison surface (side, entry/exit
        bar/price, `hold_bars`, `gross_pnl`/`net_pnl` -- asserted
        comparable only under the harness's zero-fee `AccountingPolicy`,
        the independent simulator has no fee model --, `exit_candidate_
        type`, `locked_exit_profile`, and exit attribution
        `exit_rule_id`/`exit_component_id`/`exit_kind`/`exit_layer`,
        MANDATORY exact on this lane). `TradePathMetrics`/notional/fee/
        equity fields are explicitly NOT part of Lane B's surface -- the
        independent reference does not compute them; those exact fields
        are proven, on real full-scale data, by Lane A instead
        (`research-historical-execution-parity-v1`'s corrected per-lane
        scoping). Mandatory negative control run against the full
        `full_available` dataset
        (676,246 bars, 6928 real trades from the independent simulator)
        found 4 real trades where the locked-profile result provably
        differs from what a deliberately-wrong current-bar-profile
        lookup would have produced (different exit bar and/or rule_id)
        -- e.g. entry bar 203671, locked `neutral`: correct
        `(203820, sig_neutral)` vs. wrong-current-profile
        `(203729, sig_aligned)`.
  - [x] **I5.D — Semantic diff engine.** `scripts/lane_a_parity_proof.py`/
        `scripts/lane_b_parity_proof.py` implement the structured
        comparison over the "Zero-diff comparison surface" fields
        (entry, locked profile, initial protection + attribution,
        signal stream while open, exit + attribution, `TradeRecord`,
        `TradeAccountingResult`, provenance) -- exact equality
        throughout, no new tolerance introduced.
  - [x] **I5.E — Real full_available acceptance run.** Executed against
        the real local Market Data Service (not `FakeMarketData`),
        matching the precedent set by `strategy_engine`'s `scratch/
        parity_proof.py`. Lane A: 676,246 bars, 8317 trades, 0 diffs.
        Lane B: 60,001 bars (real MDS window) for the full comparison,
        plus a 676,246-bar real-data run of the independent simulator
        alone for the negative-control search (6928 trades, 4 genuine
        divergences found). Wall time: Lane A's legacy reference stage
        alone was originally ~4.4h-extrapolated (O(bar_count^2) in
        `execution/entry.py::_entry_series`, fixed separately --
        `fd1975a`, 2876x speedup at 50k bars, confirmed
        semantics-preserving); after the fix, the full Lane A run
        (fetch + both execution loops + accounting + diff) completes in
        well under a minute.
  - [x] **I5.F — Regression fences / final gate.** Confirmed: Strategy
        Engine `/range`/`/range-batch` unchanged (no commits touched
        `adapters/http/strategy_routes.py`); Research's production
        `/range` consumer (`RunSingleInstanceBacktest`/`evaluate_range`)
        untouched -- Lane A's legacy reference is built proof-only,
        in-process, from Engine's `evaluate()`, never through the live
        route or that client method; no persistence/diagnostics changes;
        no accounting-formula changes (`accounting/service.py`
        untouched -- only `execution/entry.py`'s validation hot path was
        fixed, semantics/ordering/fills unchanged, confirmed by the full
        pre-existing test suite passing unmodified); Runtime untouched.
        Gate: I5.B and I5.C both report zero semantic diffs.
        **I5_GATE_PASSED.**
- [x] **I6 — Persistence / Diagnostics Split + Persisted-Artifact
      Regression Proof.** Normative requirements: `research-run-
      artifact-parity-v1` (new capability, this revision) plus the
      already-normative `research-run-artifacts-v1`/`research-
      diagnostics-projection-v1` (amended in I0). Nothing past this
      point (I7/I8) starts until this is green. A practical regression
      proof over the narrow common-facts surface, not a full
      structural-equality/canonicalizer project — see the capability
      spec's "deliberately NOT a complete canonicalizer" note.
      **I6_GATE_PASSED.** Sub-tasks:
  - [x] **I6.A — Frozen-input/reference harness foundation.**
        `scripts/old_bbb_candle_adapter.py::candles_to_ohlcv_records` --
        proof-only old-BBB input adapter: constructs
        `candles_to_ohlcv_dataframe`'s exact row-record shape directly
        from the one `ResolveBacktestWindow`-resolved `MarketFrame
        .candles` Research's own pipeline used — bypassing old BBB's
        `execution/data_loader.py::load_candles_once`/`data_engine
        .store.Db` entirely for this proof. No new MDS interface, no
        change to old BBB's production data-loading architecture.
  - [x] **I6.B — Common-facts field mapping.** The field-mapping table
        in design.md's "I6 implementation strategy" section
        (`entry_idx`↔`entry_bar_index`, `exit_instance_id`↔
        `exit_rule_id`, etc.) confirmed still accurate and used directly
        by `scripts/persist_and_verify_run.py`'s cross-system diff —
        scoped only to the closed common-facts list in `research-run-
        artifact-parity-v1`, not a full field union of both systems.
  - [x] **I6.C — New-side provenance/storage field verification.**
        `scripts/persist_and_verify_run.py`'s manifest-hash check:
        every persisted file's actual sha256/size matches its
        `manifest.json` record; `market_data_hash` in the bundle matches
        the one frozen `MarketFrame` both I6.E checks were computed
        from. No cross-system comparison, no canonicalizer, no
        nondeterministic-metadata allowlist machinery. Verified PASS on
        both real runs below.
  - [x] **I6.D — Persistence/diagnostics split (proof-only).**
        `scripts/persist_and_verify_run.py::_write_bundle` builds the
        target I6.D shape — `strategy_evaluation.json` IS the real
        `HistoricalExecutionProjection` v2 envelope (not the legacy
        dense shape); `result.json` references it (and `trades.json`/
        `execution_events.json`) by sha256 identity, never re-embedding
        — as a SEPARATE, parallel proof-only bundle, exactly like I4/I5's
        `execution/projection_loop.py`/`run_projection_execution_loop`
        sit parallel to the unmodified legacy path. Production
        `PersistSingleInstanceBacktest`/`SingleInstanceBacktestResult`
        are NOT changed — they still persist the legacy shape.
        Production actually cutting persistence over to this shape is
        I7's job (coordinated with the route cutover), not I6's;
        confirmed explicitly with the user before implementing. Content
        preserved per "No silent loss of common-surface content through
        the diagnostics split": every `trades.json`/`execution_events
        .json`/`metrics.json` field the proof-only bundle carries is
        the same real `TradeRecord`/`ExecutionEvent`/accounting-summary
        content the existing production bundle already carries.
  - [x] **I6.E — Common-facts regression proof.** Two checks, both PASS
        on real MDS data: (1) cross-system — the independent old-BBB-
        grounded reference (verbatim mechanics, same methodology as I5
        Lane B) vs. the persisted-then-read-back new-side Run, on the
        common-facts surface (side, entry/exit bar/price, hold_bars,
        gross_pnl, exit_candidate_type); (2) persistence read-back — the
        in-memory `TradeRecord`/`ExecutionEvent` objects vs. the same
        objects reconstructed (`pydantic.model_validate`) from the
        persisted `trades.json`/`execution_events.json` after a full
        write+read round trip. Run on both the canonical always-on
        scenario (real `full_available` BTCUSDT.P/5m, 676,246 bars,
        8317 trades) and the profile-sensitive adversarial scenario
        (real 60,001-bar MDS window, 556 trades, same fixture I5 Lane B
        used) — **zero diffs on both, both checks, both scenarios.**
  - [x] **I6.F — Regression / completeness gate.** Confirmed: no
        consumer (`read_artifacts.py`/`run_views.py`/BFF routes/
        diagnostics projection) touched or regresses — `git diff
        --stat` against the pre-I6 SHA on `src`/`tests` is empty; run
        artifact bundle still contains everything I5 verified was
        needed (nothing in production removed); `research-run-
        artifacts-v1`/`research-diagnostics-projection-v1` requirements
        hold (unaffected); no common-facts field silently dropped by
        the diagnostics split (I6.E(2)'s zero read-back diffs prove
        this directly). Gate: I6.E's both checks report zero
        diffs on both the canonical always-on Run and the profile-
        sensitive adversarial Run.
- [x] **I7 (Research's share) — Coordinated Cutover, single-instance
      only.** Normative requirements: new `research-production-cutover-v1`
      (this revision) plus amendments to `research-unified-execution-
      loop-v1`/`research-run-artifacts-v1`/`research-diagnostics-
      projection-v1`. Switch Research's *historical* `/range` consumption
      to the I3-I6 path, coordinated with `strategy_engine`'s same-
      checkpoint work (old Research cannot parse the new contract, must
      land together). `/range-batch` consumption is explicitly out of
      scope for this cutover's production-approval — I8 owns that.
      **I7_GATE_PASSED.** Sub-tasks:
  - [x] **I7.A — EXPLORE.** Read production wiring
        (`strategy_routes.py`, `evaluate_range.py`, `ports.py` both
        repos, `run_backtest.py`, `run_batch.py`, `read_artifacts.py`,
        `diagnostics/projection.py`, `run_views.py`). Findings: (1)
        `MaterializeBacktestOutcome`/`PersistSingleInstanceBacktest`
        shared with batch — must not be mutated in place; (2)
        `diagnostics/projection.py` reads legacy dense fields
        (`component_evidence`/`raw`/`entries`/`exit_policy`) that won't
        exist after cutover, and no diagnostic-artifact generator exists
        yet despite `research-diagnostics-projection-v1` already
        requiring one; (3) `RunArtifactManifest` lacks market identity,
        so `read_artifacts.py::_summary()` needs a resolved shape for
        `result.json`.
  - [x] **I7.B — Spec authored.** `research-production-cutover-v1`
        capability written: scope boundary (batch/Runtime untouched),
        final `/range` v2 contract, Research v2 consumer wiring, shared-
        infrastructure-stays-batch-shaped resolution, persistence
        cutover shape (identity subset + reference-by-identity), hard
        diagnostics-generator prerequisite, fail-closed compatibility,
        live E2E regression gate, coordinated rollback.
  - [x] **I7.C — Companion capability amendments.** MODIFIED/ADDED
        requirements added to `research-unified-execution-loop-v1`
        (single-instance execution path wiring, batch explicitly
        unaffected), `research-run-artifacts-v1` (production
        `result.json`/`strategy_evaluation.json` shape cutover),
        `research-diagnostics-projection-v1` (generator existence +
        `projection.py` migration made a hard prerequisite).
  - [x] **I7.D — VERIFY.** Re-checked against code; found and fixed one
        real blocker: `EvaluateStrategyRangeBatch` calls the same
        `EvaluateStrategyRange.execute()` `/range` was going to be
        repurposed to return `.v2` from — would have silently switched
        `/range-batch` to `.v2` too. Corrected: `/range` gets a new,
        separate application-service method; `execute()`/
        `evaluate_execution()` stay unmodified and remain the HTTP path
        `/range-batch` reaches (not reduced to private/unrouted code).
  - [x] **I7.E — strategy_engine companion delta.** `/range` v2-only
        cutover via a new method (not `execute()`), `/range-batch`
        explicitly unchanged and still HTTP-reachable to the sparse
        `.v1` path, new additive `StrategyEvaluator` Protocol method,
        live routes explicitly unaffected, coordinated-rollback note
        — mirrored in `strategy_engine`'s own OpenSpec
        (`strategy-research-execution-contract-v1`).
  - [x] **I7.F — Real cutover implementation.** `EmaPullbackRangeEvaluator
        .evaluate_execution_projection()` + `EvaluateStrategyRange
        .execute_projection()` wired to `/range` (Engine); `execute()`/
        `evaluate_execution()` unmodified, still serving `/range-batch`.
        Research: `evaluate_range_projection`/`evaluate_range_diagnostics`
        added to `StrategyEnginePort`/`HttpStrategyEngineClient`;
        `MaterializeBacktestProjectionOutcome`/`PersistSingleInstanceRun`
        (new, single-instance-only) wired into `RunSingleInstanceBacktest`;
        `MaterializeBacktestOutcome`/`PersistSingleInstanceBacktest`
        untouched, batch-only. `ReadResearchRuns`/`run_views` cut over in
        place to the canonical I6.D shape — one reader, no legacy
        fallback, no `contract_version` discrimination. Diagnostic-
        artifact generator (`GenerateRunDiagnostics`,
        `POST /runs/{run_id}/diagnostics/generate`) built;
        `diagnostics/projection.py` migrated off the removed dense fields
        onto the generated artifact + `entry_opportunities` (`signal_
        entry`/`stop_ready`/`portfolio_entry` collapse to one series,
        matching the Master Plan's `stop_ready` invariant). Test suites
        updated in both repos; `ruff`/`mypy` green (`mypy src`, the
        project's own configured gate in both repos); batch's own
        `FakeStrategyEngine`/legacy-path tests untouched and still pass.
  - [x] **I7.G — Live N=1 E2E gate.** Real, freshly-started Strategy
        Engine + Research Service processes (local, not the shared
        `bbb_stack` docker deployment) against the real, already-running
        Market Data Service: confirmed `/range` serves `.v2` from the
        live Engine; a real `POST /api/research/backtests` request
        completed end to end (real HTTP `/range` call, real execution,
        real accounting, 3 closed trades); the persisted bundle is in
        the canonical shape (`result.json` references, not re-embeds);
        `GET /runs`, `/runs/{id}`, `/runs/{id}/trades` all read it back
        correctly through the BFF; `POST /runs/{id}/diagnostics/generate`
        then `GET /runs/{id}/signal-trace` succeeded (404 `diagnostics_
        not_yet_generated` beforehand, as specified).
      Gate: N=1 production path green end to end against a live stack —
      **PASSED (I7.G)**. `openspec validate --strict`/`--all --strict`
      green in both repos; `pytest`/`ruff check`/`mypy src` green in
      both repos; no dual-shape reader, no `contract_version`
      discrimination, no legacy-compatibility path introduced.
- [x] **I8 (Research's share) — Batch Lifetime Redesign.** Only after
      I7. Normative requirements: new `research-batch-lifecycle-v1` (this
      revision) plus a MODIFIED delta on `research-batch-experiments-v1`.
      **I8_GATE_PASSED.** Sub-tasks:
  - [x] **I8.A — EXPLORE.** Read `run_batch.py`/`evaluate_range_batch.py`/
        `materialize_backtest_outcome.py`/`artifacts.py`. Confirmed
        design.md's existing analysis: `RunBatchExperiment`'s
        per-candidate settle loop is already correct; the actual bloat
        is `evaluate_range_batch`'s ONE `/range-batch` response holding
        all N candidates' evaluations resident before that loop starts.
        **New finding, not previously confirmed against a real Engine**:
        probed the real, live `/range-batch` route directly — it returns
        `contract_version: "strategy_evaluation_execution.v1"` with
        sparse `decision_events`, while Research's real
        `_parse_evaluation_result` expects the older dense
        `entries`/`exit_policy`/`component_evidence` shape. Fed a real
        captured response through the real parser: raised
        `UpstreamServiceError`. **`RunBatchExperiment` is not currently
        functional against the live Engine stack** — existing batch
        tests only exercise an in-process `FakeStrategyEngine`, so this
        was never previously exposed.
  - [x] **I8.B — Spec authored.** `research-batch-lifecycle-v1` written:
        scope boundary (single-instance/Runtime untouched), the
        real-wire-incompatibility finding stated as a requirement I8
        must fix (not perpetuate), per-candidate release (constant-RSS
        gate), migration to the canonical
        `MaterializeBacktestProjectionOutcome`/`PersistSingleInstanceRun`
        path (closing the I7-to-I8 batch-artifact-readability gap, then
        deleting the legacy batch-only components), and a two-part
        regression gate (RSS benchmark + real live-Engine batch run).
        `research-batch-experiments-v1`'s "Authoritative per-candidate
        path" requirement amended (MODIFIED) to name the canonical
        components. First draft's acquisition design (N per-candidate
        `/range` calls) was later found blocked — see I8.C.
  - [x] **I8.C — VERIFY.** Re-checked against code; found and fixed one
        real blocker: `/range` has no preloaded-`MarketFrame` transport
        (`EvaluateIndicatorRange._prepare()` always calls
        `self._market_data.load_range(...)` when `request.market_frame
        is None`), so the drafted N-independent-`/range`-calls design
        would cause N separate Engine-side MDS reads, not one shared
        acquisition — violating the Master Plan's own shared-L0
        invariant. Corrected: re-read `EvaluateStrategyRangeBatch
        .execute()` and found it already implements shared-once
        acquisition + sequential in-process per-variant evaluation
        (reusing a supplied `market_frame` via `IndicatorRangeRequest
        ._prepare()`) — its only real problems are calling the old
        `.execute()` (`.v1`) instead of the `.v2` projection path, and
        buffering all N outcomes into one response. New requirement
        "Streamed shared-once acquisition" replaces the blocked one:
        `/range-batch` cut over to a streamed (NDJSON/chunked) `.v2`
        response — one shared Engine-side MDS fetch, sequential
        per-variant evaluation and emission, no N-aggregate held on
        either side. Also clarified: today's two failure-isolation
        levels collapse into one per-candidate boundary in the stream-
        consuming loop — does not violate `research-batch-experiments-
        v1`'s "Failure isolation" requirement (no specific error-level
        taxonomy is normative there).
  - [x] **I8.D — strategy_engine companion note.** Corrected in
        `strategy_engine`'s own `tasks.md`: Engine DOES need I8 work
        under the corrected design — `/range-batch`'s response cut over
        to the streamed `.v2` shape (a new serializer + route change),
        not "no route change" as the first draft claimed.
  - [x] **I8.E — Element-shape/boundary/ordering fixes (pre-APPLY
        review).** Three deterministic corrections applied to both
        OpenSpecs before implementation: (1) every stream element
        normatively `{variant_id, result, error}`, `variant_id`
        mandatory, exactly one of `result`/`error` non-null, `result`
        the unwrapped canonical `.v2` envelope; (2) batch evaluation
        goes through `EvaluateStrategyRange.execute_projection()`, never
        an evaluator's `evaluate_execution_projection()` directly; (3)
        shared `MarketFrame` acquisition/validation completes before any
        streaming begins, so acquisition failure is a clean whole-
        request HTTP error with zero elements streamed.
  - [x] **I8.F — Real implementation.** Research: `StrategyEnginePort
        .evaluate_range_batch`/`HttpStrategyEngineClient` rewritten to a
        streaming generator (`httpx` `.stream()`, NDJSON line-by-line
        decode via the existing `parse_historical_execution_projection`,
        strict request-order validation, fail-closed on malformed/
        out-of-order/duplicate/missing elements).
        `StrategyEvaluationBatchVariantOutcome.result` retyped to
        `HistoricalExecutionProjectionDTO`. `RunBatchExperiment` rewritten:
        shared window/frame acquisition unchanged; per-candidate settle
        loop now consumes the streaming generator directly, materializing
        via `MaterializeBacktestProjectionOutcome`/persisting via
        `PersistSingleInstanceRun` (the same canonical single-instance
        path) and releasing each candidate before the next is produced;
        results correlated by `variant_id` into a `candidate_id`-keyed
        dict so the final summary list is restored to request order
        regardless of stream arrival order (only the small summaries are
        held, never the heavy projections). Legacy batch-only
        `MaterializeBacktestOutcome`/`PersistSingleInstanceBacktest`
        deleted, along with the now-orphaned `SingleInstanceBacktestResult`/
        `SingleInstanceBacktestOutcome` types; `application/backtests/
        artifacts.py` trimmed to the shared manifest models only.
        Fixed a latent bug surfaced by the new failure path:
        `RunBatchExperiment`'s per-candidate exception handler used
        `str(exc)`, which is empty for dataclass-based
        `ResearchServiceError` subclasses constructed with keyword-only
        args (`BaseException.args` stays empty) — now prefers `.message`.
        Test suites updated (`test_single_instance_backtest.py`'s shared
        `FakeStrategyEngine` gained a streaming, projection-based
        `evaluate_range_batch`; `test_batch_experiments.py` rewritten
        throughout; the now-dead `test_materialize_backtest_outcome.py`
        deleted). `pytest`/`ruff check`/`mypy src` green in both repos.
  - [x] **I8.G — Live gates.** (1) Real batch run: fresh local Engine
        (current I8 code) + real Market Data Service + in-process
        `RunBatchExperiment` wired to the real `HttpStrategyEngineClient`
        — N=2 candidates, both completed, independently persisted in
        canonical shape, immediately readable through `ReadResearchRuns`/
        `GET /runs/{run_id}` (closing the I7-to-I8 batch-artifact-
        readability gap); single-instance `POST /backtests` re-confirmed
        unaffected on the same stack. (2) N=1/2/4/11 constant-RSS
        benchmark, Engine-process side: same live Engine process, peak
        RSS sampled via `ps` during each run — 100928 / 101008 / 101056 /
        101184 KB (1.00x/1.00x/1.00x/1.00x of N=1, +0.25% total from N=1
        to N=11) — approximately constant, not linear. (3) N=1/2/4/11
        constant-RSS benchmark, Research-process side (closing the gap
        that I8.G originally measured Engine only): each N run in its
        own isolated subprocess (`resource.getrusage(RUSAGE_SELF)
        .ru_maxrss` is a per-process lifetime high-water mark, not
        resettable within one process, so isolating per-N in separate
        subprocesses is required for a clean measurement) against a
        fresh live Engine — 52384 / 52432 / 52576 / 52576 KB
        (1.00x/1.00x/1.00x/1.00x of N=1, +0.37% total from N=1 to N=11)
        — approximately constant, confirming `RunBatchExperiment` itself
        (not just Engine) never holds N candidates' state simultaneously.
      Gate: N=1/2/4/11 benchmark, peak RSS approximately constant in N,
      both Engine-process and Research-process — **PASSED (I8.G.2,
      I8.G.3)**; real batch run against a live Engine instance, N>1,
      succeeds end to end — **PASSED (I8.G.1)**. `openspec validate
      --strict`/`--all --strict` green; `pytest`/`ruff check`/
      `mypy src` green in both repos.

## Spec

- [ ] `openspec archive compact-strategy-evaluation-boundary-v1` only
      after the full Master Plan (I0-I8, joint with `strategy_engine`)
      is complete.
