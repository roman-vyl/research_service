## Context

Current code establishes the correct seam: `RunBatchExperiment` resolves one shared window, consumes
the streamed Strategy Engine batch, materializes and atomically persists one canonical run at a
time, derives the existing compact metrics, and restores request order. `PersistBatchExperiment`
then publishes the immutable batch request/summary bundle. There is no batch HTTP route, while
`create_app()` already builds both use cases and current live config validation.

External references were reviewed only for organization. Karpathy's
[autoresearch](https://github.com/karpathy/autoresearch) separates an immutable evaluator from a
mutable experiment, keeps experiment history, supplies a fixed `program.md`, and continues without
per-iteration approval. A public
[trading adaptation](https://github.com/nhocconan/AutoResearch-based-Trading-Strategy-Generation-and-Testing)
also makes its simulation/metrics immutable and persists failure history, but uses strategy-code
generation and scalar gates. BBB retains the immutability/history ideas and rejects code mutation,
its extra evaluator, and scalar ratcheting because current BBB contracts and the EMA research skill
require topology- and explanation-oriented knowledge.

## Goals / Non-Goals

Goals are fresh context per iteration, restartable durable continuity, repository-level evaluator
immutability, canonical batch reuse, information-gain experiment selection by the worker, and
mechanical validation by the supervisor.

Non-goals are distributed agents, parallel hypotheses, a dashboard, remote orchestration, scheduler,
queue, external database, production promotion, live trading, parameter optimization, model
training, evaluator changes, and code or skill self-modification.

## Decisions

1. **Scripts are the composition boundary.** V1 is a local CLI, not a production service. The thin
   batch adapter uses `create_app()`'s existing composition, current `ValidateStrategyConfig`,
   `RunBatchExperiment`, and `PersistBatchExperiment`. It contains no trading logic.
2. **Worker decides; supervisor enforces.** The supervisor never selects a hypothesis or compares a
   scalar metric. It validates process, contracts, budgets, paths, and transitions only.
3. **One process per attempt.** Every normal iteration and retry starts a new command. The worker
   reads program, skill, state, and journal and writes exactly one result before exiting.
4. **State is compact; journal is append-only.** Atomic temp-write/fsync/replace publishes state.
   Journal append is flushed/fsynced. Canonical artifacts retain dense truth.
5. **Fail-closed git guard.** Before and after a worker, unstaged, staged, and untracked paths are
   inspected. Only the concrete ignored session root is allowed. Any other path hard-stops without
   reset or deletion.
6. **Crash idempotency.** State iteration advances only after valid result → clean guard → journal
   append → atomic state write. Attempt metadata is durable in the iteration directory. A restart
   reuses the uncommitted iteration number, retains logs, and continues only within the remaining
   retry budget. If a crash occurs after journal append but before state replace, restart detects the
   journal's `(session_id, iteration_id)`, validates the retained `iteration_result.json`, and
   atomically advances state without launching another worker or appending a duplicate journal row.
   A journal row with a missing retained result fails closed as inconsistent recovery state.
7. **Flexible semantic phases.** State stores a string phase plus completed phases; EMA causal order
   is enforced by the worker's mandatory skill read and hard-stop policy, not a brittle generic enum.
8. **Operator-owned permissions and budgets.** The command is supplied by CLI/environment, parsed by
   `shlex`, executed without `shell=True`, and receives the prompt on stdin. No dangerous permission
   flag or small scientific grid limit is hardcoded.

## Risks / Trade-offs

The git guard is deterministic repository enforcement, not an OS security boundary. An operator
must still choose an appropriate agent sandbox. The supervisor cannot prove scientific correctness;
that belongs to the domain policy and canonical evaluator. Candidate semantic validation requires
live Strategy Engine availability, exactly like current Research config validation. A production
capability missing from the live catalog is a hard stop, not a reason to modify production code.
