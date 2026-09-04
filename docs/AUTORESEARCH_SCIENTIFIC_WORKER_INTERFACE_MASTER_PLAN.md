# AutoResearch Scientific Worker Interface — Master Plan

Status: **DESIGN DOCUMENT, NOT YET APPROVED FOR IMPLEMENTATION.**
No production code, schema, supervisor, worker-profile, or prompt has been changed as part of
writing this document. This document is self-contained: it can be handed to a fresh engineer or
agent with no memory of any prior conversation.

Tagging convention used throughout this document:

- **CONFIRMED CURRENT FACT** — verified against the current repository code/state, with an exact
  `file:line` citation. If the codebase changes, re-verify before trusting this tag.
- **TARGET DESIGN** — a proposed future behavior. Does not exist in code today.
- **OPEN QUESTION** — a real unresolved design decision. Do not silently pick an answer during
  implementation without resolving it first.
- **DEFERRED** — explicitly out of scope for this design pass; a later, separate design effort is
  required before touching it.

---

## 1. Executive Summary

BBB AutoResearch runs a supervised loop in which a deterministic Python harness
(`scripts/autoresearch_supervisor.py`) executes backtests while an LLM plays trader-researcher: it
proposes hypotheses, chooses parameter values to test, and interprets results. A recent HOST smoke
run using a new local worker profile (`qwen35-local`, Ollama `qwen3.5:9b` via OpenCode) failed
twice during the *planning* stage — not because the model failed at trading reasoning, but because
it could not correctly produce the very large, low-level `execution_plan.json` artifact the planning
stage currently requires (**CONFIRMED CURRENT FACT** — see Section 3).

Investigation of the current stage-contract machinery
(`scripts/autoresearch_stage_contracts.py`) shows that a large fraction of what the planning
worker is forced to serialize today — component identity, fixed parameters, frozen starting
strategy, stage authority metadata — is **already** deterministically known to the harness before
the worker is ever invoked (**CONFIRMED CURRENT FACT**, Section 5). The harness currently uses this
knowledge only to *validate* the worker's output after the fact
(`validate_stage_request`/`_strip_allowed`, `scripts/autoresearch_stage_contracts.py:320-423`), not
to *generate* the mechanical parts of the worker's output before the fact.

This document proposes a **TARGET DESIGN**: split the current single `execution_plan.json`
worker-authored contract into two artifacts — a narrow, stage-scoped `scientific_proposal.json`
authored entirely by the LLM, and a `execution_plan.json` materialized deterministically by the
harness from that proposal plus already-known frozen state. The scientific worker keeps full
authority over every genuine scientific decision; the harness absorbs every mechanical,
already-known, already-validated field. This is proposed as a **canonical ABI for all worker
profiles** (Claude, Codex, GLM, Qwen, and future models) — not a special-case accommodation for a
weak local model.

This document is a design artifact only. No implementation has started. See Section 29 for the
recommended first concrete step.

---

## 2. Problem Statement

The current planning-stage worker-facing contract (`autoresearch/prompts/planning.md`,
`autoresearch/schemas/execution_plan.v2.schema.json`,
`autoresearch/schemas/batch_experiment_request.schema.json`) conflates two distinct kinds of work
in a single LLM output:

1. **Genuine scientific decisions**: which hypothesis to test, which parameter values or ranges to
   investigate, how to read observed response topology, whether a region is characterized or needs
   further work.
2. **Mechanical production materialization**: exact component/instance/parameter identities, fixed
   parameter values, full nested `raw_spec` structure, candidate/experiment identifiers, accounting
   and execution policy boilerplate, frozen-hash restatement.

Both kinds of work currently live in one worker call, validated as one atomic artifact
(`execution_plan.json`), written by one subprocess invocation of the worker's CLI. A worker that
gets the mechanical part wrong fails the whole iteration, regardless of the quality of its
scientific reasoning — and today's harness gives no signal distinguishing "bad science" from "bad
JSON."

The central open question this document answers architecturally (not by implementation) is:

> Can the harness absorb responsibility for everything that is already deterministically knowable
> from active stage, frozen session state, and stage contract — leaving the worker responsible only
> for what is genuinely a scientific choice?

---

## 3. Evidence From Qwen HOST Smoke

**CONFIRMED CURRENT FACT.** Session: `ema-anchor-host-smoke-qwen35-20260904200530`. Session
artifacts at `var/autoresearch/ema-anchor-host-smoke-qwen35-20260904200530/`.

Preceding this smoke, targeted tests were run and passed in full:

```
tests/test_autoresearch_worker_profiles.py + tests/test_autoresearch_supervisor.py
74 passed in 5.27s   (.venv/bin/python -m pytest, project virtualenv, Python 3.12.13)
```

Local provider chain was independently confirmed working, not merely assumed:

- `ollama list` showed `qwen3.5:9b` present locally.
- `opencode models` output included `ollama/qwen3.5:9b` verbatim.
- `var/autoresearch/ema-anchor-host-smoke-qwen35-20260904200530/iterations/0001/supervisor_metadata.json`
  recorded `worker.model = "ollama/qwen3.5:9b"`, `worker.runner = "opencode"`,
  `worker.worker_profile = "qwen35-local"` — i.e. the real local model was actually invoked, not a
  stub or a different provider.

Two planning attempts were made, both failed, and the session hard-stopped
(`var/autoresearch/ema-anchor-host-smoke-qwen35-20260904200530/state.json`:
`"status": "hard_stopped"`,
`"stop_reason": "planning output boundary violation: protected=[], unexpected=['baseline_spec.json']"`):

```
Attempt 0 (retry_index 0): duration_seconds 465.670035, exit_code 0
  failure: "invalid execution plan: cannot read valid JSON from
  .../iterations/0001/execution_plan.json: [Errno 2] No such file or directory: '.../execution_plan.json'"

Attempt 1 (retry_index 1): duration_seconds 683.507271, exit_code 0
  failure: "planning output boundary violation: protected=[], unexpected=['baseline_spec.json']"
```

Interpretation of this evidence: on attempt 0, the worker's CLI process exited cleanly
(`exit_code 0`) but produced no `execution_plan.json` at all. On attempt 1 (a retry), the worker
wrote content into `baseline_spec.json` — a pre-existing input file already present in the iteration
directory (the naked strategy fixture materialized at session init) — instead of creating
`execution_plan.json`. The harness's output-boundary check
(`scripts/autoresearch_supervisor.py:837-862`) correctly detected an unexpected file and hard-stopped
rather than silently accepting a wrong-file write.

`canonical batch execution` never started. `interpretation` never started
(`supervisor_metadata.json`: `"interpretation_attempts": []`).

**This is explicitly NOT evidence that Qwen3.5:9b is a poor trading researcher.** The model never
reached execution or interpretation, so its scientific reasoning capability was never exercised or
tested in this smoke. The demonstrated failure is entirely at the level of multi-file, schema-heavy,
production-contract materialization discipline during a single long-running planning call (~465s and
~683s respectively — the model was actively computing, not hanging). Qwen is simply the first worker
profile to expose, in a real HOST run, an architectural weight that has been latent in the
worker-facing contract for every worker profile all along.

