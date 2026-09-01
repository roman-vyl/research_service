# bbb-autoresearch-v1 Delta Specification

## MODIFIED Requirements

### Requirement: Immutable evaluator boundary

An active worker SHALL NOT modify any tracked repository file or create an untracked file outside
its stage-specific allowed output set. A worker SHALL NOT execute or substitute the canonical
research evaluator, access or copy a raw market database, start Engine/MDS services, monkeypatch
imports or HTTP clients, install/synchronize dependencies, or repair its environment to bypass a
canonical execution failure. The supervisor SHALL inspect staged, unstaged, untracked, and
stage-output paths before and after each worker and hard-stop fail-closed without resetting
evidence.

Only the supervisor-owned execution stage SHALL invoke the existing canonical batch adapter with
authoritative cwd, argv, Research runtime environment, canonical artifact root, and required
Engine/MDS connectivity. Provider-specific permissions, rules, hooks, and sandbox settings MAY
provide defense in depth but SHALL NOT be required for correctness.

#### Scenario: Production source mutation

- **WHEN** a worker changes a tracked evaluator file
- **THEN** the supervisor records the path, hard-stops, and does not accept the result.

#### Scenario: Session-local execution substitute

- **WHEN** a worker creates a local evaluator, Engine/MDS runtime, raw market-database copy,
  `sitecustomize` or other import/client shim, proxy execution path, dependency lock, or environment
  self-repair output
- **THEN** it cannot become experiment truth and the stage hard-stops without launching or adopting
  the substitute.

#### Scenario: Provider policy is absent

- **WHEN** a CLI provider has no hook or command rule prohibiting a dangerous action
- **THEN** supervisor-owned execution and receipt validation still prevent that action's output
  from becoming accepted canonical experiment truth.

### Requirement: Session-scoped mutation

Autonomous runtime files SHALL live under `var/autoresearch/<session_id>/`, and each worker stage
SHALL have an explicit output allowlist within its iteration directory. Supervisor-owned prompts,
logs, frozen requests, canonical execution outputs, receipts, and control metadata SHALL remain
distinguishable from worker-authored outputs and SHALL be checked for mutation before acceptance.
Tracked infrastructure, unrelated OpenSpec changes, and the domain skill SHALL remain immutable
during a session.

#### Scenario: Planning output only

- **WHEN** a planning worker completes normally
- **THEN** only its versioned plan and declared supplementary analysis are accepted as worker
  outputs; executable/importable code, databases, service helpers, dependency files, symlinks, and
  changes to supervisor-owned files are rejected.

#### Scenario: Interpretation output only

- **WHEN** an interpretation worker completes normally
- **THEN** only its versioned iteration result and declared supplementary analysis are accepted as
  worker outputs, and canonical request/result/receipt inputs remain byte-identical.

### Requirement: Fresh worker per logical iteration

One logical research iteration SHALL consist of a fresh planning process, at most one
supervisor-owned canonical execution for the accepted request, and a fresh interpretation process.
The two worker processes SHALL use one provider-agnostic AgentRunner contract and represent one
autonomous researcher separated around the immutable execution boundary, not independent planner
and interpreter research roles. State and journal SHALL advance only after final interpretation is
validated.

#### Scenario: Normal brokered iteration

- **WHEN** planning produces a valid canonical request
- **THEN** the supervisor freezes and executes that request, supplies receipt-bound canonical
  evidence to a fresh interpretation process, validates its result, and atomically commits one
  journal row and one state advancement.

#### Scenario: Codex and Claude providers

- **WHEN** either Codex, Claude Code, or another supported CLI is selected by the operator
- **THEN** it receives the same planning/interpretation contracts and cannot change canonical
  execution ownership.

### Requirement: Existing batch path only

The planning worker SHALL formulate hypotheses, candidates, grids, and one immutable canonical
`BatchExperimentRequest`, but SHALL NOT execute it. The supervisor SHALL be the sole owner of
invoking the existing `scripts/autoresearch_execute_batch.py` adapter, which SHALL continue to use
current live config validation, `RunBatchExperiment`, canonical per-run persistence, and
`PersistBatchExperiment`. AutoResearch SHALL NOT implement simulation, accounting, metric
derivation, direct worker-owned MDS/Strategy Engine research execution, local service substitutes,
or a second summary format.

Before accepting an interpretation, the supervisor SHALL verify a supervisor-owned execution
receipt and the canonical request/summary/manifest identity, summary hash, candidate identities and
counts, completed run IDs, and shared completed-candidate market-data hash. It SHALL resolve the
reported path and require the exact canonical `<Settings().artifacts_root>/batches/<experiment_id>`
location without traversal or symlink escape. Filesystem location and bundle integrity without a
valid receipt SHALL be insufficient.

#### Scenario: Valid batch experiment

- **WHEN** a worker plans a justified valid batch
- **THEN** the supervisor runs the existing canonical adapter and every successful candidate is a
  canonical persisted run referenced by the final journal.

#### Scenario: Worker directly calls Engine or MDS

- **WHEN** a worker claims research evidence obtained through direct Engine/MDS execution, a raw
  market store, or any non-supervisor execution
- **THEN** that evidence cannot satisfy the experiment contract or be accepted as canonical truth.

#### Scenario: Plausible bundle without receipt

