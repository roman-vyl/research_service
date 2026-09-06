## Context

See proposal.md - Why. Load-bearing facts established by code investigation:

- `BatchSideSummary`/`BatchCandidateResult`/`BatchExperimentResult`
  (`src/research_service/application/experiments/contracts.py:95,105,160`) are all
  `ConfigDict(extra="forbid", frozen=True)`.
- `_verify_batch_artifact` (`scripts/autoresearch_supervisor.py:1498+`) does not read
  `execution_output.json`'s embedded `result`; it independently re-reads the canonical
  `summary.json` persisted by `persist_batch_experiment.execute()`, verifies its SHA256 against
  `manifest.json`, and parses it with `BatchExperimentResult.model_validate_json(...)`. That parsed
  object (`canonical_summary`) is what `candidate_facts` -- and therefore `EvidenceRef` /
  `_metric()` resolution during interpretation -- is built from.
- `scripts/autoresearch_execute_batch.py:23-27` calls `services.run_batch_experiment.execute(request)`
  to get `result`, then `services.persist_batch_experiment.execute(request, result)` (which produces
  the hashed `summary.json`), then writes `payload["result"] = result.model_dump(mode="json")` into
  `execution_output.json` -- the same `result` instance feeds both artifacts.

Consequence: because the models are strict and `summary.json` is hash-pinned, a post-hoc JSON patch
to either artifact is not viable (it would trip `extra="forbid"` on re-validation and break the
SHA256 check). The only correct injection point is inside the `BatchCandidateResult`/
`BatchSideSummary` construction itself, before `persist_batch_experiment.execute()` runs -- one
computation, consumed by both artifacts.

## Goals / Non-Goals

**Goals:**
- `cumulative_risk_outcome` computed once, in `candidate_summary.py`, using Decimal arithmetic,
  from the same win/loss facts already used for `win_rate` -- never reconstructed via
  `round(N * WR)`.
- Field lands in both the canonical `summary.json` (and therefore `candidate_facts`/`EvidenceRef`)
  and `execution_output.json`, because both are serializations of the same enriched `result` object.
- Minimal edit to existing, strict models -- no parallel structure, no new artifact, no new
  evidence kind.

**Non-Goals:**
- No change to `_verify_batch_artifact`, `_complete_execution_receipt`, or any other supervisor
  logic that already consumes `BatchExperimentResult` generically via its existing fields --
  they pass the new field through unchanged since they operate on the whole model, not a fixed
  field allowlist.
- No change to prompts, `program.md`, `MetricRoles` priorities, dense sweep, Compact Evidence,
  cross-iteration memory, Strategy Engine, or any Research Service contract beyond the two models
  named above.
- No persistence-format version bump: `manifest["contract_version"]` stays
  `"research_batch_artifacts.v1"` since the batch artifact bundling contract (request/summary/
  manifest triple, hashing scheme) is unchanged -- only the summary's own row schema gains a field,
  which is the same category of change as the existing `win_rate`/`profit_factor` fields already in
  that schema.

## Decisions

**Computation site: `candidate_summary.py`, not a new module.** `_side_summary()` and
`derive_batch_candidate_summary()` already hold `len(trades)` and the win/loss partition in scope
right where `win_rate` is computed. Adding `_cumulative_risk_outcome(n, wr)` there keeps one
formula, colocated with the fact it derives from, with no new file.

**Formula implementation: `Decimal(n) * (2 * wr - 1)` computed from `win_rate`, not from a
reconstructed win count**, per explicit instruction -- even though at this exact call site the raw
win count is available and would be numerically identical (WR is an exact `Decimal` ratio, so
`N*(2*WR-1) == 2*wins - N` exactly, no rounding difference here). Using the WR-based formula
everywhere keeps a single, reusable definition that also works at any future call site where only
`N`/`WR` are available (e.g. a worker or analysis script re-deriving ΣR from persisted facts alone),
rather than one formula tied to internal-only data.

**Edge case N == 0 -> ΣR = 0, WR stays null.** `_win_rate` already returns `None` exactly when
`not trades`. `_cumulative_risk_outcome` short-circuits on `n == 0` before touching `wr`, returning
`Decimal("0")` -- matches `_win_rate`'s existing null-on-empty behavior without forcing WR to a
sentinel value.

**Defensive `0 <= WR <= 1` check lives in `_cumulative_risk_outcome`.** `win_rate` itself has no
`Field(ge=0, le=1)` constraint on the Pydantic model (confirmed absent) and is computed as
`winners/len(trades)` which is structurally already in `[0, 1]` -- so this check can never fail in
current code, but is retained as explicit defense-in-depth against a future formula change to
`_win_rate`, per the request's own requirement, raising `ValueError` (caught the same way other
`ValueError`s from this module already propagate through `run_batch_experiment.execute()`).

**Invariant ΣR_total == ΣR_long + ΣR_short is a structural consequence, not a runtime check.**
Trades partition exactly into `long`/`short` by `trade.side` (`derive_batch_candidate_summary`
already does this), so `wins_total = wins_long + wins_short` and `N_total = N_long + N_short` hold
by construction; substituting into `ΣR = 2*wins - N` shows the aggregate equals the side sum
algebraically. No separate runtime assertion is needed in production code; a unit test asserts it
holds for representative fixtures as a regression guard.

**Model change: add `cumulative_risk_outcome: Decimal` to both `BatchSideSummary` and
`BatchCandidateResult`, required-on-completion.** Matches the existing pattern of `return_pct`/
`max_drawdown` (always present on a completed candidate, `Decimal`, never `None` -- unlike
`win_rate`/`profit_factor` which can be `None`). Added to `_SUMMARY_FIELDS` and
`_SUMMARY_FIELDS_REQUIRED_ON_COMPLETION` in `contracts.py:29-30` so `validate_summary_shape`
enforces required-on-completion / forbidden-on-failure automatically, with no new validator code.

**`CANONICAL_METRIC_PATHS` extension is additive only.** `_metric()` (dict-walk resolver) is
schema-agnostic and needs no change; only the frozenset literal in
`scripts/autoresearch_quality_contracts.py` gains three string entries following the existing
`win_rate`/`long.win_rate`/`short.win_rate` naming convention.

## Risks / Trade-offs

- [Touching a Research Service production contract, which is explicitly out of scope for this
  session's broader work] -> Mitigated: this is the pre-authorized fallback for exactly this
  situation (strict models proven un-patchable at the JSON layer); the change is the minimal
  possible field addition, not a restructuring, and does not touch the artifact bundling contract
  (`manifest.json` shape, hashing scheme, `request.json`/`summary.json` file layout) at all.
- [A completed candidate whose `win_rate` is ever made nullable-but-nonzero-N by some other future
  change would silently need `_cumulative_risk_outcome` revisited] -> Mitigated: `_win_rate` only
  returns `None` when `trades` is empty (confirmed in current code), and
  `_cumulative_risk_outcome`'s own `n == 0` short-circuit reads that same emptiness, so the two
  functions stay coupled to the same underlying condition rather than to each other's output.

## Migration Plan

No data migration: this only affects freshly-computed batch summaries going forward. Existing
persisted `summary.json` artifacts under `RESEARCH_ARTIFACTS_ROOT/batches/` are immutable
(`Atomic, immutable batch artifacts` requirement) and are never rewritten; they simply predate the
new field and are not read by any code path that requires it retroactively.