---

## 4. Current Architecture — What Code Actually Does

**CONFIRMED CURRENT FACT.** The planning stage prompt is rendered by
`render_planning_prompt` (`scripts/autoresearch_supervisor.py:1698-1755`), which requires the
worker to write one `bbb_autoresearch_execution_plan.v2` document
(`autoresearch/schemas/execution_plan.v2.schema.json`) to `result_path` = `<iteration_dir>/execution_plan.json`
(`scripts/autoresearch_supervisor.py:1730`).

That schema (`execution_plan.v2.schema.json:5`) requires, as top-level fields:
`contract_version, session_id, iteration_id, phase, hypothesis, question, market_property_proxy,
competing_explanation, action, canonical_request, explanatory_metadata, hard_stop_reason,
stage_context`.

`canonical_request`, when `action == "batch"`, must be a complete
`BatchExperimentRequest` (`autoresearch/schemas/batch_experiment_request.schema.json`, 260 lines) —
a fully nested production contract: per-candidate `DeployableStrategyInstance.raw_spec` (component
identity, fixed parameters, mutable parameter, all setup/trigger/blocker/exit structure),
`AccountingPolicy`, `ExecutionPolicy` (with `const` fields the worker must reproduce verbatim, e.g.
`entry_price_source = "signal_bar_close"`), `candidate_id` (regex-constrained string), top-level
`experiment_id`, and (for legacy/pre-v3 semantics) `range_policy`/`range`.

`stage_context` (`execution_plan.v2.schema.json:15-24`) requires: `active_stage`,
`starting_strategy_sha256` (64-hex, must be copied verbatim, never recomputed), `allowed_semantic_dimensions`,
`prerequisite_disposition_refs`.

The worker is instructed (`autoresearch/prompts/planning.md:1-49`) to read the program, skill,
state, and journal tail, construct one action, and if `action == "batch"`, match the
`batch_experiment_request.schema.json` "exactly" — "Do not invent, rename, nest, or drop any field
from memory or a prior iteration's guess" (`planning.md:8-9`). The prompt already explicitly
forbids the worker from inventing `range_policy`/`range` for v3 sessions
(`planning.md:10`, `range_authority_note` built in
`scripts/autoresearch_supervisor.py:1721-1729`) — this is the one field class already fully
harness-owned today (see Section 5).

After the worker exits, the supervisor validates the written `execution_plan.json` against schema,
then against stage-contract semantics via `validate_stage_request`
(`scripts/autoresearch_stage_contracts.py:404-423`), which in turn calls `validate_stage_context`
(`:197-234`) and `_strip_allowed` (`:320-401`) to prove the candidate changed nothing outside the
stage's allowed semantic dimensions. Only after this passes does the supervisor freeze the request
(namespacing `experiment_id` via `_with_canonical_experiment_id`,
`scripts/autoresearch_supervisor.py:544`; injecting `range_policy`/`range` at
`:611-621`) and hand it to the execution path.

The output-boundary check that hard-stopped the Qwen smoke lives at
`scripts/autoresearch_supervisor.py:837-862`: it diffs the iteration directory before/after the
worker subprocess exits, allowing writes only to the declared `result_path` (here,
`execution_plan.json`) and files under the declared `analysis_dir`
(`<iteration_dir>/planning_analysis/`); anything else is `unexpected` and triggers a hard stop.
This mechanism is generic — it is parameterized by whatever `result_path` is passed to the stage
runner, not hardcoded to the string `execution_plan.json` (see Section 22 for the migration
implication).

---

## 5. Existing Stage Contract / Semantic Binding Model

**CONFIRMED CURRENT FACT.** `scripts/autoresearch_stage_contracts.py` defines the full
A→B stage-contract machinery for `bbb_autoresearch_state.v3` sessions.

`STAGES` (`:22-29`): `A_CONTROL, B1_WIDTH, B2_LOOKBACK, B3_WIDTH_X_LOOKBACK,
C_ENTRY_REGION_SELECTION, D_EXIT_GEOMETRY`.

`DIMENSIONS` (`:30-34`): `symmetric_measurement_geometry, anchor_stack_width,
untouched_anchor_lookback`.

`STAGE_DIMENSIONS` (`:35-40`) maps stage → allowed mutable dimensions:

```python
STAGE_DIMENSIONS = {
    "A_CONTROL": (),
    "B1_WIDTH": ("anchor_stack_width",),
    "B2_LOOKBACK": ("untouched_anchor_lookback",),
    "B3_WIDTH_X_LOOKBACK": ("anchor_stack_width", "untouched_anchor_lookback"),
}
```

`PROVISIONAL_STAGES = ("C_ENTRY_REGION_SELECTION", "D_EXIT_GEOMETRY")` (`:57`) — these stage names
exist as reserved identifiers only; `validate_stage_context` fails closed
(`:211-214`) if any plan targets them. **Their behavioral contract is undefined until a future
change explicitly defines it — do not design their production semantics as if implemented
(DEFERRED).**

`REQUIRED_STAGES` (`:64-69`) encodes causal prerequisites: B1 and B2 each require only A_CONTROL
closed (they are independent branches); B3 requires all three of A_CONTROL, B1_WIDTH, B2_LOOKBACK
closed.

The session's frozen `stage_contract` (assembled at init time from a template, see below) contains
a `semantic_bindings` list — one entry per dimension in `DIMENSIONS`, each with one or more
`targets`, each target fully specifying `component_role, component_id, instance_id, parameter_name,
params_storage, fixed_parameters` (`validate_stage_contract`, `:101-177`). The canonical template
`autoresearch/templates/ema_anchor_stage_contract_session.json` (lines ~69-84, re-read fresh) binds:

```
anchor_stack_width       -> component_id=anchor_stack_width_setup, instance_id=stage-width,
                             parameter_name=min_current_width_atr,
                             fixed_parameters={atr_timeframe: base, atr_period: 14,
                                                min_recent_width_atr: 4.0, width_lookback_bars: 80}

untouched_anchor_lookback -> component_id=untouched_anchor_setup, instance_id=stage-lookback,
                             parameter_name=lookback,
                             fixed_parameters={active_bars: 3}

symmetric_measurement_geometry -> two targets (stop_loss, take_profit exits),
                             parameter_name=distance.multiplier, params_storage=structural
```

This is loaded and validated at session init: `scripts/autoresearch_init.py:55-156` calls
`_load_v3_stage_contract`, which reads `template["stage_contract"]["semantic_bindings"]`
(`autoresearch_init.py:103-105`), then `validate_stage_contract` and
`validate_resolved_stage_targets` (`autoresearch_init.py:155-156`,
`scripts/autoresearch_stage_contracts.py:271-305`) before the session is allowed to exist. **This
proves the binding is frozen at session creation time, before any worker is ever invoked — it is
not something the worker discovers or negotiates.**

`reference_strategy(state)` (`scripts/autoresearch_stage_contracts.py:308-317`) returns a deep copy
of the frozen naked starting strategy — the single source of truth every stage's candidates are
compared against.

