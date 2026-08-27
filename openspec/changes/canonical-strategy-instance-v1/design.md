## Context

A prior cross-repo audit in this session established, with file:line
evidence, the following facts this design relies on (see proposal.md for
the "why"; this section states only what constrains the "how"):

- Strategy Runtime is the authoritative source for strategy-instance
  identity semantics and for the `derive_strategy_instance_id` derivation
  (`derive_strategy_instance_id(strategy_id, ticker, base_timeframe,
  raw_spec)`). Its persisted deployment-file shape — flat `enabled`,
  `strategy_id`, `ticker`, `base_timeframe`, `raw_spec`, one file per
  instance, `instance_id` explicitly forbidden as input — is already
  almost exactly the target deployable representation this change
  converges Composer and Research onto, not a separate concept requiring
  a future reconciliation.
- `strategy_version`: audited LEGACY/COMPATIBILITY_FIELD across Strategy
  Engine and Research Service — schema-required only, never branched on,
  exactly one value (`"v1"`) ever registered, entirely absent from
  Runtime's own live-path contract (`LiveStrategySpec`).
- `family`: audited SAME_CONCEPT_DIFFERENT_NAME as `strategy_id` — Engine's
  own composer-catalog route passes `family=strategy_id` internally as a
  literal passthrough; no case exists anywhere in either codebase where
  the two values differ for the same entity.
- `enabled`: confirmed Runtime-only deployment/activation gate
  (`CommittedBarDeploymentSelector.select`), read only there; zero
  references in Research Service or Strategy Engine today. It sits
  outside the *identity* subset but is a real field of Runtime's
  deployment document, not a field to be stripped from every
  representation.
- Research's config layer (`StrategyConfigDraft`, `/config/save`, etc.)
  and its backtest layer (`SingleInstanceBacktestRequest`) are today two
  fully disconnected code paths, each with its own idea of what a
  strategy instance is. This change makes both consume the same strategy
  representation — the backtest layer via a narrower identity-subset
  projection of it, not a second, structurally different object — instead
  of adding a translator between two different representations.
- The Composer→backtest submission path has zero test coverage today and
  its current request body is already structurally incompatible with the
  canonical backtest endpoint (posts `{draft: apiDraft}`, endpoint expects
  `SingleInstanceBacktestRequest` directly) — there is no currently
  working caller whose wire compatibility this design needs to preserve.
- An adversarial review of an earlier draft of this change, verified
  against the actual code (not just the change documents), found two
  places where removing/renaming fields breaks *working* code and an
  *active* baseline spec that the earlier draft incorrectly claimed were
  unaffected:
  - `application/experiments/contracts.py:31,34-35`
    (`BatchExperimentRequest.validate_unique_identity`) reads
    `item.backtest.run_id` for every candidate **before** any candidate
    executes; `application/experiments/run_batch.py:54,70` reads it again
    on both the success and failure paths. All three reads break once
    `SingleInstanceBacktestRequest.run_id` is removed.
  - `api/routers/research.py:47-49,74-76` and
    `application/research/component_catalog.py:15-25` use `family` as
    the strategy selector, matching `research-component-catalog-v1`'s
    baseline requirement text ("Unsupported family rejection") — a
    capability this change did not originally declare as modified.
  - `api/routers/research.py:107` (`except FileExistsError: raise
    RunAlreadyExists(payload.run_id)`) reads `payload.run_id` in the
    `/backtests` route's own error path, not just in
    `application/backtests/artifacts.py`.
  - Neither `SingleInstanceBacktestRequest` nor `StrategyEvaluationRequest`
    (`application/backtests/contracts.py:20`, `domain/contracts.py:89`)
    sets `extra="forbid"` today — only `frozen=True`. Pydantic v2 defaults
    to `extra="ignore"`, so every "field X SHALL be rejected" requirement
    in this change's delta specs needs that config added, or those fields
    would be silently dropped instead of causing a rejection.
  This design and `tasks.md` account for all four findings below.

## Goals / Non-Goals

