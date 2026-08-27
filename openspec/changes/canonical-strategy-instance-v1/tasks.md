## 1. Cross-repo coordination prerequisites

- [x] 1.1 Resolved: `strategy_engine` completed
      `strategy-evaluation-canonical-boundary-v1` (commits `4028242`,
      `d61cfef`, `83e2f18`). Engine's evaluation boundary now accepts
      exactly `{strategy_id, raw_spec}` and rejects `strategy_version`,
      caller-supplied `instance_id`, and `compatibility_profile` outright
      (`extra="forbid"`) rather than merely tolerating their absence. See
      §9 for the Research-side sync this enables.
- [x] 1.2 Confirmed: `strategy_runtime`'s `derive_strategy_instance_id` is
      unchanged and remains the normative derivation; no dependency
      concern.
- [x] 1.3 Resolved: Engine's Composer Catalog API response field is now
      named `strategy_id`, not `family` (same Engine change as 1.1). See
      §9.

## 2. Research Service — canonical strategy-instance domain types

- [x] 2.1 Add a `StrategyInstanceIdentity` domain type
      (`strategy_id`, `ticker`, `base_timeframe`, `raw_spec`) with no
      `instance_id`, `family`, `variant`, or `strategy_version` fields.
- [x] 2.2 Add a `DeployableStrategyInstance` domain type: the identity
      fields plus a sibling `enabled: bool`, matching Runtime's flat
      deployment-file shape exactly (no nested identity/deployment
      structure).
- [x] 2.3 Port `derive_strategy_instance_id`'s algorithm (or call an
      equivalent shared implementation) so Research computes the same
      `instance_id` Runtime would for the same identity fields —
      `enabled` MUST NOT be an input to this derivation.
- [x] 2.4 Add validation that rejects an instance carrying an explicit
      `instance_id`, `family`, `variant`, or `strategy_version` field,
      per `canonical-strategy-instance-v1`; confirm `enabled=false`
      passes validation identically to `enabled=true`.
- [x] 2.5 Set `extra="forbid"` (or equivalent) on `StrategyInstanceIdentity`
      and `DeployableStrategyInstance` so an unrecognized/legacy field
      causes rejection instead of being silently dropped (per design.md
      Decision 10).

## 3. Research Service — backtest API

- [x] 3.1 Change `SingleInstanceBacktestRequest` to embed a
      `StrategyInstanceIdentity` (not `DeployableStrategyInstance` —
      backtest evaluation never receives `enabled`) plus `range_policy`,
      `execution`, `accounting`, `managed_policy_enabled` — remove
      `run_id` as an input field.
- [x] 3.2 Set `extra="forbid"` (or equivalent) on
      `SingleInstanceBacktestRequest` and on `StrategyEvaluationRequest`
      (currently only `frozen=True`, neither sets it — confirmed in
      `application/backtests/contracts.py:20` and
      `domain/contracts.py:89`) so that `run_id`, `instance_id`, `family`,
      `variant`, `strategy_version`, and `enabled` are rejected on
      `/backtests`, not silently ignored (per design.md Decision 10).
- [x] 3.3 Model the range portion of the request as a discriminated
      shape keyed by `range_policy`: `explicit_range` requires a real
      `{from_ms, to_ms}` pair with existing alignment/ordering
      validation; `full_available` carries no range fields at all — not
      an optional-and-unvalidated pair (per design.md Decision 11). The
      identity subset's `ticker`/`base_timeframe` are unaffected by this
      and remain always-present.
- [x] 3.4 Generate `run_id` inside the backtest orchestration use case on
      every accepted request (no idempotency/dedup lookup); return it in
      `BacktestRunResponse` as today.
- [x] 3.5 Update the identity-consistency check in
      `application/backtests/artifacts.py` (`manifest.run_id != run_id`
      etc.) to reflect server-generated `run_id` and derived
      `instance_id`.
- [x] 3.6 Fix `api/routers/research.py`'s `/backtests` route: the
      `except FileExistsError: raise RunAlreadyExists(payload.run_id)`
      branch (line 107 today) references a field being removed from
      `payload`. Reference the generated identity instead (e.g.
      `result.run_id`), and reconsider whether this branch should still
      surface as a caller-facing `409` at all now that collision is an
      internal Research concern, not caller-triggerable duplicate
      semantics (per design.md Decision 12).
