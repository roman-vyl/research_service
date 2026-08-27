## 1. Cross-repo coordination prerequisites

- [ ] 1.1 Confirm with the Strategy Engine repo owners that Engine will
      keep accepting requests without a caller-supplied `strategy_version`
      (Research MAY continue sending its historical constant internally
      without exposing it as a field Research requires from its own
      callers). Do not implement Engine-side changes here.
- [ ] 1.2 Confirm `strategy_runtime`'s `derive_strategy_instance_id`
      signature and hashing algorithm are stable enough to reference as
      the normative derivation from this repo (read-only dependency, no
      changes to that repo).
- [ ] 1.3 Confirm with the Strategy Engine repo owners that Engine's
      Composer Catalog API response field currently named `family`
      (`ComponentCatalog.family`) either gets renamed on Engine's own
      timeline or that Research reading it internally under its old name
      (without exposing `family` to Research's own callers) is acceptable
      in the interim. Do not implement Engine-side changes here.

## 2. Research Service — canonical strategy-instance domain types

- [ ] 2.1 Add a `StrategyInstanceIdentity` domain type
      (`strategy_id`, `ticker`, `base_timeframe`, `raw_spec`) with no
      `instance_id`, `family`, `variant`, or `strategy_version` fields.
- [ ] 2.2 Add a `DeployableStrategyInstance` domain type: the identity
      fields plus a sibling `enabled: bool`, matching Runtime's flat
      deployment-file shape exactly (no nested identity/deployment
      structure).
- [ ] 2.3 Port `derive_strategy_instance_id`'s algorithm (or call an
      equivalent shared implementation) so Research computes the same
      `instance_id` Runtime would for the same identity fields —
      `enabled` MUST NOT be an input to this derivation.
- [ ] 2.4 Add validation that rejects an instance carrying an explicit
      `instance_id`, `family`, `variant`, or `strategy_version` field,
      per `canonical-strategy-instance-v1`; confirm `enabled=false`
      passes validation identically to `enabled=true`.
- [ ] 2.5 Set `extra="forbid"` (or equivalent) on `StrategyInstanceIdentity`
      and `DeployableStrategyInstance` so an unrecognized/legacy field
      causes rejection instead of being silently dropped (per design.md
      Decision 10).

## 3. Research Service — backtest API

- [ ] 3.1 Change `SingleInstanceBacktestRequest` to embed a
      `StrategyInstanceIdentity` (not `DeployableStrategyInstance` —
      backtest evaluation never receives `enabled`) plus `range_policy`,
      `execution`, `accounting`, `managed_policy_enabled` — remove
      `run_id` as an input field.
- [ ] 3.2 Set `extra="forbid"` (or equivalent) on
      `SingleInstanceBacktestRequest` and on `StrategyEvaluationRequest`
      (currently only `frozen=True`, neither sets it — confirmed in
      `application/backtests/contracts.py:20` and
      `domain/contracts.py:89`) so that `run_id`, `instance_id`, `family`,
      `variant`, `strategy_version`, and `enabled` are rejected on
      `/backtests`, not silently ignored (per design.md Decision 10).
- [ ] 3.3 Model the range portion of the request as a discriminated
      shape keyed by `range_policy`: `explicit_range` requires a real
      `{from_ms, to_ms}` pair with existing alignment/ordering
      validation; `full_available` carries no range fields at all — not
      an optional-and-unvalidated pair (per design.md Decision 11). The
      identity subset's `ticker`/`base_timeframe` are unaffected by this
      and remain always-present.
- [ ] 3.4 Generate `run_id` inside the backtest orchestration use case on
      every accepted request (no idempotency/dedup lookup); return it in
      `BacktestRunResponse` as today.
- [ ] 3.5 Update the identity-consistency check in
      `application/backtests/artifacts.py` (`manifest.run_id != run_id`
      etc.) to reflect server-generated `run_id` and derived
      `instance_id`.
- [ ] 3.6 Fix `api/routers/research.py`'s `/backtests` route: the
      `except FileExistsError: raise RunAlreadyExists(payload.run_id)`
      branch (line 107 today) references a field being removed from
      `payload`. Reference the generated identity instead (e.g.
      `result.run_id`), and reconsider whether this branch should still
      surface as a caller-facing `409` at all now that collision is an
      internal Research concern, not caller-triggerable duplicate
      semantics (per design.md Decision 12).
- [ ] 3.7 Remove the `strategy_version` field from
      `StrategyEvaluationRequest`'s caller-facing surface; keep whatever
      value Research sends to Engine internally out of the
      Research-facing request contract (per design.md Decision 5).

## 4. Research Service — config validate/serialize/save

- [ ] 4.1 Change server-side `StrategyConfigDraft.instances` from
      `list[dict[str, Any]]` to `list[DeployableStrategyInstance]`
      (`enabled` included, since Composer edits/persists it here).
- [ ] 4.2 Update `config_validation.py` to validate each instance as a
      deployable strategy instance and to reject legacy identity fields
      per `research-config-validation-v1`'s new requirement.
- [ ] 4.3 Add an application-layer command builder/projector that
      extracts the `StrategyInstanceIdentity` from one stored
      `DeployableStrategyInstance` (dropping `enabled`) and combines it
      with Research-owned evaluation concerns (range policy,
      execution/accounting policy, managed-policy toggle) to produce a
      `SingleInstanceBacktestRequest` — a projection of the one strategy
      representation into a narrower request, not a conversion between
      two different strategy representations. This is the piece that
      closes the previously-flagged config→backtest gap.