**Goals:**
- Fix the normative strategy-instance contract so Composer, Research, and
  Runtime describe the same object, with `instance_id` derived
  identically everywhere.
- Separate strategy **identity** (`strategy_id`/`ticker`/`base_timeframe`/
  `raw_spec`) from `enabled` **deployment metadata** semantically, while
  keeping both in one flat deployable document — matching Runtime's
  existing file shape — rather than inventing a nested identity/metadata
  structure Runtime doesn't use.
- Remove `family`, `variant`, `strategy_version`, and caller-editable
  `instance_id` from every Research-facing strategy-instance
  representation — no aliasing, no compatibility shim.
- Move `run_id` ownership to Research Service, with simple v1 semantics:
  every accepted request creates a new run.
- Remove the requirement that `full_available` requests carry a
  meaningless placeholder market range.
- Make the deployable document Composer produces structurally usable as a
  Runtime deployment file with no strategy-semantic transformation, so a
  future deployment capability only has to add transport/persistence, not
  redesign the object.
- Make every request model this change touches actively reject the
  fields it retires, rather than silently ignoring them.
- Keep batch-experiment candidate/run correlation working once `run_id`
  is no longer known before a candidate executes.
- Keep the component-catalog boundary's selector consistent with the
  rest of the Research-facing contract (`strategy_id`, not `family`).

**Non-Goals:**
- Changing Strategy Engine calculation, live-trading semantics, or
  Engine's own `LiveStrategySpec`/`StrategySpecEnvelope` wire schema —
  that is Engine's own OpenSpec authority; this design only fixes what
  Research Service requires from its own callers.
- Touching Market Data Service coverage APIs, warmup policy, or any part
  of `research-history-window-planning-v1`'s still-deferred scope (see
  Risks below for the exact seam between that change and this one).
- Changing the physical persistence mechanism (temp file + fsync + atomic
  rename) beyond the `family`→`strategy_id` path-segment rename that field
  retirement forces.
- Batch execution architecture and range-batch wiring: this change fixes
  only how a candidate's run identity is correlated, not how batches are
  scheduled, executed, or how the future range-batch/Engine-batch
  integration works. `research-batch-experiments-v1`'s
  multi-variant-in-one-run question was already resolved before this
  change (confirmed free of `variants[]`-in-run semantics); only its
  run-identity-correlation requirement is touched here.
- Composer execution/accounting-policy editing UX.
- **The future Runtime-deployment capability itself**: no `Deploy`
  endpoint, no filesystem path/permissions design, no Runtime
  reload/watch mechanism, no Composer "Deploy" UI, no live-activation
  orchestration. This change only ensures the deployable document shape
  doesn't have to change again when that capability is built.
- Request-level idempotency or deduplication for `POST /backtests` (see
  Decision on run identity below — deliberately simple v1 semantics, not
  a placeholder for a mechanism to add later without deciding now).
- Any implementation in `research_frontend`, `strategy_engine`, or
  `strategy_runtime` — this change's specs live in `research_service`
  only; the other three repos' own adoption is tracked in `tasks.md` as
  dependent work, not authored here.

## Decisions

1. **One flat deployable document, two semantic layers, no structural
   nesting.** The wire/storage JSON is exactly `{enabled, strategy_id,
   ticker, base_timeframe, raw_spec}` — matching Runtime's existing file
   shape. `instance_id` is computed only from `strategy_id`/`ticker`/
   `base_timeframe`/`raw_spec` (the **identity subset**); `enabled` is
   metadata layered on top and plays no role in the hash/derivation.
   Toggling `enabled` does not create a new instance or change
   `instance_id`. Rejected: a nested shape like `{identity: {...},
   deployment: {enabled}}` — rejected because Runtime's real file format
   is flat and this change's whole point is convergence onto what Runtime
   already does, not a new abstraction Runtime would then also have to
   adopt.