- [x] 3.7 Remove the `strategy_version` field from
      `StrategyEvaluationRequest`'s caller-facing surface; keep whatever
      value Research sends to Engine internally out of the
      Research-facing request contract (per design.md Decision 5).

## 4. Research Service — config validate/serialize/save

- [x] 4.1 Change server-side `StrategyConfigDraft.instances` from
      `list[dict[str, Any]]` to `list[DeployableStrategyInstance]`
      (`enabled` included, since Composer edits/persists it here).
- [x] 4.2 Update `config_validation.py` to validate each instance as a
      deployable strategy instance and to reject legacy identity fields
      per `research-config-validation-v1`'s new requirement.
- [x] 4.3 Add an application-layer command builder/projector that
      extracts the `StrategyInstanceIdentity` from one stored
      `DeployableStrategyInstance` (dropping `enabled`) and combines it
      with Research-owned evaluation concerns (range policy,
      execution/accounting policy, managed-policy toggle) to produce a
      `SingleInstanceBacktestRequest` — a projection of the one strategy
      representation into a narrower request, not a conversion between
      two different strategy representations. This is the piece that
      closes the previously-flagged config→backtest gap.
- [x] 4.4 Rename `family` to `strategy_id` in `config_validation.py` and
      the `family`-typed query param on `GET /configs/state` /
      `PUT /configs/selected` in `api/routers/research.py`. (The
      `/component-catalog` route's `family` param is handled separately
      in §5 — it's governed by a different capability,
      `research-component-catalog-v1`.)
- [x] 4.5 Change persisted path construction in
      `adapters/config/filesystem.py` from
      `<configs_root>/<family>/<experiment_id>.json` to
      `<configs_root>/<strategy_id>/<experiment_id>.json`; update the
      per-root selection-file logic the same way.
- [ ] 4.6 Decide and document a migration path for existing saved configs
      under the old `<family>/` layout (flagged as a deployment/cutover
      concern in design.md — a one-time rename since `family` values and
      `strategy_id` values are identical today per the audit).