`_strip_allowed(strategy, contract, dimensions)` (`:320-401`) is the mechanism that currently
performs *post-hoc verification*: given a candidate strategy and the list of dimensions allowed for
the active stage, it locates each bound target inside the candidate's `raw_spec`, checks that its
`fixed_parameters` match exactly (`component != expected_fixed` raises, `:369-370`), replaces the
mutable parameter with the sentinel `"<mutable>"`, and returns the normalized structure for
comparison against the same operation applied to the frozen reference. `validate_stage_request`
(`:404-423`) does exactly this comparison for every candidate in the batch.

**Key architectural fact: this function set already contains everything needed to go the other
direction — from a scientific choice (a value for the mutable parameter) plus the frozen reference
plus the frozen binding, to a fully valid candidate `raw_spec` — but today it is used exclusively
for verification, never for construction.** This is the crux of the master-plan proposal: the same
deterministic knowledge the harness already has is currently used only to catch the worker's
mistakes after the fact, not to prevent them by not asking the worker to do that work at all.

`expected_prerequisite_disposition_refs(stage, state)` (`:180-194`) and
`_stage_authority_context(state)` (`scripts/autoresearch_supervisor.py:1659-1695`, in the
supervisor, not the stage-contracts module) are pure, deterministic functions computed from durable
state alone. `_stage_authority_context` is rendered directly into the planning prompt today (via
`stage_authority_context` prompt value, `autoresearch_supervisor.py:1749-1753`) — the worker is
already told the exact expected `mutable`/`frozen` dimension lists and exact
`prerequisite_disposition_refs` value in prose, then still separately required to re-encode that
same information as structured JSON in its output. This is the concrete instance of the "redundant
restatement" pattern named in Section 6.

`validate_disposition` (`:426-438`) validates the `stage_disposition` object
(`stage, status, evidence`) that interpretation, not planning, produces.

Stage transition is **not an LLM decision** at the mechanical level: after interpretation commits a
disposition, `scripts/autoresearch_supervisor.py:2072-2093` computes `next_stage` purely from
`disposition["status"]` and `active_stage` — A_CONTROL → B1_WIDTH automatically on
close, B1_WIDTH → B2_LOOKBACK automatically on close, and only B2_LOOKBACK → B3_WIDTH_X_LOOKBACK
requires the worker's `proposed_next_experiment.stage == "B3_WIDTH_X_LOOKBACK"` to be present
(`:2082-2087`) — i.e. B3 is opt-in via worker proposal, not automatic. B3 closing does not
auto-advance anywhere (`:2088-2093`, `C_ENTRY_REGION_SELECTION` is provisional).

---

## 6. Scientific vs Mechanical Responsibilities

**CONFIRMED CURRENT FACT**, synthesizing Sections 4-5: for B1_WIDTH and B2_LOOKBACK, every field of
`stage_context`, every `component_id`/`instance_id`/`parameter_name`/`fixed_parameters`, and the
entire `raw_spec` except the single mutable parameter's value, is deterministically derivable from
already-frozen session state before the worker is invoked. The worker's only genuine scientific
input for these stages is: which numeric value(s) or range to test for the one mutable parameter,
and the accompanying hypothesis/question/rationale text.

For A_CONTROL, `STAGE_DIMENSIONS["A_CONTROL"] == ()` — there is no mutable dimension at all; the
single candidate must be `_strip_allowed`-identical to the frozen reference in every respect except
what `A_CONTROL: ()` permits, i.e. nothing (see Section 9).

For B3_WIDTH_X_LOOKBACK, both `anchor_stack_width` and `untouched_anchor_lookback` targets are
individually just as deterministic as in B1/B2 — but **the code contains no concept of
"geometry"** (cartesian product, selected pairs, region refinement, etc.) at all. `STAGE_DIMENSIONS`
only says both dimensions are simultaneously mutable; nothing in `_strip_allowed`,
`validate_stage_request`, or the B3 branch of `_stage_authority_context`
(`scripts/autoresearch_supervisor.py:1685-1694`) constrains or assists how the worker should combine
values across the two dimensions. This is a genuine, currently unformalized scientific degree of
freedom (see Section 12).

---

## 7. Target Worker ↔ Harness Boundary

**TARGET DESIGN.** The central architectural principle:

> **LLM determines WHAT experiment should be performed. Harness determines HOW that experiment is
> represented, materialized, validated, identified and executed reproducibly.**

Scientific worker owns:

- the trading hypothesis;
- the research question;
- competing explanations;
- which values to investigate;
- which range to extend;
- which regions to refine;
- experimental geometry, when that is genuinely a scientific decision (B3 and beyond);
- topology interpretation;
- thinning / side / regime / concentration interpretation;
- the decision that the current area is characterized versus requires continuation;
- the next most informative experiment.

Deterministic harness owns:

- active stage authority;
- allowed semantic dimensions;
- the semantic binding from dimension to production component/parameter;
- fixed parameters;
- the frozen starting strategy;
- the frozen market universe / research horizon;
- component/instance/parameter mechanical identities, when already fixed by the stage contract;
- canonical Strategy Spec construction;
- candidate generation;
- candidate_id / experiment_id / correlation identities;
- production `BatchExperimentRequest` serialization;
- accounting / execution policy defaults;
- managed-replay derivation;
- `range_policy` / explicit range;
- market-data identity;
- artifact paths;
- provenance;
- integrity/freeze validation;
- actual execution.

Golden rule:

> **If a field can be unambiguously derived from active stage, frozen session state, stage
> contract, and the worker's own scientific choices, the worker must not be required to generate
> it.**

This boundary is explicitly proposed as a **candidate canonical ABI for every worker profile** —
Claude, Codex, GLM, Qwen, and any future model (see Section 20) — not a workaround scoped to
`qwen35-local`. It is motivated by, but not limited to, the smoke evidence in Section 3.

---

## 8. Target Artifact Flow

**TARGET DESIGN.** Conceptual pipeline:

```
Scientific Context
        |
Scientific LLM
        |
Scientific Proposal            <- LLM-authored: WHAT the researcher chose
        |
Deterministic Experiment Materializer
        |
Canonical Strategy Specs
        |
Canonical BatchExperimentRequest / execution_plan   <- Harness-authored: WHAT WILL ACTUALLY EXECUTE
        |
Existing Stage Validation      (validate_stage_request, unchanged)
        |
Existing Freeze / Integrity / Provenance  (unchanged)
        |
Canonical Research Execution   (unchanged)
        |
Compact Evidence
        |
Scientific LLM Interpretation
        |
Next Scientific Decision
```

Two distinct artifacts, two distinct authors:

- `scientific_proposal.json` — LLM-authored evidence of *what the researcher chose*.
- `execution_plan.json` — harness-authored, materialized evidence of *what will actually be
  executed*.

This split gives clean provenance: researcher intent is recorded independently from laboratory
materialization, and either can be inspected or audited without the other.

---

## 9. A_CONTROL Design

**TARGET DESIGN, with a strong recommendation grounded in CONFIRMED CURRENT FACT.**