- [ ] 4.4 Rename `family` to `strategy_id` in `config_validation.py` and
      the `family`-typed query param on `GET /configs/state` /
      `PUT /configs/selected` in `api/routers/research.py`. (The
      `/component-catalog` route's `family` param is handled separately
      in §5 — it's governed by a different capability,
      `research-component-catalog-v1`.)
- [ ] 4.5 Change persisted path construction in
      `adapters/config/filesystem.py` from
      `<configs_root>/<family>/<experiment_id>.json` to
      `<configs_root>/<strategy_id>/<experiment_id>.json`; update the
      per-root selection-file logic the same way.
- [ ] 4.6 Decide and document a migration path for existing saved configs
      under the old `<family>/` layout (flagged as a deployment/cutover
      concern in design.md — a one-time rename since `family` values and
      `strategy_id` values are identical today per the audit).

## 5. Research Service — component catalog

- [ ] 5.1 Rename the `family` query param to `strategy_id` on
      `GET /component-catalog` in `api/routers/research.py:47-49`.
- [ ] 5.2 Rename `GetComponentCatalog.execute(family=...)` to
      `execute(strategy_id=...)` in
      `application/research/component_catalog.py`, including the
      unsupported-value rejection message and the local cache key.
- [ ] 5.3 Handle the Engine-response-field seam: `ComponentCatalog.family`
      (Strategy Engine's own response field, checked at
      `component_catalog.py`'s `catalog.family != family` line) is not
      renamed by this task — Research reads it internally under its
      existing name while no longer exposing `family` to its own callers
      (per design.md Decision 14 and task 1.3's coordination check).
- [ ] 5.4 Add tests for `strategy_id`-based catalog requests and for
      unsupported-`strategy_id` rejection (HTTP 400, no upstream call),
      per `research-component-catalog-v1`'s delta spec.

## 6. Research Service — batch experiments

- [ ] 6.1 Remove the `run_id`-uniqueness half of
      `BatchExperimentRequest.validate_unique_identity`
      (`application/experiments/contracts.py:31,34-35`); keep only
      `candidate_id`-uniqueness.
- [ ] 6.2 Update `RunBatchExperiment._run_candidate`
      (`application/experiments/run_batch.py:41-76`): the success path
      keeps reporting the generated `result.run_id`; the failure path
      (currently `run_id=request.run_id` at line 70) SHALL NOT reference
      a candidate `run_id` that was never generated — omit `run_id` from
      a failed `BatchCandidateResult` instead.
- [ ] 6.3 Confirm `BatchCandidateResult.run_id` becomes optional
      (present only on `status="completed"`), and that all correlation
      between a request candidate and its result — in code and in any
      client-facing summary — uses `candidate_id`.
- [ ] 6.4 Confirm each `BatchCandidateRequest.backtest` still wraps
      exactly one `StrategyInstanceIdentity` (the same shape the
      standalone `/backtests` endpoint accepts) — batch execution
      introduces no second strategy-instance shape.
- [ ] 6.5 Add tests: duplicate `candidate_id` rejected pre-execution;
      duplicate strategy/range parameters across candidates (no longer
      duplicate `run_id`) are explicitly allowed; a failed candidate's
      result has no `run_id`; a successful candidate's result has a
      generated `run_id`; batch summary correlation is verifiable via
      `candidate_id` alone.

## 7. Tests and gates (this repo)

- [ ] 7.1 Add/replace backend tests for: identity-subset validation
      rejection cases, `enabled` toggle not affecting `instance_id` or
      validation outcome, extra/legacy fields rejected (not ignored) on
      `/backtests`, server-generated `run_id` (including that a
      caller-supplied `run_id` is rejected), two identical requests
      producing two distinct runs, `full_available` request with no
      range fields, `explicit_range` request still requiring a real
      range, config save/validate/serialize round-trip under the new
      `strategy_id`-keyed path, and the command-builder projection from
      a stored instance to a backtest request.
- [ ] 7.2 Run full `research_service` test suite, including the new/
      updated batch-experiments and component-catalog tests from §5 and
      §6.
- [ ] 7.3 `openspec validate canonical-strategy-instance-v1 --strict`
      passes before implementation review.

## 8. Dependent repos (tracked here, implemented in their own changes)

- [ ] 8.1 `research_frontend`: rebuild Composer's
      `StrategyConfigDraft`/`StrategyInstanceDraft` types (including an
      editable `enabled` field per instance) and `runBacktest()` request
      construction against this contract; remove `variant`/`family`/
      editable `instance_id` from Composer UI; own change, own OpenSpec
      tree (or equivalent), not authored here.
- [ ] 8.2 `strategy_engine`: decide, on its own timeline, whether to drop
      `strategy_version` from `StrategySpecEnvelope`/`config_hash`, and
      whether/when to rename the Composer Catalog API's `family` response
      field to `strategy_id` — or keep either as Engine-internal-only
      concerns once Research stops forwarding/requiring them as
      caller-facing fields.
- [ ] 8.3 `strategy_runtime`: no change required; its existing
      `derive_strategy_instance_id` and deployment file shape are already
      the reference implementation this change points to.

## 9. Future follow-up (explicitly not this change)

- [ ] 9.1 (Not started, not designed here) A future Runtime-deployment
      capability: `POST` deployment endpoint, atomic filesystem
      persistence into Runtime's deployment directory, Runtime
      discovery/reload interaction, and a Composer "Deploy" UI step after
      Validate/Backtest. This change's only contribution to that future
      work is making the deployable document already the right shape.
