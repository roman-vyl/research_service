## 1. Versioned handoff contracts

- [ ] Add exact JSON schemas and validators for `bbb_autoresearch_execution_plan.v1`,
      `bbb_autoresearch_execution_receipt.v1`, and the persisted iteration-control record.
- [ ] Reuse canonical `BatchExperimentRequest` validation and preserve exact v1/v2 scientific
      contract compatibility without silent migration.

## 2. Provider-agnostic worker stages

- [ ] Introduce a generic `AgentRunner` boundary with stage-specific prompts, result paths, logs,
      timeouts, attempts, and output allowlists.
- [ ] Split prompts/program requirements into planning and interpretation responsibilities while
      preserving one logical researcher and all Research Quality Policy semantics.
- [ ] Prohibit direct execution, raw market-store access, local evaluator/service substitutes,
      import/client monkeypatching, package managers, and dependency/environment self-repair.

## 3. Supervisor-owned canonical execution

- [ ] Validate and atomically freeze the normalized planning request and SHA256 before execution.
- [ ] Move invocation of the existing `scripts/autoresearch_execute_batch.py` adapter into the
      supervisor with controlled cwd, argv, virtual environment, service endpoints, configs root,
      artifact root, timeout, and logs.
- [ ] Fail closed on canonical dependency/executor failure without exposing a fallback execution
      path to either worker stage.

## 4. Receipt and acceptance validation

- [ ] Persist the minimal trusted receipt atomically and recompute its request, executor, output,
      artifact, identity, ordering, exit-status, and hash fields before acceptance.
- [ ] Reuse all existing canonical path/provenance/integrity checks and require final interpretation
      to agree with the frozen request, receipt, and canonical summary.
- [ ] Detect mutation of supervisor-owned request/output/receipt files and unexpected worker output;
      hard-stop before journal/state commit.

## 5. Stage-aware recovery

- [ ] Persist monotonic planning/request/execution/interpretation/commit stages and separate attempt
      metadata for planning and interpretation.
- [ ] Resume completed canonical execution without rerunning the batch; retry interpretation with a
      fresh worker when required.
- [ ] Recover interpretation-before-commit and journal-before-state crashes idempotently; fail
      closed on ambiguous executor outcome.

## 6. Focused verification

- [ ] Add deterministic normal-flow tests covering plan -> supervisor executor -> receipt ->
      interpretation -> journal/state commit with fake AgentRunner processes and canonical test
      services only.
- [ ] Add negative tests for direct worker execution claims, shims/monkeypatches, local services,
      raw DB files, dependency managers/lockfiles, non-canonical bundles, missing/forged/tampered
      receipts, changed requests, changed outputs, and artifact mismatches.
- [ ] Add crash tests at every durable stage proving no duplicate batch execution or journal row.
- [ ] Prove Codex and Claude command fixtures use the same generic contracts and that provider rules
      are optional defense in depth.
- [ ] Prove supplementary analysis and negative research evidence remain allowed, and supervisor
      never ranks candidates or reconstructs scientific interpretation.

## 7. Documentation and release verification

- [ ] Update AutoResearch README/operational documentation with brokered execution, recovery,
      compatibility, environment ownership, and operator guidance.
- [ ] Run targeted AutoResearch tests, `make verify`, `openspec validate --all --strict`,
      `git diff --check`, and `git status --short`.
