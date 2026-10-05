## Context

BBB AutoResearch v1 already has the right scientific split: a mutable autonomous researcher works
above an immutable evaluator, preserves durable evidence, and cannot select a winner by scalar
metric. The implementation also validates that a reported batch lives at the exact current
`<Settings().artifacts_root>/batches/<experiment_id>` path and that request, summary, manifest,
hashes, candidate identities/counts, run IDs, and market-data hashes agree.

The missing boundary is process ownership. The current fresh worker both decides what to test and
runs `scripts/autoresearch_execute_batch.py`. A post-process Git guard and artifact verifier cannot
prevent that process from changing cwd/environment, choosing another artifact root, synchronizing
dependencies, monkeypatching imports or HTTP clients, copying a market database, or starting a
substitute service. Smoke tests demonstrated these failures with both Codex and Claude Code, so the
problem is provider-independent.

Karpathy-style autoresearch keeps the researcher mutable and the evaluator immutable. BBB's
supervisor-brokered execution is the local adaptation of that same boundary: the researcher still
chooses hypotheses, candidates, grids, and interpretation, while the process that creates trading
truth is no longer mutable agent behavior. This is not a generic workflow engine: there is one
fixed planning/execution/interpretation protocol, one existing Research executor, no arbitrary DAG,
no queue, and no production orchestration service.

## Goals / Non-Goals

Goals:

- keep scientific decisions and interpretation with the autonomous worker;
- make canonical batch execution exclusively supervisor-owned;
- retain the existing Research evaluator and canonical artifact contracts;
- bind every accepted batch interpretation to one immutable request and one trusted execution
  receipt, while accepting non-batch interpretations against their frozen plan without a receipt;
- remain provider-agnostic across Codex, Claude Code, and future CLI agents;
- recover deterministically without repeating a valid completed batch;
- preserve exact Research Quality Policy semantics and v1/v2 compatibility decisions unless a
  new enclosing execution contract is explicitly introduced.

Non-goals:

- rewriting Research, Strategy Engine, MDS, accounting, execution, or backtest semantics;
- changing quality thresholds, phase lifecycle, side policy, or promotion decisions;
- introducing planner and interpreter as independent researcher roles;
- requiring Claude hooks, Codex rules, or provider-specific prompts for correctness;
- building an OS security platform, remote workflow engine, scheduler, queue, or distributed agent;
- building signatures, PKI, remote attestation, or another complex cryptographic system;
- creating another evaluator or batch summary format.

## Decisions

### 1. One logical iteration has three mechanical stages

One research iteration remains the unit that advances state and appends one journal row:

1. a fresh planning invocation reads program, skill, state, journal, and relevant contracts;
2. it emits one planning result containing the hypothesis and selected action and, when batch
   compute is justified, one canonical batch request;
3. the supervisor validates and freezes the plan and its optional request;
4. for `batch` only, the supervisor invokes the existing canonical adapter and creates a receipt;
5. a fresh interpretation invocation reads the frozen plan, state, and applicable evidence;
6. it emits the existing quality-aware iteration result;
7. the supervisor validates and commits journal/state atomically as today.

The two CLI processes are technical isolation around one autonomous researcher. They are not two
agents with competing goals, independent memory, or separate scientific authority.

Planning may also return a justified `artifact_diagnostic`, `terminal`, or `hard_stop` action. For
each non-batch action the supervisor freezes the plan, creates no execution intent or receipt,
launches no canonical executor, and starts a fresh interpretation worker. That worker emits the
applicable existing iteration-result contract, after which the supervisor performs the same
mechanical validation and journal/state commit. The supervisor never promotes planning output
directly into scientific interpretation. Planning and interpretation remain two technical
invocations of one logical autonomous researcher.

An `artifact_diagnostic` interpretation may use only permitted existing canonical evidence and
artifacts. It may not create a new experiment result or make non-canonical facts authoritative.
`terminal` and `hard_stop` likewise pass through the ordinary interpretation contract and status
validation; the absence of compute does not justify a synthetic receipt.

### 2. Planning produces a small immutable contract

Introduce `bbb_autoresearch_execution_plan.v1`. Its normative content is deliberately small:

- contract version, session ID, and iteration number;
- current phase;
- hypothesis, question, market-property proxy, and competing explanation;
- action: `batch`, `artifact_diagnostic`, `terminal`, or `hard_stop`;
- for `batch`, one document satisfying the current canonical `BatchExperimentRequest` contract;
- optional worker-authored explanatory metadata needed for later interpretation, without computed
  trading facts;
- hard-stop reason when applicable.

For `batch`, the supervisor validates exact identity, candidate ordering/uniqueness, configured
candidate budget, strategy/window comparability, and current live config validation through the
canonical execution path. It then writes the normalized request once and records its SHA256. After
freezing, any byte change invalidates the stage; the worker cannot replace a request and retain its
execution. For a non-batch action the whole normalized plan is frozen, but no canonical request,
execution intent, or execution receipt is created.