Confirmed: `STAGE_DIMENSIONS["A_CONTROL"] == ()` (`scripts/autoresearch_stage_contracts.py:36`) — no
mutable dimension exists for this stage. `validate_stage_request`
(`scripts/autoresearch_stage_contracts.py:415-416`) enforces `len(request.candidates) != 1` raises
for `A_CONTROL` — exactly one candidate, no exceptions. `reference_strategy(state)` is a pure deep
copy of the frozen starting strategy (`:308-317`) — there is no per-value override mechanism today
(the comment at `:311-314` explicitly notes Phase A "no longer scans a configured geometry list,"
referencing `autoresearch-frozen-control-phased-discovery-v1`).

`autoresearch/program.md:40-41` states: "`A_CONTROL` measures the one frozen naked control exactly
once and does not scan or optimize exit geometry." No numeric or candidate-identity decision is
described for A_CONTROL anywhere in `program.md`.

The one thing `program.md:55-56` requires of *every* iteration, A_CONTROL included, is: "State the
hypothesis, competing explanation, market-property proxy, support, refutation, and confounder before
choosing compute." This is a genuine textual framing duty — even for a single frozen candidate, the
worker is expected to articulate what the control baseline measurement is *for* scientifically
(e.g., what a subsequent B1/B2 deviation from this baseline will be interpreted against). This is
not a numeric or geometric decision, but it is not nothing.

**Recommendation**: A_CONTROL likely needs no *numeric-decision* planning LLM call — there is no
candidate-value choice to make and only one legal candidate shape. Whether it needs a
*minimal textual* LLM call (hypothesis/question framing only, no `canonical_request` authoring at
all) versus can be fully templated/skipped and deferred entirely to the interpretation step that
follows the (harness-materialized, harness-executed) control run, is an **OPEN QUESTION** requiring
explicit resolution before Phase 1 implementation (Section 23). Two candidate lifecycles:

- **Option A (minimal LLM call)**: session init → planning LLM writes only
  `{hypothesis, question, competing_explanation}` (TARGET DESIGN shape, not final) → harness
  materializes the one frozen candidate deterministically → execution → interpretation.
- **Option B (no LLM call)**: session init → harness deterministically materializes and executes
  the one frozen candidate immediately → interpretation LLM is the *first* LLM call of the session,
  producing both the control interpretation and the first B1/B2 scientific proposal.

Option B removes an LLM call entirely for A_CONTROL and is the stronger reading of the evidence
above (zero scientific content requiring the *researcher*, as opposed to the *interpreter*, to
supply before execution). Option A preserves a place for the worker to state its framing hypothesis
before seeing the result, which has independent epistemic value (stating a prediction before seeing
data is a legitimate scientific practice, distinct from rationalizing after the fact). **This
document does not resolve Option A vs Option B — it is an explicit OPEN QUESTION for Phase 1
design**, not something to decide implicitly during implementation.

---

## 10. B1_WIDTH Design

**TARGET DESIGN — conceptual shape only, not a final schema.**

```json
{
  "hypothesis": "...",
  "question": "...",
  "values": [11, 12, 14, 16, 18, 20],
  "rationale": "...",
  "expected_information_gain": "resolve upper boundary"
}
```

Fields the worker must **not** be required to write, because Section 5 confirms they are already
deterministically derivable from frozen `stage_contract` + `active_stage` alone: `target_dimension`
(implied by `active_stage == B1_WIDTH`), `component_id`, `instance_id`, `parameter_name`,
`fixed_parameters`, `raw_spec`, candidate ids, experiment id, `starting_strategy_sha256`, `range`,
`market_data_hash`, accounting/execution policy boilerplate.

`values` may instead be expressed as an explicit range/step description (e.g.
`{"min": 10, "max": 22, "step": 2}`) **if that range/step choice is itself the worker's scientific
choice** — the harness must never choose the range, minimum, maximum, or step on its own; it may
only expand an explicit worker-specified range/step description into explicit candidate values
mechanically. Which representation (explicit list vs. range/step) the final schema supports is an
**OPEN QUESTION** left to the Phase 2 implementation design, not resolved here.

---

## 11. B2_LOOKBACK Design

**TARGET DESIGN.** Structurally identical to Section 10, with the scientific coordinate being the
`untouched_anchor_lookback` dimension (bound to
`untouched_anchor_setup.stage-lookback.lookback`, fixed `active_bars = 3`) instead of width. No
independent design content beyond Section 10 is required — this is intentional: B1 and B2 are
structurally symmetric single-dimension stages (`REQUIRED_STAGES` treats them as independent
siblings, Section 5), so their scientific-proposal shape should be symmetric by construction.

---

## 12. B3 Geometry — Explicit Design Gap

**No final schema is proposed here.** This section documents the gap, not a solution.

**CONFIRMED CURRENT FACT**: no code path — `STAGE_DIMENSIONS`, `_strip_allowed`,
`validate_stage_request`, or the B3 branch of `_stage_authority_context`
(`scripts/autoresearch_supervisor.py:1685-1694`) — contains any concept of experimental geometry.
`STAGE_DIMENSIONS["B3_WIDTH_X_LOOKBACK"]` (`scripts/autoresearch_stage_contracts.py:39`) simply lists
both dimensions as simultaneously mutable; how the worker should combine values across them is
entirely unconstrained today (worker must serialize N full candidates, each independently valid
under `_strip_allowed`, with no harness assistance or guidance beyond the prose note at
`_stage_authority_context` telling the worker to justify the joint region from B1/B2 evidence).

Candidate geometries a scientifically free worker might want, none of which should be prematurely
foreclosed by an overly narrow enum: full cartesian product, selected (width, lookback) pairs, sparse
targeted points, boundary extension along one axis, asymmetric refinement (dense near one edge,
sparse elsewhere), several distinct disjoint promising regions ("islands"), diagonal-like sampling
following a suspected ridge (`SKILL.md:142`, "diagonal ridge" language already exists in
methodology), or any other scientifically justified structure.

Guiding principle for the eventual design: **the worker explicitly specifies what points, regions,
or combinations it wants; the harness compiles exactly that geometry; the harness never silently
fills in a missing scientific choice** (no default grid, no default step, no default region).

This is deliberately scheduled as its own design checkpoint — **Phase 7** in Section 23 — after
B1/B2 are implemented and validated in production, not bundled into the initial B1/B2 work. Design
questions to resolve at that checkpoint include: how to represent named axes with explicit points vs
free-form region descriptions; whether the schema should support heterogeneous geometry types in one
proposal (e.g., a coarse cartesian sweep plus separately several targeted refinement points); and how
the materializer validates that a geometry description is internally consistent before attempting
candidate generation.

---

## 13. Interpretation vs Planning Lifecycle

**Investigation, not a settled recommendation.**

**CONFIRMED CURRENT FACT**: interpretation already produces both `stage_disposition`
(`autoresearch/schemas/iteration_result.v3.schema.json:7`, required fields `stage, status,
evidence`) and `proposed_next_experiment`
(`iteration_result.v3.schema.json:6`, `oneOf` an object with `kind`/`reason` or `null`) in the same
call that interprets the just-completed batch's results. The next iteration's *fresh* planning
worker (a new subprocess, new context) is currently required to re-derive and re-serialize a large
overlapping amount of the same stage/scientific context from scratch — even though the interpreting
worker, moments earlier, already implicitly "knew" what it wanted to do next (it named a
`proposed_next_experiment`).

