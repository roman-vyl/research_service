## Why

Composer, Research Service, and Strategy Runtime each describe "a strategy
instance" with a different shape today. Composer/Research use
`family`/`variant`/an editable `instance_id`/`experiment_id`; Runtime uses
a flat `enabled`/`strategy_id`/`ticker`/`base_timeframe`/`raw_spec`
deployment-file shape with a derived `instance_id` and forbids the other
fields outright. A cross-repo audit (Composer→backtest call chain,
Runtime/Engine contract comparison, `strategy_version`/`family`/`enabled`
field-by-field investigation) confirmed these are not two legitimate
representations of different things — they are one concept, described
inconsistently, with the divergence already baked into Research Service's
own config-persistence contract
(`<configs_root>/<family>/<experiment_id>.json`), not just in frontend
DTOs. A backtest launched from Composer today cannot even reach the
canonical backtest endpoint: the request body is structurally
incompatible with `SingleInstanceBacktestRequest`.

Strategy Runtime is the authoritative source for strategy-instance
identity semantics and for the `derive_strategy_instance_id` derivation.
Its existing deployment-file shape — `enabled` plus the four identity
fields, flat, one file per instance — is already almost exactly the
target representation the other two systems should converge on, not a
separate concept to be reconciled against later.

This change fixes the normative contract so Composer produces, Research
validates/serializes/persists/backtests, and Runtime deploys the same
strategy-instance object — closing the drift before any implementation
work proceeds.

## What Changes

- Define a new canonical strategy-instance contract with two layers over
  one flat JSON shape: an **identity subset** (`strategy_id`, `ticker`,
  `base_timeframe`, `raw_spec`) that determines `instance_id`, and a
  **deployable document** (identity subset plus a sibling `enabled`
  field) that Composer can hold, edit, and eventually hand to a future
  Runtime-deployment boundary unchanged. `instance_id` is derived, never
  stored or caller-supplied. `enabled` is deployment/activation metadata:
  toggling it does not change identity or `instance_id`, and Research
  backtest semantics do not depend on it — a disabled instance is fully
  validatable and backtestable.
- Retire `family`, `variant`, and `strategy_version` from every
  Research-service-facing strategy-instance representation. **BREAKING**
  for any caller still sending them.
- Make Research Service own `run_id` generation; the backtest endpoint no
  longer accepts `run_id` as a request field. **BREAKING**. Each accepted
  backtest request creates a new immutable run — request-level
  idempotency/deduplication is explicitly not part of this contract.
- Make `range_policy=full_available` requests carry no market-range
  fields at all — `ticker`/`base_timeframe` alone select the stream; no
  caller-supplied placeholder `from_ms`/`to_ms` is required or accepted.
  **BREAKING** for the `explicit_range` vs `full_available` request shape.
- Re-scope Research's config-draft `instances[]` as a Research-owned
  grouping array whose elements are the same deployable strategy-instance
  object, not an untyped per-instance dict — and rename the persisted
  config path segment from `<family>` to `<strategy_id>` to match. A
  backtest request is built by **projecting the identity subset extracted
  from that same deployable document**, plus Research-owned evaluation
  concerns (range policy, execution/accounting policy, managed-policy
  toggle, generated `run_id`) — `enabled` stays behind at the
  config/deployable layer and never reaches `/backtests`. There is no
  separate "config strategy DTO" converted into a "backtest strategy DTO"
  by a translator: there is one strategy representation, and the backtest
  request is a narrower projection of it, not a second format.
- `risk_multiplier` (Runtime live-position operational state) is
  confirmed out of the canonical contract entirely — unlike `enabled`, it
  never appears in the deployable document, Composer, or any Research
  representation.
- Direction-only, not implemented here: a future Composer capability to
  deploy a strategy instance to Strategy Runtime (`Validate → Backtest →
  Deploy`) becomes straightforward once the deployable document is the
  same object throughout, because no strategy-semantic transformation is
  needed between what Composer edits and what a Runtime deployment file
  requires. The deployment endpoint, filesystem integration, and any
  Composer UI for it are explicitly out of scope for this change (see
  `design.md` Non-Goals).

## Capabilities

### New Capabilities

- `canonical-strategy-instance-v1`: the single strategy-instance JSON
  contract shared by Composer, Research Service, and Strategy Runtime —
  the identity subset, the deployable document built on top of it, and
  the derived-identity rule that ties them together. No existing spec
  owns this cross-service contract today.

