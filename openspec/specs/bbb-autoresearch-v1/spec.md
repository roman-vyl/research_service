# bbb-autoresearch-v1 Specification

## Purpose
Define a local autonomous research-control capability. It is not a strategy evaluator, backtester,
accounting engine, market-data engine, strategy component, or scalar optimizer.
## Requirements
### Requirement: Immutable evaluator boundary

An active worker SHALL NOT modify any tracked repository file or create an untracked file outside
its concrete ignored session root. The supervisor SHALL inspect staged, unstaged, and untracked
paths before and after each worker and hard-stop fail-closed without resetting evidence.

#### Scenario: Production source mutation

- **WHEN** a worker changes a tracked evaluator file
- **THEN** the supervisor records the path, hard-stops, and does not accept the result.

### Requirement: Session-scoped mutation

Autonomous runtime files SHALL live under `var/autoresearch/<session_id>/`. Tracked infrastructure,
unrelated OpenSpec changes, and the domain skill SHALL remain immutable during a session.

#### Scenario: Runtime output only

- **WHEN** a worker writes prompt/result/log/analysis files inside its session
- **THEN** the mutation guard permits them and no tracked output is created.

### Requirement: Fresh worker per iteration

The supervisor SHALL launch a fresh process for exactly one iteration, validate its structured
result after exit, and launch another fresh process only when continuation is valid. For the
`A_CONTROL` stage, the supervisor SHALL deterministically materialize that iteration's
`execution_plan.json` from frozen session and stage-contract state instead of launching a planning
worker process; the iteration's first worker process is its interpretation call. Every other stage,
and interpretation for every stage including `A_CONTROL`, SHALL continue to run as a fresh worker
process per this requirement unchanged.

#### Scenario: Autonomous continuation

- **WHEN** iteration N completes with a proposed next experiment
- **THEN** state advances atomically and a fresh process receives iteration N+1.

#### Scenario: A_CONTROL requires no planning worker

- **WHEN** the active stage for an iteration is `A_CONTROL`
- **THEN** the supervisor materializes that iteration's `execution_plan.json` deterministically from
  frozen session and stage-contract state and does not launch a planning worker process for it.

#### Scenario: A_CONTROL interpretation still runs as a fresh worker

- **WHEN** the `A_CONTROL` iteration's canonical execution completes
- **THEN** the supervisor launches a fresh worker process for interpretation of that result, and that
  worker reports the semantic fields (hypothesis, question, competing explanation, proposed next
  experiment) required of interpretation for every stage.

### Requirement: Durable research continuity

`state.json` SHALL be a compact atomically published snapshot and `journal.jsonl` SHALL be
append-only. Agent chat history SHALL NOT be authoritative. Both contracts SHALL be versioned.

#### Scenario: Restart after one iteration

- **WHEN** a supervisor restarts after iteration 1 committed
- **THEN** it reads state/journal intact and starts iteration 2 without rerunning iteration 1.

### Requirement: Knowledge rather than leaderboard

State SHALL preserve hypotheses, competing explanations, dimensions/ranges, response shapes,
regions, aggregate/long/short interpretations, explicit side asymmetry, explicit thinning risk,
temporal/regime concentration concern, other confounders, validation, unresolved boundaries, and
next questions. The worker SHALL report these semantic fields explicitly and the supervisor SHALL
persist them without deriving one from another. Infrastructure SHALL NOT select a candidate using
PF, PnL, or another scalar.

#### Scenario: Higher PF observed

- **WHEN** one candidate has higher PF
- **THEN** the supervisor performs no keep/discard decision; the domain worker interprets the
  multi-metric topology under its skill.

### Requirement: Domain policy and causal order

Every worker prompt SHALL require a complete read of the domain skill before acting. The operational
program SHALL reference rather than duplicate that methodology. A next step violating its causal
phase order SHALL hard-stop.

#### Scenario: Exit optimization before structural evidence

- **WHEN** the next required step would optimize exits before structural entry evidence
- **THEN** the worker reports a hard stop instead of executing it.

### Requirement: Existing batch path only

Experiments SHALL use current canonical candidate contracts, live config validation, `RunBatchExperiment`, canonical per-run persistence, and `PersistBatchExperiment`. AutoResearch SHALL NOT implement simulation, position sizing, an equity ledger, accounting, metric derivation, direct MDS/Strategy Engine research execution, or a second summary format. It SHALL inherit the canonical Research sizing semantics of each batch candidate. Before accepting a batch result, the supervisor SHALL verify the canonical request/summary/manifest identity, summary hash, candidate identities and counts, completed run IDs, and shared completed-candidate market-data hash against the worker result. Before reading that bundle, it SHALL resolve the reported path and require the exact canonical `<Settings().artifacts_root>/batches/<experiment_id>` location without traversal or symlink escape.

#### Scenario: Valid batch experiment

- **WHEN** a worker runs a justified batch
- **THEN** every successful candidate is a canonical persisted run whose quantities and equity chain were produced by Research Service
- **AND** the journal references the existing batch artifact and run IDs.

#### Scenario: Canonical batch reference mismatch

- **WHEN** a worker result disagrees with its canonical request, summary, or manifest
- **THEN** the supervisor rejects the result without recomputing trading metrics or sizing.

#### Scenario: Valid-looking bundle outside canonical storage

- **WHEN** a worker reports a structurally valid bundle below its session directory or another non-canonical path
- **THEN** the supervisor rejects it before reading bundle contents.

#### Scenario: AutoResearch does not select quantity

- **WHEN** AutoResearch constructs or interprets a candidate
- **THEN** it supplies no independent fixed/equity sizing choice and derives no quantity from research metrics.

### Requirement: Reproducible compact journal

Each accepted journal event SHALL record session/iteration/time/baseline, phase, hypothesis and
alternative, exact experiment/candidate IDs, window, strategy context, axes, assumptions, artifact,
run IDs, market-data hash, topology, conclusion, and next question, without dense trades.

#### Scenario: Inspect historical finding

- **WHEN** an operator reads a journal row
- **THEN** it can locate canonical detailed artifacts and reproduce the experiment context.

### Requirement: Bounded failure, cancellation, and budgets

Process crashes and malformed results SHALL retry only to the configured limit. Cancellation SHALL
be marker-based and clean. Iteration and wall-clock budgets SHALL stop deterministically.

#### Scenario: Repeated worker crash

- **WHEN** fresh worker attempts fail up to the configured limit
- **THEN** the session hard-stops and no failed output is accepted as a research finding.

#### Scenario: Cancellation before next worker

- **WHEN** an operator requests cancellation
- **THEN** the supervisor transitions to `cancelled` without launching another worker.

### Requirement: Hard-stop taxonomy

Hard stops SHALL include semantic mismatch, missing live capability, ambiguous/invalid contracts,
data-integrity/hash mismatch, evaluator inconsistency, repository mutation, repeated process
failure, budgets, cancellation, human-policy terminal conclusions, required production changes,
and causal-order violation. Normal phase completion SHALL continue autonomously.

#### Scenario: Ordinary phase completion

- **WHEN** a phase yields a meaningful next discriminating experiment
- **THEN** the supervisor launches the next worker without asking a human.
