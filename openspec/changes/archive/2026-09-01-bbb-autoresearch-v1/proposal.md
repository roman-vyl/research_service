## Why

Research Service already owns a canonical, reproducible batch evaluator, but an operator must still
manually carry knowledge and initiate each next experiment. BBB AutoResearch v1 adds a small local
control plane that can continue a hypothesis-driven research program across fresh agent contexts
without allowing the researcher to modify the system that evaluates it.

## What Changes

- Add versioned, durable session/iteration/journal contracts under ignored `var/autoresearch/`.
- Add init/status/cancel CLIs and a mechanical supervisor with bounded retries, budgets, restart,
  atomic state, append-only journal, and a fail-closed git mutation guard.
- Add an operational constitution and fresh-worker prompts that defer EMA methodology to the
  existing domain skill and prohibit scalar-leaderboard optimization.
- Add a thin standalone adapter that validates candidates and invokes only the existing
  `RunBatchExperiment` → `PersistBatchExperiment` lifecycle.

## Capability

### New Capability

- `bbb-autoresearch-v1`: autonomous research orchestration above the immutable canonical evaluator.

## Impact

Only tracked orchestration, documentation, schemas, tests, and this active OpenSpec change are
added. Production evaluator packages under `src/research_service/` are unchanged. There is no new
HTTP route, service, database, dependency, strategy semantic, or deployment behavior.
