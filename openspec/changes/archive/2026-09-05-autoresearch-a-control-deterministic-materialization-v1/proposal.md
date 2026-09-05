## Why

`A_CONTROL` is a frozen naked control strategy: `scripts/autoresearch_stage_contracts.py`
(`STAGE_DIMENSIONS`) allows zero semantic dimensions for this stage, and `validate_stage_request`
enforces exactly one candidate. There is no numeric or candidate-identity decision left for a
scientific worker to make at this stage today -- yet the current contract still requires a fresh
planning LLM process to hand-author a full `execution_plan.json` (component identity, `raw_spec`,
`candidate_id`, `experiment_id`, frozen `starting_strategy_sha256`, and the rest of the production
`BatchExperimentRequest` shape) purely by copying values the harness already knows deterministically
from `stage_contract` and session state.

A recent controlled HOST smoke with the `qwen35-local` worker profile
(`ema-anchor-host-smoke-qwen35-20260904200530`) demonstrated the cost of this: two full planning
attempts (~465s and ~684s) failed on file/schema materialization mechanics -- one produced no
`execution_plan.json` at all, the other wrote into the wrong file and the harness correctly
hard-stopped the session on an output-boundary violation -- without the worker ever reaching a
genuine scientific decision. `docs/AUTORESEARCH_SCIENTIFIC_WORKER_INTERFACE_MASTER_PLAN.md`
(sections 9 and 29) analyzed this architecture end to end and recommends, as the lowest-risk first
implementation step, removing the planning LLM call for `A_CONTROL` specifically: the stage has no
scientific content to elicit before execution, so the harness should materialize its
`execution_plan.json` directly from frozen session/stage_contract state, and invoke a worker for the
first time at interpretation of the control result -- where it proposes the first real `B1_WIDTH` or
`B2_LOOKBACK` scientific experiment.

## What Changes

- Deterministic harness materialization of the `A_CONTROL` `execution_plan.json` directly from
  frozen session state (`stage_contract.starting_strategy`, `bootstrap.json`,
  `research_quality_policy`) -- no planning worker process is launched for this one stage.
- **BREAKING** (normative, not implementation): the current `bbb-autoresearch-v1` spec's "Fresh
  worker per iteration" requirement states the supervisor launches a fresh process for exactly one
  iteration, implying a worker process at every iteration including planning. This change carves out
  an explicit, narrow exception: for `A_CONTROL` only, the supervisor materializes the plan itself
  and iteration 1's only worker invocation is interpretation.
- The worker's first invocation in any session remains interpretation of the `A_CONTROL` result,
  where it is still required to report hypothesis/question/competing-explanation framing for the
  control measurement and to propose the first real experiment -- this preserves "Knowledge rather
  than leaderboard" and "Domain policy and causal order" requirements unchanged; only the pre-
  execution planning call for this one stage is removed.
- No change to `B1_WIDTH`, `B2_LOOKBACK`, `B3_WIDTH_X_LOOKBACK`, or later provisional stages: all
  continue to require full-form planning exactly as today. This change is scoped strictly to
  `A_CONTROL`.
- No change to the `execution_plan.v2` schema shape, `batch_experiment_request.schema.json`, worker
  profiles, or the component catalog delivery path.
- No new scientific-proposal contract, no materializer for mutable-dimension stages, no B3 geometry
  design -- those are later master-plan phases (2-8), out of scope here.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `bbb-autoresearch-v1`: the "Fresh worker per iteration" requirement gains a narrow, explicit
  exception for `A_CONTROL`: the supervisor deterministically materializes the control iteration's
  `execution_plan.json` from frozen session/stage_contract state instead of launching a planning
  worker process; the fresh-process guarantee still applies to that iteration's interpretation call
  and to every worker process at every later stage.

## Impact

- `scripts/autoresearch_supervisor.py`: planning-stage dispatch must branch on `active_stage ==
  "A_CONTROL"` to skip the planning worker launch and invoke a new deterministic materialization
  path instead (implementation detail for design.md / a later implementation change -- not decided
  here).
- `scripts/autoresearch_stage_contracts.py`: `reference_strategy()`, `validate_stage_context()`, and
  `validate_stage_request()` already contain everything needed to construct the single `A_CONTROL`
  candidate; this change proposes reusing them from the materialization path rather than only from
  post-hoc worker-output validation.
- `autoresearch/prompts/planning.md`: no content change required for other stages; A_CONTROL simply
  stops being routed through this prompt.
- `openspec/specs/bbb-autoresearch-v1/spec.md`: delta to "Fresh worker per iteration".
- `openspec/changes/autoresearch-frozen-control-phased-discovery-v1/`: this change is a downstream
  refinement of that still-active (unarchived) change, which defined the current `A_CONTROL`/`B1`/
  `B2` stage semantics this proposal builds on; it does not modify or duplicate that change's scope.
- Existing regression safety net (`tests/test_autoresearch_stage_contract.py`,
  `tests/test_autoresearch_supervisor.py`) is expected to gain new coverage for the materialization
  path in the implementation change, but is not modified by this proposal itself.
- No production Research Service / Strategy Engine / Market Data Service change.