2. **`enabled` is part of the canonical deployable document, not excluded
   from every representation — but it never crosses into the backtest
   request.** Composer/config storage SHALL hold `DeployableStrategyInstance
   = {enabled} + {identity subset}`, because the document Composer
   eventually hands to a deployment boundary needs to be usable as-is.
   `POST /backtests` SHALL only ever receive the **identity subset
   projected out of** that deployable document — never the deployable
   document itself, never `enabled`. A disabled instance validates and
   backtests exactly like an enabled one precisely because the backtest
   layer never sees `enabled` to begin with, not because it sees it and
   ignores it. (Earlier drafts of this design used "same object"/"one
   object reused" language for this relationship; that phrasing is
   corrected everywhere in this document and in `proposal.md` to "project
   the identity subset from the same deployable instance" — the risk
   being that "same object" could be misread as "the deployable document,
   `enabled` included, is what gets embedded in `SingleInstanceBacktestRequest`,"
   which is exactly wrong.) This reverses this change's earlier draft
   position (`enabled` fully excluded from Composer) — that draft
   conflated "not part of identity" with "not part of the document,"
   which is wrong once a future deploy capability is anticipated.

3. **`instance_id` is never a request or storage field, anywhere.** It is
   always computed from the identity subset, never supplied. Rejected:
   accept-but-recompute-and-silently-reconcile (ignore a caller-supplied
   value if it happens to match, error only on mismatch) — rejected
   because it keeps a dead field alive in the wire contract and invites
   drift; making the field's mere presence an error is simpler and closes
   the door on "how did the frontend's `instance_id` and the derived one
   diverge" debugging sessions before they start.

4. **`family` is retired, not aliased.** Composer/Research send
   `strategy_id` directly. Rejected: keep `family` as a wire-compatible
   alias for `strategy_id` — explicitly out of scope per this change's
   ground rules, and the audit found zero divergent-value case that an
   alias would ever need to paper over.

5. **`strategy_version` is dropped from the Research↔Engine backtest
   boundary, not defaulted.** Research Service SHALL stop requiring or
   forwarding it as a field it asks callers for. Rejected: keep it with a
   hardcoded `"v1"` default — a field nobody reads and nobody varies is
   pure legacy weight, and the identity hash it currently feeds
   (`StrategySpecEnvelope.config_hash` in Strategy Engine) stays
   deterministic without it, since the value has never varied. Cross-repo
   seam: Engine's own contract still declares this field today; that is
   Engine's schema to change on its own timeline, not this repo's. If
   Engine still wants an internal value, Research MAY continue supplying
   the historical constant on the wire to Engine without exposing it as
   a field Research requires *from its own callers* — this is called out
   explicitly in `tasks.md` as a coordination point, not silently absorbed
   as if Engine already changed.

6. **`run_id` becomes Research-generated; every accepted request creates
   a new run.** The backtest endpoint no longer accepts `run_id` as an
   input field. v1 semantics are deliberately simple: two requests with
   identical strategy instance and evaluation parameters, submitted
   intentionally, produce two distinct runs — this is normative behavior,
   stated in the delta spec, not an unresolved question. Rejected: an
   optional caller-supplied `run_id`/idempotency key for
   dedup/replay-safety — rejected for v1 because no concrete caller need
   was found in the audit and it would reintroduce the exact ownership
   ambiguity this decision resolves; a content-addressed run identity
   (derived from instance + params) was also rejected for the same
   reason plus it would silently turn "run" into a memoized/cacheable
   concept it isn't today. Known limitation, not swept under an open
   question: a transport-level retry after an indeterminate network
   outcome (client sent the request, connection dropped before the
   response arrived) can produce two runs for what the caller intended as
   one submission. v1 accepts this as a stated limitation; a dedup
   mechanism is a genuine, separately-scoped future capability if this
   becomes a real problem.

7. **`full_available` requests carry no market-range fields.**
   `ticker`/`base_timeframe` alone select the stream; `explicit_range`
   still requires a real `from_ms`/`to_ms`. This is a request-*shape*
   decision only — the resolution mechanism (MDS `get_bounds`, continuity
   audit against the resolved window) is unchanged and stays normative in
   `research-single-instance-backtest-v1` exactly as it is today.