- [x] 4.7 Enforce in `ValidateStrategyConfig.execute()` that every
      `draft.instances[i].strategy_id` equals `draft.strategy_id` — one
      experiment/config explores one strategy type. Fail closed with a
      `ValidationErrorItem(path=f"instances[{i}].strategy_id", ...)` per
      offending instance, before any Strategy Engine delegation (per
      `research-config-validation-v1`'s new "One strategy type per
      experiment/config" requirement). Add tests: single/multiple
      matching instances accepted; single mismatching instance rejected;
      mismatch among multiple instances rejected with the correct
      offending index.

## 5. Research Service — component catalog

- [x] 5.1 Rename the `family` query param to `strategy_id` on
      `GET /component-catalog` in `api/routers/research.py:47-49`.
- [x] 5.2 Rename `GetComponentCatalog.execute(family=...)` to
      `execute(strategy_id=...)` in
      `application/research/component_catalog.py`, including the
      unsupported-value rejection message and the local cache key.
- [x] 5.3 Superseded by §9: Engine's own response field is now
      `strategy_id`, not `family` — `ComponentCatalog.family` renamed to
      `ComponentCatalog.strategy_id` and `component_catalog.py`'s
      comparison updated accordingly (`catalog.strategy_id != strategy_id`).
- [x] 5.4 Add tests for `strategy_id`-based catalog requests and for
      unsupported-`strategy_id` rejection (HTTP 400, no upstream call),
      per `research-component-catalog-v1`'s delta spec.

## 6. Research Service — batch experiments

- [x] 6.1 Remove the `run_id`-uniqueness half of
      `BatchExperimentRequest.validate_unique_identity`
      (`application/experiments/contracts.py:31,34-35`); keep only
      `candidate_id`-uniqueness.
- [x] 6.2 Update `RunBatchExperiment._run_candidate`
      (`application/experiments/run_batch.py:41-76`): the success path
      keeps reporting the generated `result.run_id`; the failure path
      (currently `run_id=request.run_id` at line 70) SHALL NOT reference
      a candidate `run_id` that was never generated — omit `run_id` from
      a failed `BatchCandidateResult` instead.
- [x] 6.3 Confirm `BatchCandidateResult.run_id` becomes optional
      (present only on `status="completed"`), and that all correlation
      between a request candidate and its result — in code and in any
      client-facing summary — uses `candidate_id`.
- [x] 6.4 Confirm each `BatchCandidateRequest.backtest` still wraps
      exactly one `StrategyInstanceIdentity` (the same shape the
      standalone `/backtests` endpoint accepts) — batch execution
      introduces no second strategy-instance shape.
- [x] 6.5 Add tests: duplicate `candidate_id` rejected pre-execution;
      duplicate strategy/range parameters across candidates (no longer
      duplicate `run_id`) are explicitly allowed; a failed candidate's
      result has no `run_id`; a successful candidate's result has a
      generated `run_id`; batch summary correlation is verifiable via
      `candidate_id` alone.

## 7. Tests and gates (this repo)

- [x] 7.1 Add/replace backend tests for: identity-subset validation
      rejection cases, `enabled` toggle not affecting `instance_id` or
      validation outcome, extra/legacy fields rejected (not ignored) on
      `/backtests`, server-generated `run_id` (including that a
      caller-supplied `run_id` is rejected), two identical requests
      producing two distinct runs, `full_available` request with no
      range fields, `explicit_range` request still requiring a real
      range, config save/validate/serialize round-trip under the new
      `strategy_id`-keyed path, and the command-builder projection from
      a stored instance to a backtest request.
- [x] 7.2 Run full `research_service` test suite, including the new/
      updated batch-experiments and component-catalog tests from §5 and
      §6.
- [x] 7.3 `openspec validate canonical-strategy-instance-v1 --strict`
      passes before implementation review.

## 8. Dependent repos (tracked here, implemented in their own changes)

- [ ] 8.1 `research_frontend`: rebuild Composer's
      `StrategyConfigDraft`/`StrategyInstanceDraft` types (including an
      editable `enabled` field per instance) and `runBacktest()` request
      construction against this contract; remove `variant`/`family`/
      editable `instance_id` from Composer UI; own change, own OpenSpec
      tree (or equivalent), not authored here.
- [x] 8.2 Resolved: `strategy_engine` completed
      `strategy-evaluation-canonical-boundary-v1` — see §9.
- [ ] 8.3 `strategy_runtime`: no change required; its existing
      `derive_strategy_instance_id` and deployment file shape are already
      the reference implementation this change points to.

## 9. Research ↔ Strategy Engine boundary sync (single + managed + authoring + catalog)

Corrective slice, added once `strategy_engine` completed
`strategy-evaluation-canonical-boundary-v1` (`4028242`/`d61cfef`/`83e2f18`)
and unblocked tasks 1.1/1.3/8.2 above. Scope: bring the single-backtest,
managed-replay, authoring-validation, and composer-catalog wire calls to
Engine in line with its now-final contract. Batch's `RunBatchExperiment`
architecture, `variant_id`/`candidate_id`, and shared-L0 acquisition are
explicitly out of scope — batch already reuses `RunSingleInstanceBacktest`
unchanged and needed no structural change here.

- [x] 9.1 `StrategyEvaluationRequest`/`ManagedReplayRequest`
      (`domain/contracts.py`): drop `strategy_version` and
      `compatibility_profile` fields entirely (no longer sent to Engine,
      nothing else read them). Drop `instance_id` from
      `ManagedReplayRequest` (unused once off the wire — managed-replay's
      response carries no instance identity). Keep `instance_id` on
      `StrategyEvaluationRequest` as Research-owned provenance carried
      into the client, not as a wire field.
- [x] 9.2 `HttpStrategyEngineClient.evaluate_range`/`evaluate_managed_replay`
      (`adapters/http/strategy_engine_client.py`): send exactly
      `{strategy_id, raw_spec}` as `strategy` on both wire calls. Stamp
      `StrategyEvaluationResult.instance_id` from `request.instance_id`
      (Research's own already-derived identity) instead of parsing
      `body.get("instance_id")`, since Engine no longer echoes it.
- [x] 9.3 `StrategyEvaluationResult` (`domain/contracts.py`): drop
      `strategy_version` (Engine no longer echoes it); keep `instance_id`
      as described in 9.2. `evaluation.instance_id` remains the identity
      the whole execution/accounting chain
      (`execution/entry.py`/`loop.py`/`static_exits.py`/`protection.py`,
      `accounting/service.py`) relies on — unaffected by this change since
      it is stamped from Research's own derivation, never Engine's.
- [x] 9.4 `run_backtest.py`: remove the now-dead `_ENGINE_STRATEGY_VERSION`/
      `_ENGINE_COMPATIBILITY_PROFILE` constants and their use at both
      `StrategyEvaluationRequest(...)` and `ManagedReplayRequest(...)`
      call sites.
- [x] 9.5 `RunSummary` (`application/backtests/run_views.py`) and its
      `_summary()` builder (`application/backtests/read_artifacts.py`):
      drop `strategy_version` — it existed on this Research-facing
      contract solely as a pass-through of Engine's now-retired echo, not
      as an independent Research concept.
- [x] 9.6 `ComponentCatalog` (`api/contracts/catalog.py`): rename
      `family` to `strategy_id`, matching Engine's now-final
      `/composer-catalog` response field. Update
      `GetComponentCatalog.execute()`'s (`application/research/
      component_catalog.py`) comparison and drop the now-obsolete
      "Engine still calls it family" comment.
- [x] 9.7 Tests: exact-wire-key-set assertions for `/range` and
      `/managed-replay` requests (`{strategy_id, raw_spec}` only, no
      `strategy_version`/`instance_id`/`compatibility_profile`); a
      regression test proving a legacy `family`-shaped catalog response is
      rejected, not silently accepted; existing managed-policy-events and
      persistence/manifest/`instance_id` regression coverage re-verified
      green, not re-authored (`test_single_instance_backtest.py`,
      `test_managed_policy_events.py`, `test_run_artifacts.py`).
- [x] 9.8 Authoring validation: confirmed already correct as of
      `canonical-strategy-instance-v1`'s original implementation —
      `ValidateStrategyConfig.execute()` already sends
      `DeployableStrategyInstance.model_dump(mode="json")` directly
      (`{enabled, strategy_id, ticker, base_timeframe, raw_spec}`), the
      exact shape Engine's `CanonicalStrategyInstanceModel` expects,
      correlated by `index`/`config_hash` — no Engine-returned
      `instance_id` was ever depended on. No code change required.

## 11. Application seam: separate evaluation acquisition from materialization (Step 2)

Corrective/preparatory slice, added after §9 (Step 1). Purpose: let a
future batch path acquire N `StrategyEvaluationResult`s from one shared
Engine call and finish each one through the existing single-instance
execution/accounting/persistence pipeline, without duplicating that
pipeline. Does NOT implement batch itself — `RunBatchExperiment`,
`BatchCandidateRequest`, `candidate_id`/`variant_id`, and any Engine
`/range-batch` client remain untouched and continue to work exactly as
before, via `RunSingleInstanceBacktest`.

- [x] 11.1 Add `MaterializeBacktestOutcome`
      (`application/backtests/materialize_backtest_outcome.py`):
      `execute(request: SingleInstanceBacktestRequest, evaluation:
      StrategyEvaluationResult, market_frame: MarketFrame) ->
      SingleInstanceBacktestOutcome`. Performs contract acceptance,
      managed-replay provisioning, execution, accounting, and result
      construction — no Engine range evaluation, no MDS window
      resolution, no persistence. Constructor takes only
      `StrategyEnginePort` (needed for managed-replay calls during
      execution).
- [x] 11.2 Move `run_id` generation into `MaterializeBacktestOutcome`,
      after contract acceptance/execution/accounting succeed, immediately
      before constructing `SingleInstanceBacktestResult` — not at the top
      of the (now split) orchestration, so a candidate that fails before
      a materialized result exists never consumes a run identity.
- [x] 11.3 Slim `RunSingleInstanceBacktest.execute()` down to: derive
      `instance_id`, resolve the window, build the Engine wire request,
      call `evaluate_range()` once, read the `MarketFrame`, delegate to
      `MaterializeBacktestOutcome.execute()`. Public signature and
      external behavior unchanged.
- [x] 11.4 Tests: a continuation-only test proving
      `MaterializeBacktestOutcome.execute()` produces a correct outcome
      given a canned evaluation/frame with no `evaluate_range` call at
      all (fake engine raises if range evaluation is attempted); an
      `evaluate_range`-call-count assertion on the existing single-path
      composition test; a Phase-A-failure test (window/MDS audit) proving
      the continuation and its run-id generation are never reached; a
      Phase-B-failure test proving `run_id` generation does not run
      before a materialized result.
- [x] 11.5 Confirmed unchanged: `PersistSingleInstanceBacktest`,
      `accept_strategy_execution_contract`, `run_unified_execution_loop`,
      `account_execution_loop`, all persisted artifact shapes, and the
      entire `experiments/` batch package.

## 12. Future follow-up (explicitly not this change)

- [ ] 12.1 (Not started, not designed here) A future Runtime-deployment
      capability: `POST` deployment endpoint, atomic filesystem
      persistence into Runtime's deployment directory, Runtime
      discovery/reload interaction, and a Composer "Deploy" UI step after
      Validate/Backtest. This change's only contribution to that future
      work is making the deployable document already the right shape.
- [x] 12.2 Done — see §13. Batch evaluation optimization enabled by §11's
      seam: shared window resolution, one Engine `/range-batch` call, and
      N `MaterializeBacktestOutcome.execute()` calls in place of
      `RunBatchExperiment`'s prior N sequential
      `RunSingleInstanceBacktest.execute()` calls.

## 13. Batch experiment rebuild on the shared-evaluation seam (Step 3)

Clean-cutover rebuild of `RunBatchExperiment`, added after §11's
Phase-A/Phase-B seam landed. `BatchCandidateRequest.backtest` (a nested
standalone `SingleInstanceBacktestRequest`) is retired entirely — no
alias, no dual-schema acceptance, old shape fails closed.

- [x] 13.1 Rebuild `BatchExperimentRequest`/`BatchCandidateRequest`
      (`application/experiments/contracts.py`): experiment owns
      `strategy_id`/`range_policy`/`range` once; each candidate carries a
      `DeployableStrategyInstance` + its own execution/accounting/
      managed_policy_enabled/metadata. `model_validator` rejects: mismatched
      range shape, duplicate `candidate_id`, any candidate whose
      `strategy.strategy_id` differs from the experiment's, and any
      ticker/base_timeframe divergence across candidates — all before any
      external call.
- [x] 13.2 Add `StrategyEvaluationBatchVariant`/
      `StrategyEvaluationBatchRequest`/`StrategyEvaluationBatchVariantOutcome`
      (`domain/contracts.py`) and `StrategyEnginePort.evaluate_range_batch`
      (`ports/strategy_engine.py`).
- [x] 13.3 Implement `HttpStrategyEngineClient.evaluate_range_batch`
      (`adapters/http/strategy_engine_client.py`): wire request carries
      only `{market, variants:[{variant_id, strategy:{strategy_id,
      raw_spec}}], options}` — no `enabled`/`instance_id`/`run_id`.
      Response correlation is by `variant_id` key (via a dict), never
      array position; an unrequested, duplicate, or missing `variant_id`
      raises `UpstreamServiceError` before any candidate is touched.
      Factored the shared per-result body parser
      (`_parse_evaluation_result`) out of `evaluate_range` for reuse.
- [x] 13.4 Rebuild `RunBatchExperiment.execute()`
      (`application/experiments/run_batch.py`): shared Phase A (one
      `ResolveBacktestWindow.execute()`, one `evaluate_range_batch()`, one
      `read_historical_range()`) runs once before any candidate loop;
      per-candidate Phase B calls `MaterializeBacktestOutcome.execute()` +
      `PersistSingleInstanceBacktest.execute()` per successful variant,
      isolated by the three failure levels in
      `research-batch-experiments-v1`. Never calls
      `RunSingleInstanceBacktest` or `evaluate_range()`.
      `application/backtests/from_deployable_instance.py`'s existing
      `build_backtest_request()` projects each candidate's canonical
      strategy + the experiment's shared range into the
      `SingleInstanceBacktestRequest` `MaterializeBacktestOutcome`/
      `PersistSingleInstanceBacktest` need — no second builder.
- [x] 13.5 Wire `RunBatchExperiment` in `api/app.py` with
      `container.strategy_engine`/`container.market_data`/a
      `MaterializeBacktestOutcome` instance/`persist_single_instance_backtest`
      — no service-locator, explicit constructor injection.
- [x] 13.6 Tests: contract-level rejection (legacy shape, dummy
      full_available range, missing explicit_range, mismatched
      strategy_id/ticker/base_timeframe); shared-acquisition call counts
      (N candidates → one window resolution, one historical read, one
      `evaluate_range_batch`, zero `evaluate_range`); Engine wire shape
      assertions at the HTTP-client level; response correlation
      (shuffled order, unknown/duplicate/missing `variant_id`); per-result
      `instance_id` stamping; all three failure levels, including that a
      Level-3 failure does not roll back already-persisted siblings;
      managed-policy-events batch regression re-authored (not deleted)
      against the new architecture; standalone single-backtest regression
      unchanged.
- [x] 13.7 HTTP API exposure: unchanged — `RunBatchExperiment` is still
      not exposed via a public Research HTTP route. Not added here; this
      slice is scoped to the application/Engine-integration rebuild only,
      per the same non-goal as the rest of this change's frontend/HTTP
      surface work.
- [x] 13.8 Corrective: `StrategyEvaluationBatchRequest` carries
      `expected_market_data_hash`; `HttpStrategyEngineClient
      .evaluate_range_batch` sends it; `RunBatchExperiment` supplies
      `window.market_data_hash`. Requires the paired Engine-side
      corrective (`strategy_engine` commit `94f1419`,
      `strategy-evaluation-canonical-boundary-v1` Slice 10) that added
      `expected_market_data_hash` to `/range-batch` and forwards it to the
      shared L0 acquisition — batch's shared acquisition now has the same
      fail-closed provenance guarantee single `/range` already had.

## 14. Public backtest API boundary: accept the canonical deployable instance directly

Corrective slice, closing the last narrow boundary leak found while
auditing Research's public HTTP surface ahead of frontend migration:
`POST /api/research/backtests` accepted the internal
`SingleInstanceBacktestRequest` directly, forcing any caller to
pre-project `DeployableStrategyInstance` → `StrategyInstanceIdentity`
(dropping `enabled`) itself, even though `build_backtest_request()`
already existed to do exactly that projection.

- [x] 14.1 Add `BacktestRunRequest` (`api/contracts/backtests.py`):
      wraps `DeployableStrategyInstance` (reused directly, not
      hand-copied) plus `range_policy`/`range`/`execution`/`accounting`/
      `managed_policy_enabled`. Mirrors
      `SingleInstanceBacktestRequest.validate_range_shape` so malformed
      range shape still fails closed via FastAPI's own body validation
      (422), not a bare exception from inside `to_application()`.
      `to_application()` calls the existing `build_backtest_request()` —
      no manual `StrategyInstanceIdentity(...)` construction in the API
      layer or the router.
- [x] 14.2 `api/routers/research.py`: `run_backtest()`'s body type changes
      from `SingleInstanceBacktestRequest` to `BacktestRunRequest`; the
      route calls `payload.to_application()` before
      `RunSingleInstanceBacktest.execute()`. `RunSingleInstanceBacktest`,
      `PersistSingleInstanceBacktest`, `BacktestRunResponse`, and every
      persisted artifact shape are unchanged.
- [x] 14.3 Tests: `full_available`/`explicit_range` accepted through the
      new shape; `enabled=true`/`enabled=false` both accepted with
      identical derived `instance_id` and distinct `run_id`s; legacy
      fields (`family`, `variant`, `strategy_version`, `instance_id`,
      nested `market`, nested `strategy` blob, caller `run_id`) rejected
      (422); persisted `request.json`'s `strategy` has no `enabled` field,
      proving the projection actually ran; full existing single/batch
      suite green unmodified.

Explicitly unchanged (scope guard): Strategy Engine, batch
(`RunBatchExperiment` already called `build_backtest_request()` itself,
untouched), config API, diagnostics `variant` query param naming
(tracked separately, not this slice).