### Modified Capabilities

- `research-backtest-api-v1`: request contract now wraps the canonical
  strategy-instance identity subset instead of an ad hoc envelope;
  `run_id` becomes server-generated instead of caller-supplied, replacing
  the prior caller-triggered duplicate-run-id rejection behavior; each
  accepted request creates a new run, with no request-level idempotency.
- `research-single-instance-backtest-v1`: `range_policy=full_available`
  requests no longer require a caller-supplied market range.
- `research-config-validation-v1`: each config-draft instance is now
  validated as one deployable strategy instance, not an unconstrained
  per-instance shape; every instance's `strategy_id` MUST also match the
  draft's own top-level `strategy_id` — one experiment/config explores
  one strategy type, never a mix.
- `research-config-persistence-v1`: persisted config identifier and path
  layout move from `family` to `strategy_id`.
- `research-batch-experiments-v1`: candidate pre-execution uniqueness and
  result correlation move from caller-supplied `run_id` to `candidate_id`;
  `run_id` becomes a Research-generated result field present only on
  successful candidates. Each candidate wraps one canonical deployable
  strategy instance, same shape as a standalone backtest's identity.
  **Later in this change (Step 3)**: the batch contract itself is
  rebuilt — a candidate no longer embeds a standalone
  `SingleInstanceBacktestRequest` (**BREAKING**, no alias); an experiment
  owns one shared `strategy_id`/`range_policy`/range, every candidate
  must share `ticker`/`base_timeframe`, and Research evaluates all
  candidates through one shared Strategy Engine `/range-batch` call
  (`candidate_id` used directly as the Engine `variant_id`) instead of N
  sequential standalone `/range` calls. See design.md Decision 16 and the
  delta spec's new requirements.
- `research-component-catalog-v1`: catalog selector moves from `family`
  to `strategy_id`, matching the backtest/config boundary.

Correcting an earlier draft of this proposal: `research-batch-experiments-v1`
was previously described as unaffected by this change ("already free of
`variants[]`-in-run semantics"). That claim is only true for the
multi-variant question; it is false for run-identity ownership, since
batch's pre-execution uniqueness check and success/failure correlation
both currently depend on `SingleInstanceBacktestRequest.run_id`, which
this change removes. See the delta spec and Decision below.

## Impact

- **research_service** (this repo): `application/backtests/contracts.py`
  (`SingleInstanceBacktestRequest`, `StrategyEvaluationRequest`), `domain/
  config.py` (`StrategyConfigDraft`), `adapters/config/filesystem.py`
  (persisted path layout), `api/routers/research.py` (route bodies,
  including the `payload.run_id` reference in the `/backtests` error
  path), `application/research/config_validation.py`,
  `application/research/component_catalog.py` (`family`→`strategy_id`),
  and `application/experiments/contracts.py` +
  `application/experiments/run_batch.py` (candidate/run correlation no
  longer keyed by a pre-execution `run_id`).
- **research_frontend** (dependent, tracked, not implemented in this
  change): Composer's `StrategyConfigDraft`/`StrategyInstanceDraft` types
  and the `runBacktest()` request-construction path must be rebuilt
  against this contract, including an editable `enabled` field on each
  instance draft — flagged in `tasks.md`, owned by that repo's own
  change.
- **strategy_engine**: resolved. `strategy_engine` completed
  `strategy-evaluation-canonical-boundary-v1` (commits `4028242`,
  `d61cfef`, `83e2f18`), retiring `strategy_version`, caller-supplied
  `instance_id`, and `compatibility_profile` from its Research-facing
  evaluation boundary and renaming the Composer Catalog API's `family`
  field to `strategy_id`. This change's tasks.md §9 brings Research's
  single-backtest, managed-replay, authoring-validation, and
  component-catalog wire calls in line with that now-final Engine
  contract. Batch's `/range-batch` client and `RunBatchExperiment`
  architecture are an explicit non-goal of §9, tracked for a later slice.
- **strategy_runtime** (authoritative source, not modified): its existing
  deployment-file shape and `derive_strategy_instance_id` function are
  the normative reference this contract converges on; no code change is
  requested there — this change brings the other two systems to Runtime's
  shape, not the other way around.