Confirmed mechanical nuance (Section 5): stage transition itself is **not** gated on the worker's
proposal for A_CONTROL→B1 or B1→B2 (both auto-advance on `characterized`/`terminally_rejected`
disposition alone, `scripts/autoresearch_supervisor.py:2074-2081`) — only B2→B3 requires the
worker's explicit `proposed_next_experiment.stage == "B3_WIDTH_X_LOOKBACK"`
(`:2082-2087`). So today's `proposed_next_experiment` field already carries some, but not all,
transition-relevant scientific authority; the rest is deterministic.

**Evaluation, not adoption**:

- *Epistemic value of a fresh call*: A genuinely fresh planning invocation, with its own read of
  `state.json`/journal tail, provides an independent reconsideration point — the interpreting
  context's proposal is provisional; a separate planning pass could in principle catch a
  contradiction or reconsider given the full accumulated state rather than just the interpretation's
  own working memory. Whether this independent-reconsideration value is realized in practice, or
  whether the fresh planning worker in practice just restates the interpretation's proposal
  verbatim (in which case the second call is pure overhead), is an **OPEN QUESTION** not answerable
  from code alone — it requires empirical evidence from actual sessions (do fresh planning calls
  ever meaningfully diverge from the prior interpretation's `proposed_next_experiment`?).
- *Recovery/retry impact*: two independently retryable calls (Section 19) give cleaner failure
  isolation than one merged call — if a merged call fails, it is ambiguous whether the interpretation
  half or the next-proposal half was at fault, complicating retry semantics and provenance.
- *Scientific discipline risk*: merging risks momentum bias — a single context that just
  interpreted a result and immediately proposes the next experiment may anchor too strongly on its
  own immediately-prior narrative, reducing the natural friction a second, separately-invoked call
  provides.

**Recommendation**: do not merge planning and interpretation now. Keep two calls through at least
Phase 2/3 (B1/B2 rollout). Re-evaluate as a distinct, later phase (**Phase 9**, Section 23) once
real B1/B2 evidence exists on whether fresh planning calls diverge meaningfully from the prior
interpretation's proposal — this is an empirical question, not a purely architectural one, and
should not be decided by this document alone.

---

## 14. Component Catalog Role

**TARGET DESIGN**, split explicitly by stage class:

- **Locked stages (current B1, B2, and A_CONTROL)**: the component/instance/parameter binding is
  already frozen in `stage_contract.semantic_bindings` before the worker is ever invoked (Section
  5). For these stages, the worker likely does not need the full `component_catalog.json` snapshot
  at all — everything it would use the catalog to discover (component id, parameter schema, default
  values) is already resolved by the stage contract, and exposing the full catalog only adds
  unnecessary prompt surface and an additional place the worker could (as Qwen did) go looking for
  something to write into.
- **Future exploratory stages**: any stage where the worker is expected to select *new* components
  — a new setup, blocker, context, exit component, or interaction structure not already bound by the
  active stage contract — genuinely needs component discovery. The catalog is a real scientific
  capability surface in that case, not incidental prompt bloat.

**Explicit instruction**: do not remove the component-catalog concept from the system. Only scope
*when* it is served to the worker — omit it (or reduce it to a minimal binding-confirmation excerpt)
for locked B1/B2/A_CONTROL calls; retain full catalog access for any future stage where component
selection is itself a scientific decision. `C_ENTRY_REGION_SELECTION` and `D_EXIT_GEOMETRY` are
**PROVISIONAL_STAGES** (Section 5) — whether they will need catalog access is **DEFERRED** until
their behavioral contract is defined.

---

## 15. Deterministic Materializer Responsibilities

**TARGET DESIGN.** A new function (or small module), conceptually:

```
scientific_proposal + active_stage_contract + frozen_starting_strategy + frozen_research_horizon
  -> canonical Strategy Specs
  -> canonical BatchExperimentRequest
  -> (feeds into) existing validation/freeze/execution path, unchanged
```

Concretely, the materializer must, for B1/B2:

1. Read `active_stage` and resolve the single bound target via `_binding(contract, dimension)`
   (existing function, `scripts/autoresearch_stage_contracts.py:236-237`, reused unchanged).
2. Deep-copy `reference_strategy(state)` (existing function, `:308-317`, reused unchanged) once per
   proposed value.
3. For each proposed value, locate or insert the target component instance (mirroring
   `_find_instance`/`_instances`, `:248-268`, in the *construction* rather than *verification*
   direction — this is genuinely new code, since these functions currently only locate an existing
   instance for stripping/comparison, not insert a new one from scratch), set its
   `fixed_parameters` (verbatim from the stage contract) and the one mutable `parameter_name` to the
   proposed value.
4. Generate `candidate_id` deterministically (e.g. `f"{dimension}_{value}"`, exact scheme is an
   **OPEN QUESTION**, Section 26).
5. Attach `accounting`/`execution` policy defaults (source of these defaults — programme-level
   config vs hardcoded — is an **OPEN QUESTION**, Section 26).
6. Assemble the full `BatchExperimentRequest` (`experiment_id` logical part, `candidates`,
   `strategy_id`) — `range_policy`/`range` remains excluded here exactly as today
   (`scripts/autoresearch_supervisor.py:613-621` already forbids and separately injects this; no
   change to that mechanism).
7. Assemble `stage_context` (`active_stage`, `starting_strategy_sha256`,
   `allowed_semantic_dimensions`, `prerequisite_disposition_refs`) purely from
   `_stage_authority_context`-equivalent deterministic computation (already exists as pure functions,
   `expected_prerequisite_disposition_refs` `:180-194` and the `STAGE_DIMENSIONS` lookup — reused, not
   reimplemented).

The materializer is new code. Every function it calls to resolve frozen bindings, the reference
strategy, and prerequisite refs already exists and should be reused unchanged, not reimplemented.

Architectural placement: **OPEN QUESTION** — plausibly a new module
`scripts/autoresearch_plan_materializer.py` alongside `autoresearch_stage_contracts.py`, invoked by
`scripts/autoresearch_supervisor.py` between the planning-worker subprocess call and the existing
`validate_stage_request` call. Exact module boundary is left to Phase 2 implementation design, not
fixed here.

---

## 16. What Materializer Must Never Decide

**TARGET DESIGN — hard constraint, not aspirational.** The materializer is a compiler, not a
scientist. It must never:

- choose candidate values;
- choose min/max;
- choose step;
- choose whether/how to extend a boundary;
- choose which region is promising;
- choose a local optimum;
- judge that a response has plateaued;
- judge that a hypothesis is supported;
- choose B3 geometry;
- propose a new scientific-component hypothesis;
- choose the next experiment.

**Explicit warning**: this architecture must not degenerate into a set of hardcoded functions like
`add_width()`, `add_lookback()`, `pick_best()`, `optimize_range()` in which all real scientific
freedom has been pre-encoded by a human engineer and the "scientific worker" is reduced to selecting
from a small enumerated menu. Every value, range, region, or geometry choice that ends up in an
executed experiment must trace back to an explicit field in a worker-authored
`scientific_proposal.json`, never to a materializer default or heuristic.

---

## 17. Validation / Integrity / Freeze

**TARGET DESIGN, reusing CONFIRMED CURRENT FACT infrastructure unchanged.** The existing independent
validation path — `validate_stage_request`
(`scripts/autoresearch_stage_contracts.py:404-423`), which calls `validate_stage_context`
(`:197-234`) and `_strip_allowed` (`:320-401`) — is **not removed or weakened**. It remains the
independent last-line defense: the materializer itself may contain a bug, and the existing
verification path catches exactly the class of error it was built to catch (a candidate that
deviates outside its stage's allowed dimensions), regardless of whether the candidate came from a
worker typing it by hand or from a new materializer function. The freeze mechanics
(`_with_canonical_experiment_id`, `scripts/autoresearch_supervisor.py:544`; `range_policy`/`range`
injection, `:611-621`; `market_data_hash` verification, `:660-675`) are likewise unchanged — they
already operate on the fully-assembled `canonical_request` regardless of its authoring path, so a
materializer-produced request flows through the identical freeze/integrity pipeline a
worker-produced request does today.

---

## 18. Provenance Model

**TARGET DESIGN / OPEN QUESTION mix.** Conceptual hash chain to allow later proof of "which exact
scientific intent produced which exact executed experiment":

```
scientific_proposal_sha256
        |
materializer_version
        |
execution_plan_sha256
        |
canonical batch/run identities
        |
result artifacts
        |
interpretation references
```

`scientific_proposal_sha256` (hash of the LLM-authored proposal artifact) and `execution_plan_sha256`
(hash of the harness-materialized artifact) are the two natural anchor points — TARGET DESIGN,
low complexity, directly analogous to existing hash-based integrity checks already in the codebase
(`starting_strategy_sha256`, `market_data_hash`, receipt hashing at
`scripts/autoresearch_supervisor.py:2066`).

Whether `materializer_version` needs to be recorded (i.e., does the materializer itself need
versioning/provenance, so that a later audit can tell which materializer code produced a given
`execution_plan.json`) is an **OPEN QUESTION** — relevant if the materializer's logic changes over
time and old sessions need to remain interpretable, but potentially unnecessary complexity if the
materializer is expected to be simple and stable. Do not over-engineer this; resolve only if a
concrete need (e.g. an actual materializer bug affecting historical sessions) demonstrates it is
required.

---

## 19. Retry / Recovery Semantics

**TARGET DESIGN.** Four independently diagnosable failure classes, each with distinct retry
semantics — a strict improvement over today's undifferentiated planning-stage failure handling
(where, as the Qwen smoke showed, "no file written" and "wrong file written" both simply produce one
generic hard-stop path with no signal about which layer failed):

1. **Invalid scientific proposal** (worker wrote malformed or incomplete
   `scientific_proposal.json`, or none at all): retry only scientific-proposal generation. Do not
   touch existing input artifacts. Do not permit arbitrary file writes on retry. The output boundary
   remains fail-closed exactly as today (Section 22 covers the new protected-filename implication).
2. **Valid proposal, materializer or validator failure**: this is a harness bug, not a worker
   failure. Do not needlessly re-invoke the (potentially expensive, as the Qwen smoke's 465s/683s
   durations show) model. Surface this distinctly so it is triaged as an engineering defect, not a
   worker capability problem.
3. **Canonical execution dependency failure**: unchanged from today's existing fail-closed semantics
   (canonical dependency failure has no worker fallback, `autoresearch/program.md:64`) — no change
   proposed here.
4. **Invalid interpretation**: retry the interpretation contract only. Do not re-run execution — the
   canonical batch result already exists and is immutable; only the LLM's interpretation of it needs
   to be retried.

---

## 20. Worker Profile / Model Independence

**TARGET DESIGN, explicit constraint.** The target canonical interface — narrow, stage-scoped
`scientific_proposal.json` — must be **identical for every worker profile**: Claude, Codex, GLM,
Qwen, and any future model. This is not to be implemented as a per-profile branch (e.g. `qwen ->
atomic interface`, `Claude/Codex/GLM -> legacy full interface`). If the boundary described in
Section 7 is architecturally correct, it is correct independent of which model happens to sit behind
a given `WorkerProfile`.

**CONFIRMED CURRENT FACT**: `scripts/autoresearch_worker_profiles.py`'s `WorkerProfile` dataclass
(`:9-21`) carries only `key, runner, model, argv` — there is no schema-branching field, interface
version, or capability flag on the profile today. All four current profiles (`claude-sonnet46,
codex-gpt56-sol, glm52-opencode, qwen35-local`, `:24-70`) resolve through the identical
`resolve_worker_profile`/`argv` mechanism (verified in this session's test run: 74/74 tests passed,
including symmetric `test_required_worker_profiles_resolve_exact_argv` coverage for all four
profiles). Adding a per-profile interface branch would be genuinely new surface, not an extension of
an existing capability-flag mechanism — this reinforces that a profile-specific branch is an
architectural choice to actively avoid, not a natural extension of what exists.

A temporary legacy full-`execution_plan.v2` worker interface **may** exist during migration, scoped
strictly to compatibility with in-flight/old sessions and controlled rollout (Section 22) — but this
is explicitly a transition mechanism with a defined end state, not the target architecture.

---

## 21. Documentation Layering: CLAUDE.md vs SKILL vs program vs schemas

**TARGET DESIGN principle, no content change proposed in this pass (see Section 27).**

- `CLAUDE.md` (repo root) stays durable trading/research memory, implementation-light. Its own
  closing section is explicit on this: "This file is not a technical specification — its purpose is
  to preserve the trading hypothesis and the meaning of the research. Do not let technical
  refactoring silently change the scientific question AutoResearch is trying to answer"
  (`CLAUDE.md`, closing section). It must never become a JSON contract manual.
- `.claude/skills/ema-anchor-edge-research/SKILL.md` owns trading thesis, scientific process,
  topology, coarse-to-fine methodology, boundary resolution, thinning, side asymmetry, regimes,
  competing explanations, and the scientific meaning of each dimension (confirmed present today:
  `SKILL.md` sections "Parameters are proxies for market state," "Hypothesis-first protocol,"
  "B1. Independent one-dimensional discovery" through "B9. Optional third dimension," "Multi-metric
  and side-aware reasoning," "Overfitting defenses" — these already carry exactly this content and
  should continue to).
- `autoresearch/program.md` owns the operational constitution: worker responsibilities, forbidden
  actions, allowed outputs, deterministic harness boundary (confirmed present today: "Immutable
  evaluator," "Read before acting," "Required output" sections already carry this content).
- Production schemas (`autoresearch/schemas/*.json`) and reference docs own precise machine
  contracts.

These layers must not blend. A future `scientific_proposal` schema is a `schemas/`-layer artifact;
its existence should be *referenced* from `program.md` (operational constitution: "you write only
this artifact") but the schema's field-level detail belongs in the schema file, not duplicated into
prose in `program.md` or `SKILL.md`.

---

## 22. Migration / Compatibility

**Enumerated risk list. TARGET DESIGN unless marked otherwise.**

- **Existing v3 sessions**: sessions created under the current `bbb_autoresearch_execution_plan.v2`
  contract have history in `var/autoresearch/*/iterations/*/execution_plan.json`. A new narrow
  contract must be a new, additively-versioned artifact/schema, not a breaking replacement of the
  existing one.
- **`execution_plan.v2` history**: resume/recovery code paths read `execution_plan.json` directly
  (**CONFIRMED CURRENT FACT**: `scripts/autoresearch_supervisor.py:2384, 2426, 2487` all
  `load_json(iteration_root / "execution_plan.json")` or equivalent path construction) — these paths
  must continue to work for old sessions unchanged, meaning a dual-read strategy (recognize both old
  full-form and new materialized-form `execution_plan.json` — the *materialized* file, not the new
  `scientific_proposal.json`, remains at the same path/shape a resumed old session expects) is
  required, not a hard cutover.
- **Schema versioning**: a `v3` `execution_plan` schema id (or a wholly separate `$id` for
  `scientific_proposal`) is the natural mechanism, consistent with the existing `contract_version`
  const-field pattern used throughout (`execution_plan.v2.schema.json:7`,
  `bbb_autoresearch_execution_plan.v2` etc.) — no new versioning mechanism needs to be invented.
- **Dual-read / migration strategy**: **OPEN QUESTION** — exact scope and duration of the dual-read
  window is not resolved here; depends on how many/which real sessions are in flight when this ships.
- **Artifact/output boundary allowed filenames**: **critical, explicit requirement**. The output
  boundary check (`scripts/autoresearch_supervisor.py:837-862`) is generic — it is parameterized by
  whatever `result_path` the stage runner passes in, not hardcoded to the literal string
  `execution_plan.json` (verified by re-reading the function body: it compares against a
  `result_path` variable throughout). This means a new `scientific_proposal.json` stage call can, in
  principle, simply pass a different `result_path` value and the existing generic boundary logic
  applies correctly with no special-casing needed. However, this **must** be explicitly verified and
  covered by a new test before shipping — do not assume it works correctly for the new filename
  without a dedicated test, given that the exact failure class that just hard-stopped the Qwen smoke
  (`unexpected=['baseline_spec.json']`) is precisely "worker wrote to an unrecognized filename." A
  new stage that expects `scientific_proposal.json` and receives a wrongly-named file must fail
  exactly as strictly as today — no weakening of unexpected-file protection is acceptable.
- **Journal/event derivation**: `journal_event.v3` schema fields such as `parameter_axes` and
  `window_policy` likely currently derive from the full worker-authored `canonical_request`. If the
  harness now constructs `canonical_request`, the journal-writer must read from the
  materialized/frozen plan, not from worker output directly — this is a small pipeline wiring change
  beyond "add a schema," not purely additive.
- **Deterministic candidate identity**: if `candidate_id` becomes harness-generated (Section 15,
  step 4), uniqueness/stability within a batch must be guaranteed by the generation scheme —
  currently guaranteed only by the worker's own regex-constrained string choice.
- **Materializer provenance**: see Section 18 — open question on whether materializer version needs
  recording.
- **Supervisor recovery paths**: `scripts/autoresearch_supervisor.py:2384/2426/2487` recovery/resume
  logic reads `execution_plan.json` — as noted above, this remains compatible as long as the
  materialized artifact continues to be written at the same path with the same schema shape old
  resume code expects (or resume code is updated in lockstep — implementation detail, not resolved
  here).
- **Old worker profiles**: `claude-sonnet46, codex-gpt56-sol, glm52-opencode` currently use the full
  interface; Section 20 requires them to migrate to the same new interface as `qwen35-local`, not
  remain on a permanently separate path.
- **Tests**: **CONFIRMED CURRENT FACT** — `tests/test_autoresearch_stage_contract.py` (999 lines)
  hand-constructs full `raw_spec`/candidate fixtures and validates them through
  `_strip_allowed`/`validate_stage_request` today; this is the primary regression safety net a
  materializer must not break — its assertions should continue to pass unchanged against
  materializer-produced output, since the materializer targets the exact same validated shape.
  `tests/test_autoresearch_supervisor.py` (74 tests total alongside worker-profile tests, confirmed
  passing this session) covers planning/interpretation prompt rendering, freeze/resume flows, and
  worker-identity wiring — new materializer-specific unit tests are additive to this suite, not a
  replacement for it.
- **OpenSpec impact**: this change touches worker-facing contracts formally specified by
  `openspec/changes/bbb-autoresearch-stage-contract-v1/` (design.md/proposal.md/tasks.md) and
  `openspec/changes/autoresearch-frozen-control-phased-discovery-v1/`
  (design.md/proposal.md/tasks.md) — both confirmed present and read as part of this review. A new
  OpenSpec change proposal is required alongside (not replacing) these, since it changes the
  worker-facing output contract those changes established. Do not silently supersede prior OpenSpec
  changes without an explicit new change document.
- **Status tooling**: any CLI/status tooling that inspects `execution_plan.json` shape (not audited
  in depth in this pass — **DEFERRED**, flag for Phase 1/2 implementation to check) needs review for
  compatibility.
- **HOST smoke procedures**: `scripts/autoresearch_run_host.sh` is the existing canonical entrypoint
  (confirmed unchanged shape: `init|run` subcommands delegating to `autoresearch_init.py`/
  `autoresearch_supervisor.py`) and requires no change — it remains the correct invocation surface
  for both legacy and new-interface sessions.

---

## 23. Controlled Delivery Plan

**TARGET DESIGN — a starting sequence, explicitly adjustable to the actual dependency graph
discovered during implementation, not a fixed commitment.** Every phase item below carries the same
constraints: small, independently testable, fail-closed, no scope expansion beyond its stated goal,
no production Research Service / Strategy Engine / Market Data Service change unless a concrete
blocker proves one is required.

- **Phase 0** — freeze this master plan; open the corresponding OpenSpec change proposal/design
  (Section 22's OpenSpec requirement) before any code.
- **Phase 1** — A_CONTROL deterministic materialization (resolve the Option A/B open question from
  Section 9 as part of this phase's own design step).
- **Phase 2** — B1_WIDTH scientific proposal schema + materializer.
- **Phase 3** — B2_LOOKBACK scientific proposal schema + materializer (should be near-mechanical
  given B1/B2 symmetry, Section 11).
- **Phase 4** — migration/provenance/recovery hardening (Section 22 items, Section 18/19 designs
  made concrete).
- **Phase 5** — controlled HOST smoke on a strong worker (e.g. `claude-sonnet46` or
  `glm52-opencode`) — isolates materializer correctness from worker capability; a strong model
  failing here would indicate a materializer bug, not a worker limitation.
- **Phase 6** — controlled HOST smoke on `qwen35-local` — the original motivating question: can this
  model do the scientific reasoning once freed from file-contract mechanics.
- **Phase 7** — B3 geometry design (Section 12), as its own checkpoint, informed by real B1/B2
  production evidence.
- **Phase 8** — B3 implementation.
- **Phase 9** — evaluate the one-call interpretation→next-proposal lifecycle question (Section 13),
  informed by real evidence from Phases 2-6 on whether fresh planning calls diverge meaningfully
  from prior interpretation proposals.
- **Phase 10** — later `C_ENTRY_REGION_SELECTION`/`D_EXIT_GEOMETRY` stage design, only when
  explicitly undertaken as its own effort (these remain `PROVISIONAL_STAGES`, Section 5).

---

## 24. Testing Strategy

**TARGET DESIGN.**

- **Existing regression safety net, unchanged**: `tests/test_autoresearch_stage_contract.py` (999
  lines, hand-constructed `raw_spec`/candidate fixtures validated via `_strip_allowed`/
  `validate_stage_request`) and `tests/test_autoresearch_supervisor.py` (prompt rendering,
  freeze/resume, worker-identity wiring; 74/74 passing this session alongside worker-profile tests)
  continue to run unmodified against materializer-produced output — since the materializer targets
  exactly the shape these tests already validate, they function as an independent correctness check
  on the new code without needing to be rewritten for it.
- **New materializer unit tests**: proposal → exact expected `raw_spec`/candidate, mirroring the
  hand-constructed fixtures already present in `test_autoresearch_stage_contract.py` — i.e. for a
  given scientific proposal input, assert the materializer's output matches byte-for-byte (after
  canonical JSON normalization) what a correct full-form worker would have produced for the
  equivalent scientific choice.
- **Reused validation, not reimplemented**: `_strip_allowed`/`validate_stage_request` remain the
  independent last-line defense (Section 17) — no parallel validation logic should be built inside
  the materializer itself; if the materializer's output fails `validate_stage_request`, that is
  surfaced as a materializer bug (failure class 2, Section 19), not silently patched around.

---

## 25. Smoke Strategy

**TARGET DESIGN.** Mirrors Phases 5-6 (Section 23): a strong-worker HOST smoke first, to isolate any
materializer defect from worker capability limitations, followed by a `qwen35-local`-specific HOST
smoke to directly answer the question this whole effort originated from — whether Qwen3.5:9b can
produce sound scientific proposals once freed from full-JSON materialization mechanics.
`scripts/autoresearch_run_host.sh` remains the unchanged canonical entrypoint for both smokes
(confirmed this session: `init`/`run` subcommands, environment variables for
`BBB_AUTORESEARCH_LAUNCH_PROFILE`, service URLs, artifact/config roots — no changes needed to this
script for either smoke).

---

## 26. Risks / Open Questions

Consolidated list of every item tagged **OPEN QUESTION** above:

- A_CONTROL: minimal-LLM-call (Option A) vs no-LLM-call (Option B) — Section 9.
- B1/B2 proposal `values` representation: explicit list only, or also range/step description —
  Section 10.
- Planning/interpretation one-call vs two-call lifecycle — Section 13, requires empirical evidence
  from real sessions, not resolvable by code inspection alone.
- Materializer architectural placement (new module vs extension of
  `autoresearch_stage_contracts.py`) — Section 15.
- `candidate_id` deterministic generation scheme ownership and exact algorithm — Sections 15, 22.
- `accounting`/`execution` policy defaults source (programme-level config vs hardcoded harness
  constant) — Section 15; related: whether these fields ever become genuine per-experiment
  scientific choices in later stages (C_ENTRY_REGION_SELECTION / D_EXIT_GEOMETRY, per
  `program.md:114-117`'s note that exit-geometry economics become primary only in that later
  phase) is itself an open question, since those stages are currently provisional/undefined.
- Materializer version/provenance recording necessity — Section 18.
- Dual-read migration window scope/duration for old-vs-new `execution_plan.json` shape — Section 22.
- B3 geometry representation — Section 12, entire section is the open question, deliberately
  deferred to its own Phase 7 checkpoint.
- Status tooling compatibility with the new artifact shape — Section 22, not yet audited.

---

## 27. Non-Goals

Explicitly not done, and not to be done, as part of this document or this pass:

- No production code changes.
- No schema changes.
- No supervisor changes.
- No new materializer implementation.
- No worker-profile changes.
- No new HOST smoke run.
- No implementation commits.
- No `C_ENTRY_REGION_SELECTION`/`D_EXIT_GEOMETRY` stage design (remain `PROVISIONAL_STAGES`,
  untouched).
- No change to `CLAUDE.md`, `SKILL.md`, or `program.md` content today — the documentation-layering
  principle (Section 21) is a stated target for future alignment, not an action taken in this pass.

---

## 28. Definition of Done for this architecture

High-level completion criteria for the target architecture described in this document (not for this
document itself, which is complete on being written):

- Stage-scoped `scientific_proposal` contracts exist for A_CONTROL (if Section 9 resolves to
  requiring one), B1_WIDTH, and B2_LOOKBACK.
- A deterministic materializer produces an `execution_plan.json` that is valid under the existing,
  unchanged `validate_stage_request`/`_strip_allowed` path — i.e. materialized output is
  indistinguishable in effect from what a correct full-form worker would have produced for the same
  scientific choice.
- The existing validation/freeze/execution path (Section 17) is unchanged and its existing test
  suite still passes unmodified.
- A_CONTROL either requires no planning LLM call, or requires only the documented minimal one
  (Section 9 resolved, not left ambiguous).
- B1/B2 workers, across every worker profile (Section 20 — no profile-specific branching), no longer
  author `raw_spec`, component identity, or `fixed_parameters`.
- The provenance chain (Section 18) allows tracing an executed experiment back to the specific
  `scientific_proposal` that caused it.
- The existing test suite (`test_autoresearch_stage_contract.py`, `test_autoresearch_supervisor.py`,
  `test_autoresearch_worker_profiles.py`) plus new materializer-specific unit tests are all green.
- A `qwen35-local` HOST smoke reaches real interpretation for at least one of B1 or B2 — succeeding
  or failing at that point on the quality of its scientific reasoning, not on file/schema mechanics.
  (Whether the scientific reasoning itself is judged adequate is a separate, later evaluation — not
  part of this architecture's definition of done, which is about reaching that evaluation point at
  all.)

---

## 29. Recommended Next Implementation Step

The single concrete, small, low-risk first step: **open an OpenSpec change proposal for the
A_CONTROL-no-planning-LLM design (Phase 1, Section 23)**.

Rationale: this is the highest-confidence, lowest-risk finding in the entire review. It requires
resolving only one open question (Section 9's Option A vs Option B), touches no existing
multi-dimension scientific-proposal schema design (B1/B2's schema, still partially open per Section
26, is not a prerequisite for A_CONTROL), and is bounded by code already fully confirmed today:
zero numeric/candidate decisions exist for A_CONTROL (`STAGE_DIMENSIONS["A_CONTROL"] == ()`), exactly
one candidate is enforced (`scripts/autoresearch_stage_contracts.py:415-416`), and the reference
strategy is already a pure deep-copy with no per-value override mechanism
(`reference_strategy`, `:308-317`). This phase can proceed and be fully validated against the
existing test suite (Section 24) before any B1/B2 scientific-proposal schema needs to be finalized,
making it a genuinely independent, low-risk first slice of the larger architecture.