8. **Config-draft `instances[]` stays a Research-owned grouping array;
   each element is the same deployable strategy-instance object used
   everywhere else.** `experiment_id` survives as a Research
   editing/persistence grouping concern and does not become part of any
   individual instance's identity — the same relationship a
   batch/experiment already has to its individual runs. Building a
   backtest request from a stored instance is a matter of an
   application-layer command builder/projector that **extracts the
   identity subset from the stored deployable instance and adds**
   Research-owned evaluation concerns (range policy, execution/accounting
   policy, managed-policy toggle, generated `run_id`) — a *projection* of
   the one strategy representation into a narrower evaluation request,
   never a translator converting one strategy representation into a
   structurally different one, because there is only one strategy
   representation and the backtest request is not itself a second one.

9. **Persisted path `<configs_root>/<family>/<experiment_id>.json` becomes
   `<configs_root>/<strategy_id>/<experiment_id>.json`.** A rename of the
   existing atomic-persistence mechanism; atomicity, fsync, and
   corrupt-file-isolation behavior are unaffected.

10. **Retired fields are actively rejected, not silently dropped.**
    `SingleInstanceBacktestRequest`, `StrategyEvaluationRequest`, and any
    new identity/deployable-instance model this change adds SHALL set
    `extra="forbid"` (or the equivalent fail-closed behavior for
    whichever request model ends up hosting the identity subset).
    Without it, Pydantic v2's default (`extra="ignore"`) would silently
    drop `run_id`/`instance_id`/`family`/`variant`/`strategy_version`/
    `enabled` on a `/backtests` request instead of rejecting it — directly
    contradicting this change's delta-spec scenarios that require
    rejection. Rejected alternative: rely on scenario tests alone to
    catch this — rejected because it's a config flag, not a design
    trade-off; better to state the requirement than assume an
    implementer notices Pydantic's default.