### 3. The supervisor owns canonical execution

For a valid batch plan the supervisor invokes exactly the existing
`scripts/autoresearch_execute_batch.py` adapter. That adapter continues to compose:

`ValidateStrategyConfig -> RunBatchExperiment -> PersistBatchExperiment`.

The supervisor, not either worker invocation, supplies:

- execution cwd and exact argv;
- the repository-baseline executor identity;
- the Research virtual environment/runtime;
- Engine and MDS endpoints;
- canonical `Settings().artifacts_root` and configs root;
- timeout, process exit capture, stdout/stderr paths, and retry policy.

Workers do not receive authority to substitute these values. A missing or failed canonical
dependency is an execution failure and follows fail-closed policy. It is never returned to a worker
as an invitation to install packages, copy a database, monkeypatch a client, start a service, or
construct a fallback evaluator.

This design does not create a new executor. It relocates ownership of the existing adapter call.

### 4. A minimal receipt establishes execution provenance

For a compute-bearing `batch` action, introduce `bbb_autoresearch_execution_receipt.v1`, written
only by the supervisor after canonical execution or deterministic recovery of its completed
artifact. It binds:

- `session_id` and `iteration_id`;
- baseline repository SHA;
- canonical request SHA256;
- experiment ID;
- candidate IDs in request order;
- executor identity (`scripts/autoresearch_execute_batch.py`) and baseline repository SHA;
- executor start/end timestamps and exit status;
- canonical adapter-output SHA256;
- exact canonical batch artifact path;
- canonical request, summary, and manifest SHA256 values.

The receipt is an integrity record, not a cryptographic attestation platform. Atomic supervisor
writes, immutable request/output hashes, process ownership, repository-baseline identity, and the
existing canonical bundle verifier are sufficient for this local capability. A receipt authored or
modified by a worker is invalid because the supervisor recomputes every field before acceptance.
For `artifact_diagnostic`, `terminal`, and `hard_stop`, a receipt is neither required nor permitted
to be synthesized because no canonical execution occurred.

### 5. Interpretation cannot redefine execution truth

Every action receives a fresh interpretation invocation. For `batch`, its prompt receives the
original normalized request, adapter output, receipt, state, and canonical evidence. For a
non-batch action, it receives the frozen plan, state, and only the existing canonical evidence
permitted by that action, with no adapter output or receipt. In both paths it may perform
supplementary analysis and owns topology, side scope, trade-offs, quality assessment, conclusion,
and next question. It may not execute another research experiment.

The final existing `bbb_autoresearch_iteration.v2` result remains the scientific result contract.
Before accepting a `batch` interpretation the supervisor mechanically requires:

- its experiment ID and candidate IDs/order equal the frozen request;
- its execution result equals receipt and canonical summary identities/counts/run IDs/hash;
- request and adapter-output hashes still equal the receipt;
- receipt fields recompute from the current baseline and canonical artifacts;
- existing provenance/integrity and Research Quality Policy validation pass.

Before accepting a non-batch interpretation the supervisor instead requires that its action,
identity, phase, and evidence references agree with the frozen plan, that no execution intent or
receipt exists, and that the applicable existing iteration and Research Quality Policy validation
passes. It performs no scientific interpretation in either path.

No receipt field authorizes the supervisor to infer topology, choose a candidate, rank metrics, or
replace worker interpretation.

### 6. AgentRunner is generic and stage-scoped

Define one internal `AgentRunner` boundary that accepts a stage name, prompt, result schema/path,
allowed inputs/outputs, timeout, and attempt index, and returns process exit/log metadata. The
runner command remains operator-supplied and provider-neutral. Codex, Claude Code, and future CLI
agents receive the same planning and interpretation contracts.

Provider permissions, rules, hooks, and sandbox configuration may reject dangerous behavior sooner,
but correctness never depends on them. The supervisor accepts only the stage's contract and
allowlisted outputs; provider-authored artifacts cannot become experiment truth.

### 7. Worker filesystem and behavior are fail-closed

The planning worker may write only its planning result and explicitly declared supplementary
analysis. The interpretation worker may write only its interpretation result and explicitly
declared supplementary analysis. Supervisor-owned prompt/log/metadata/request/output/receipt files
are not worker outputs.

Unexpected executable/importable code, dependency locks, environment files, databases, sockets,
symlinks, service helpers, or changes to frozen supervisor files fail the stage. The operational
constitution explicitly prohibits:

