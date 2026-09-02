## 1. Resolve and encode versioned contracts

- [ ] 1.1 Inspect the current canonical EMA Pullback strategy/config fixtures, live catalog shapes,
  and config-validation contracts; document the exact operator-approved fixture fields and stop
  APPLY if no authoritative starting document exists rather than inventing syntax.
- [ ] 1.2 Add exact schemas for `bbb_autoresearch_stage_contract.v1`,
  `bbb_autoresearch_state.v3`, `bbb_autoresearch_execution_plan.v2`,
  `bbb_autoresearch_iteration.v3`, and `bbb_autoresearch_journal.v3`, reusing existing quality and
  evidence definitions without changing v1/v2 schemas.
- [ ] 1.3 Add schema-equivalent manual/model validation for all v3 contracts, including exact keys,
  enums, hashes, unique geometry IDs, one-distance symmetric geometry representation, stage
  dispositions, and evidence-reference shapes.
- [ ] 1.4 Add negative contract tests for missing/extra fields, unknown stages/dimensions,
  duplicate/invalid geometries, malformed bindings/dispositions, and attempted silent v1/v2
  expansion.

## 2. Canonical starting strategy and initialization

- [ ] 2.1 Add one checked-in complete operator-approved EMA100/EMA200/EMA500 canonical starting
  strategy fixture with ticker/timeframe, trigger, direction, exits, risk, setup/blocker/context
  structure, component IDs, instance IDs, and all required parameters intact.
- [ ] 2.2 Implement typed semantic-binding resolution through the existing Research-proxied live
  component catalog for geometry, width, and lookback; reject missing, duplicate, ambiguous, or
  catalog-incompatible instances/parameters without a generic path language.
- [ ] 2.3 Make v3 initialization validate the full fixture through the existing canonical Research
  config-validation application path before creating the session directory.
- [ ] 2.4 Freeze normalized starting strategy, source/resolved hashes, resolved typed bindings,
  configured geometries, and programme contract into state/bootstrap; prove later fixture edits do
  not affect the initialized session.
- [ ] 2.5 Add deterministic init tests for valid snapshotting, unavailable dependencies, invalid
  strategy/catalog binding, no partial session creation, and unchanged legacy initialization.

## 3. Typed candidate mutation enforcement

- [ ] 3.1 Implement a narrow strategy normalizer/comparator that locates bound components by stable
  identity, compares candidates with the applicable immutable reference, and never mutates or
  interprets the strategy.
- [ ] 3.2 Enforce identity immutability for strategy ID, enabled/control envelope, ticker,
  timeframe, EMA periods, component IDs, every component instance ID, and all fields outside the
  active typed semantic dimensions.
- [ ] 3.3 Enforce `A_BASELINE` as exactly one candidate for one configured geometry, with both bound
  exit instances equal to the configured distance and every other field identical to the naked
  starting strategy.
- [ ] 3.4 Enforce B batches as one referenced completed Phase-A geometry family, with every
  candidate preserving that exact geometry and existing batch comparability/window invariants.
- [ ] 3.5 Enforce width-only B1, naked-reset/lookback-only B2, and width-plus-lookback-only B3;
  explicitly reject B1 width leakage into B2 and any unrelated candidate change before execution.
- [ ] 3.6 Add focused positive/negative tests for reordered component arrays, valid typed changes,
  asymmetric/invented/cross-family geometry, EMA/ticker/timeframe/trigger/exit/identity mutation,
  unknown parameters, and attempted arbitrary patch/path input.

## 4. Stage lifecycle and durable evidence

- [ ] 4.1 Bind v3 plans to active stage, starting/reference hashes, one geometry ID, exact allowed
  dimensions, and prerequisite disposition references before plan/request freeze.
- [ ] 4.2 Persist accepted Phase-A references with geometry and canonical experiment/candidate/run,
  artifact/receipt, market-data, realised-trade-count, and win-rate evidence; require every
  configured geometry before allowing Phase A closure without ranking them.
- [ ] 4.3 Validate and persist worker-authored `in_progress`, `characterized`, and
  `terminally_rejected` stage dispositions with applicable evidence, without deriving closure from
  metrics or changing existing Research Quality Policy judgments.
- [ ] 4.4 Enforce A→B1→B2 availability and prohibit B3 until B1/B2 independently close; make B3
  optional and preserve an evidence-backed terminal/`NO_STABLE_EDGE` conclusion after B2.
- [ ] 4.5 Advance state v3 and journal v3 mechanically with stage history/reference evidence while
  retaining all existing v2 quality assessment, negative evidence, side, topology, and promotion
  semantics.
- [ ] 4.6 Add lifecycle tests covering characterized and rejected B1/B2, premature B3 rejection,
  optional justified B3, optional terminal conclusion without B3, and supervisor no-winner/no-
  scientific-interpretation behavior.

## 5. Brokered execution and recovery integration

- [ ] 5.1 Insert stage-contract validation after plan/request shape validation and before plan
  freeze/execution intent, leaving the canonical executor and `src/research_service/**` untouched.
- [ ] 5.2 Bind stage/reference context transitively through existing plan/request hashes and receipt
  validation without creating a second evaluator or changing receipt scientific meaning.
- [ ] 5.3 Revalidate frozen v3 stage/reference bindings during interpretation, commit, and recovery;
  never reread the repository fixture for an active session.
- [ ] 5.4 Add crash/retry tests proving no duplicate batch after valid receipt, immutable geometry
  and mutation authority across retries, idempotent journal/state commit, and unchanged non-batch
  and v1/v2 recovery behavior.

## 6. Worker context and controlled template

- [ ] 6.1 Update the EMA session template to opt into state v3, reference the canonical fixture,
  configure the operator-approved symmetric measurement geometries, and bind A/B stages to the
  existing descriptive/structural quality roles.
- [ ] 6.2 Give planning and interpretation workers compact explicit active-stage context, frozen
  starting/reference strategy locations, geometry ID, allowed semantic dimensions, prior stage
  dispositions, and applicable canonical reference evidence without a giant duplicated prompt.
- [ ] 6.3 Update `program.md`, the Strategy Specification Reference link chain, and only the required
  EMA skill methodology wording for configured matched geometries and A→B1→B2→optional-B3 causal
  order; retain Strategy Engine as raw-spec source of truth.
- [ ] 6.4 Update status/README output for v3 stage, configured/completed geometries, dispositions,
  and next available stages without adding research ranking or recommendation logic.
- [ ] 6.5 Add prompt/template/status regression tests proving workers receive exact controls and
  cannot interpret Phase A as TP/SL optimization or B3 as mandatory.

## 7. Acceptance and verification

- [ ] 7.1 Run all targeted AutoResearch contract, init, mutation, lifecycle, brokered-flow,
  recovery, provenance, quality-policy, prompt, and legacy-compatibility tests.
- [ ] 7.2 Run `make verify`, `openspec validate --all --strict`, and `git diff --check`; confirm
  `src/research_service/**`, Strategy Engine/MDS/accounting/execution semantics, and unrelated
  OpenSpec changes remain untouched.
- [ ] 7.3 Review the implementation against every acceptance scenario and confirm no generic
  mutation DSL, successful-trade-count derivation, scalar score/winner, Phase C, or B4 was added.
- [ ] 7.4 After separate operator authorization, start a brand-new controlled HOST smoke session
  and verify the autonomous A reference line → B1 width → naked-reset B2 lookback → optional B3
  behavior; do not migrate/reuse a prior session or substitute fake research evidence.