11. **`full_available` vs `explicit_range` is a discriminated, not a
    uniformly-optional, request shape.** The canonical strategy instance
    embedded in a backtest request always carries `ticker`/
    `base_timeframe` (they're part of the identity subset). The
    *range* portion of the request is conditional on `range_policy`:
    for `explicit_range` it SHALL be a required `{from_ms, to_ms}` pair
    with the existing alignment/ordering validation; for
    `full_available` it SHALL be absent entirely, not an
    optional-and-ignored pair. Implementation SHALL express this as a
    discriminated union (or an equivalent typed model with
    `range_policy`-conditional validation) — not as a single `MarketRange`
    type with `from_ms`/`to_ms` made merely optional-and-unchecked, which
    would silently re-permit the dummy-range workaround this change
    exists to forbid. No pseudocode prescribed here; the binding rule is
    the outcome (no dummy range ever required or accepted for
    `full_available`), not a specific Pydantic pattern.

12. **The `/backtests` route's own error path stops referencing
    caller-supplied `run_id`.** `api/routers/research.py`'s `except
    FileExistsError: raise RunAlreadyExists(payload.run_id)` reads a
    field that no longer exists on `payload` once `run_id` is
    server-generated. Collision on a generated `run_id` becomes an
    internal Research concern (astronomically unlikely with a proper
    generation scheme, not a caller-triggerable error path per the
    "Duplicate run rejection" removal) — the route SHALL reference the
    generated identity (e.g. `result.run_id`, available once
    orchestration has produced it) if it still needs to report a
    collision at all, and SHALL NOT report or imply a caller-owned run
    identity in that error path.

13. **Batch candidate/run correlation moves to `candidate_id`
    exclusively; `run_id` becomes a success-only result field.**
    `BatchExperimentRequest`'s pre-execution uniqueness check drops the
    `run_id`-uniqueness half and keeps only `candidate_id`-uniqueness —
    `run_id` doesn't exist until a candidate has actually run, so it
    cannot be validated before execution. `BatchCandidateResult` reports
    the Research-generated `run_id` on success and omits it on failure
    (no run was created to have one). Each candidate still wraps exactly
    one canonical strategy-instance identity subset — batch execution
    does not get its own, second strategy-instance shape. Rejected:
    keeping a client-supplied `run_id` on `BatchCandidateRequest` only
    (not on the standalone single-instance endpoint) — rejected because
    it would reintroduce caller-owned run identity through a side door,
    contradicting Decision 6 for no defensible reason specific to
    batches.

14. **Component-catalog selector renames `family`→`strategy_id`,
    matching every other Research-facing boundary.** Same treatment as
    Decision 4, applied to `research-component-catalog-v1`'s two
    requirements and the underlying route/query param and
    `GetComponentCatalog.execute()`. Cross-repo seam, same shape as
    Decision 5: Strategy Engine's own Composer Catalog API response still
    names its field `family` today (`ComponentCatalog.family`, checked
    against Engine's response in `component_catalog.py`); renaming
    Research's own query param and internal variable names does not
    rename Engine's response field. Research MAY continue reading
    Engine's `family`-named response field internally without exposing
    `family` as something Research asks its own callers for — the same
    "don't silently absorb an unfinished cross-repo rename" posture as
    `strategy_version`, tracked in `tasks.md` as a coordination point,
    not implemented here.

## Risks / Trade-offs

- [Risk] Overlap with the still-active `research-history-window-planning-v1`
  change on range semantics → [Mitigation] This change touches only
  whether a `full_available` *request* needs a caller-supplied placeholder
  range. It does not touch MDS coverage API, warmup policy, or
  `require_fully_warmed`/`allow_partial_warmup` — all exclusively that
  change's scope, and largely unimplemented/deferred per its own status
  note. Sequencing: this change's `full_available` request-shape decision
  can land independently and first; the other change's deferred MDS/
  warmup work is unaffected and proceeds on its own timeline.
- [Risk] Cross-repo drift — Strategy Engine's `strategy_version` field and
  `config_hash` computation are not edited by this change, only
  Research's caller-facing boundary is → [Mitigation] Explicitly flagged
  as follow-up work belonging to Strategy Engine's own OpenSpec tree;
  `tasks.md` sequences Research's boundary change to tolerate Engine
  still accepting `strategy_version` internally, avoiding a hard
  coupling to Engine's own change timeline.
- [Risk] Removing `run_id` from the request contract is a breaking wire
  change → [Mitigation] No currently-working caller exists to break
  further: this endpoint has zero test coverage and Composer's current
  request body is already structurally incompatible with it.
- [Risk] No request-level idempotency means a transport retry can create
  a duplicate run → [Mitigation] Accepted as a stated v1 limitation (see
  Decision 6); not solved here, not left ambiguous either.
- [Risk] `family`→`strategy_id` path rename changes the on-disk location
  of every existing saved config file → [Mitigation] Out of this design's
  scope to specify a data-migration script (implementation detail);
  `tasks.md` calls out that existing saved configs under the old
  `<family>/` layout become unreadable unless migrated, as a
  deployment/cutover concern for whoever implements the persistence-layer
  task.
- [Risk] Keeping `enabled` in the canonical document (rather than
  excluding it entirely) slightly widens what Research's config layer
  has to store/round-trip compared to a strategy-only shape →
  [Mitigation] Accepted deliberately: the alternative (strategy-only
  document today, a second `enabled`-bearing document invented later for
  deployment) is exactly the two-DTO-plus-translator problem this change
  exists to avoid.
- [Risk] Removing `SingleInstanceBacktestRequest.run_id` breaks
  `application/experiments/contracts.py`'s pre-execution uniqueness check
  and `run_batch.py`'s success/failure correlation, both of which read it
  today → [Mitigation] Addressed directly, not deferred: see Decision 13
  and the `research-batch-experiments-v1` delta spec — correlation moves
  to `candidate_id`, `run_id` becomes a success-only result field.
- [Risk] Renaming `family`→`strategy_id` at the component-catalog
  boundary touches a baseline spec (`research-component-catalog-v1`) this
  change originally failed to declare as modified → [Mitigation]
  Addressed directly: see Decision 14 and the new delta spec; the
  cross-repo half (Engine's own response field name) is called out as a
  coordination point in `tasks.md`, not silently assumed away.