- direct Engine/MDS research execution or raw market-store reads/copies;
- alternate evaluators and local service/runtime substitutes;
- `sitecustomize`, import hooks, HTTP/client monkeypatching, and proxy execution;
- `uv`, `pip`, other package/dependency managers, or environment self-repair;
- fallback execution after canonical dependency failure.

This is layered enforcement: prompts state worker obligations; AgentRunner/provider policies can
stop obvious violations early; supervisor manifests and hashes determine acceptance; only the
supervisor-owned executor can create accepted experiment truth.

### 8. Crash, retry, and resume are stage-aware

The supervisor persists a small iteration control record with monotonic stages and hashes:

- `planning_pending`: no valid plan exists. A failed planning process may retry with a fresh worker
  within its configured worker-attempt budget. No executor is launched.
- `request_prepared`: for `batch`, a valid normalized request and its hash are durable; no execution
  receipt is committed. The supervisor writes an execution-intent record before launching the
  adapter.
- `non_batch_plan_prepared`: for `artifact_diagnostic`, `terminal`, or `hard_stop`, the normalized
  plan is durable; no execution intent or receipt exists. Resume proceeds directly to a fresh
  interpretation invocation.
- `execution_completed`: a valid receipt and canonical artifacts exist; interpretation is not yet
  committed. Resume never runs the batch again and may retry only a fresh interpretation worker.
- `interpretation_prepared`: a valid interpretation exists, but journal/state commit may be
  incomplete. Resume revalidates the frozen plan and interpretation plus, for `batch` only, the
  request, receipt, and artifacts, without running either worker or executor again.
- `committed`: journal contains the iteration and state has advanced.

Recovery rules:

1. A crash before a valid plan retries planning only.
2. A crash after a non-batch plan is frozen resumes interpretation directly; it never creates an
   execution intent or receipt and never launches the executor.
3. A crash after a batch request freezes but before execution intent may launch the executor once.
4. If execution intent exists and the exact canonical bundle is complete and passes all current
   checks, the supervisor deterministically reconstructs/commits the receipt and does not rerun.
5. If execution intent exists but no complete valid bundle proves completion, the outcome is
   ambiguous and fails closed rather than automatically creating a second experiment execution.
6. A normal executor non-zero exit or unavailable canonical dependency hard-stops according to the
   execution failure policy; workers cannot provide a fallback.
7. A crash after receipt commit retries interpretation only.
8. A crash after interpretation validation but before journal append revalidates and commits it;
   the non-batch path revalidates without inventing execution provenance.
9. Existing `(session_id, iteration_id)` journal detection recovers a crash between journal append
   and atomic state replace without duplicate journal rows.

Planning and interpretation attempts have separate metadata and retry budgets. No worker retry can
change a frozen request or cause another execution for that request.

### 9. Existing BBB mechanisms are reused

The APPLY phase reuses rather than replaces:

- session identity, baseline SHA, budgets, cancellation, and terminal-state validation;
- fresh-process stdout/stderr/attempt metadata;
- atomic JSON writes and append/fsync journal persistence;
- `_journal_has_iteration()` crash recovery;
- canonical `BatchExperimentRequest` validation;
- `scripts/autoresearch_execute_batch.py` and current application composition;
- `_verify_batch_artifact()` path, traversal, symlink, identity, count, hash, run-ID, and shared
  market-data-hash checks;
- v1 compatibility behavior and quality-aware v2 state/iteration/journal contracts;
- Research Quality Policy enforcement and mechanical promotion persistence;
- repository HEAD/branch and tracked/untracked mutation guards.

## Contract and Compatibility Notes

- Add planning, receipt, and iteration-control schemas rather than silently expanding existing v1
  or v2 documents.
- Keep `bbb_autoresearch_iteration.v2`, `bbb_autoresearch_state.v2`, and
  `bbb_autoresearch_journal.v2` scientific meanings unchanged unless implementation proves an
  explicit new enclosing version is necessary. Any such need requires an explicit version and no
  silent migration.
- Existing legacy sessions cannot be silently converted to brokered execution because they lack a
  frozen request/receipt stage. Adoption is operator-driven through a newly initialized session at
  the implementation baseline.
- Archived OpenSpec changes remain immutable historical records; this change modifies the canonical
  capability through a new delta spec.

## Risks / Trade-offs

- Two CLI invocations add latency and token cost, but remove provider control over experiment
  truth and make interpretation retryable without recompute.
- A crash during executor launch can be ambiguous. Failing closed when neither receipt nor a
  complete canonical bundle proves completion is safer than silently duplicating a batch.
- Filesystem manifests and provider rules do not constitute an OS security platform. Correctness
  rests on supervisor-owned execution and receipt validation; stronger sandboxing remains optional
  defense in depth.
- Supplementary analysis remains intentionally flexible, but it cannot supply canonical trading
  facts, replace receipt-bound batch evidence, or create new truth during an artifact diagnostic.