- **WHEN** a worker creates an externally plausible request/summary/manifest bundle, including at a
  canonical-looking path
- **THEN** the supervisor rejects it because no matching supervisor-owned execution receipt exists.

#### Scenario: Canonical dependency unavailable

- **WHEN** live validation, Strategy Engine, MDS, the Research evaluator, or canonical persistence
  required by the supervisor-owned executor is unavailable
- **THEN** execution fails closed according to session policy and no worker receives authority to
  construct a fallback.

### Requirement: Durable research continuity

`state.json` SHALL remain a compact atomically published snapshot and `journal.jsonl` SHALL remain
append-only. Agent chat history SHALL NOT be authoritative. Durable iteration control SHALL also
record monotonic planning, frozen-request, execution-receipt, interpretation, and commit stages with
the hashes required for idempotent recovery. All persisted contracts SHALL be versioned.

#### Scenario: Crash after executor completion

- **WHEN** the canonical executor completed and a valid receipt and artifacts exist but
  interpretation was not committed
- **THEN** restart reuses that execution, launches only a fresh interpretation attempt, and does not
  run the batch again.

#### Scenario: Crash after interpretation

- **WHEN** a valid interpretation exists but journal append or state replace did not complete
- **THEN** restart revalidates the frozen request, receipt, artifacts, and interpretation and
  completes the journal/state commit idempotently without rerunning execution.

#### Scenario: Crash during ambiguous executor outcome

- **WHEN** execution intent exists but neither a valid receipt nor a complete verified canonical
  bundle proves successful completion
- **THEN** restart fails closed rather than automatically creating a second execution for the same
  frozen request.

### Requirement: Bounded failure, cancellation, and budgets

Planning and interpretation process crashes or malformed outputs SHALL retry independently only to
their configured limits. A planning failure before a valid request SHALL NOT launch canonical
execution. A worker retry after request freeze SHALL NOT modify that request or create another batch
execution. Canonical executor/dependency failure SHALL follow fail-closed execution policy rather
than worker self-repair. Cancellation and iteration/wall-clock budgets SHALL remain deterministic.

#### Scenario: Planning worker crash

- **WHEN** planning attempts fail before a valid request is frozen
- **THEN** only a fresh planning process may retry within budget and no canonical experiment is
  executed.

#### Scenario: Interpretation worker crash

- **WHEN** interpretation fails after a valid execution receipt exists
- **THEN** only interpretation retries with the same immutable request and evidence; the canonical
  batch is not rerun.

#### Scenario: Cancellation before next stage

- **WHEN** cancellation is observed before planning, execution, interpretation, or the next logical
  iteration
- **THEN** the supervisor transitions cleanly without launching the next stage.

## ADDED Requirements

### Requirement: Immutable execution request

Every compute-bearing logical iteration SHALL persist one validated, normalized canonical request
before execution. The supervisor SHALL bind it to session ID, iteration number, baseline repository
SHA, candidate IDs/order, and SHA256. After execution begins, any request change SHALL invalidate
the iteration and SHALL NOT be reconciled by worker interpretation.

#### Scenario: Request changed after execution

- **WHEN** the canonical request bytes or normalized content differ from the request hash recorded
  before execution
- **THEN** the receipt and final interpretation are rejected and no state/journal commit occurs.

### Requirement: Minimal trusted execution receipt

For each supervisor-owned canonical execution, the supervisor SHALL atomically persist a versioned
receipt binding session ID, iteration number, baseline repository SHA, canonical request SHA256,
experiment ID, ordered candidate IDs, canonical executor identity and baseline, executor exit
status, canonical adapter-output hash, exact canonical batch path, and required canonical artifact
hashes. The receipt SHALL be mechanically recomputable from supervisor-controlled inputs and
canonical artifacts and SHALL NOT rank or interpret candidates.

#### Scenario: Receipt or result tampered

- **WHEN** a receipt field, adapter output, request, canonical artifact, experiment identity,
  candidate order, run ID, count, or hash is missing or inconsistent
- **THEN** the supervisor rejects the interpretation fail-closed before journal/state commit.

#### Scenario: Worker-authored receipt

- **WHEN** a worker supplies a receipt without the matching supervisor execution stage
- **THEN** the document has no authority and cannot make its evidence canonical.

### Requirement: Research freedom outside execution ownership

Workers SHALL continue to own hypotheses, information-gain choices, candidate/grid construction,
response topology, side classification, competing explanations, supplementary analysis, quality
assessment, negative-result interpretation, and the next research question. Supplementary analysis
SHALL NOT create or replace canonical experiment truth. The supervisor SHALL remain mechanical and
SHALL NOT rank candidates, choose a winner, or reconstruct scientific interpretation.

#### Scenario: Supplementary artifact analysis

- **WHEN** an interpretation worker derives a topology or concentration explanation from receipt-
  bound canonical evidence
- **THEN** it may write declared supplementary analysis and report the finding without executing
  another experiment or changing canonical facts.

#### Scenario: Negative canonical result

- **WHEN** the supervisor-owned canonical batch is losing, flat, hypothesis-rejecting, or otherwise
  scientifically negative
- **THEN** the worker may preserve it as informative evidence under the unchanged Research Quality
  Policy, and the supervisor performs no scalar winner selection.
