## 1. Versioned handoff contracts

- [x] Add exact JSON schemas and validators for `bbb_autoresearch_execution_plan.v1`,
      `bbb_autoresearch_execution_receipt.v1`, and the persisted iteration-control record.
- [x] Reuse canonical `BatchExperimentRequest` validation and preserve exact v1/v2 scientific
      contract compatibility without silent migration.
- [x] Make the receipt schema and validator conditional on `action=batch`; require no execution
      intent or receipt for `artifact_diagnostic`, `terminal`, and `hard_stop`.

## 2. Provider-agnostic worker stages

- [x] Introduce a generic `AgentRunner` boundary with stage-specific prompts, result paths, logs,
      timeouts, attempts, and output allowlists.
- [x] Split prompts/program requirements into planning and interpretation responsibilities while
      preserving one logical researcher and all Research Quality Policy semantics.
- [x] Launch a fresh interpretation worker for every action, including all non-batch actions, and
      prevent the supervisor from converting planning output directly into research semantics.
- [x] Prohibit direct execution, raw market-store access, local evaluator/service substitutes,
      import/client monkeypatching, package managers, and dependency/environment self-repair.

## 3. Supervisor-owned canonical execution

- [x] Validate and atomically freeze the normalized planning request and SHA256 before execution.
- [x] Move invocation of the existing `scripts/autoresearch_execute_batch.py` adapter into the
      supervisor with controlled cwd, argv, virtual environment, service endpoints, configs root,
      artifact root, timeout, and logs.
- [x] Fail closed on canonical dependency/executor failure without exposing a fallback execution
      path to either worker stage.

## 4. Receipt and acceptance validation

- [x] For `batch`, persist the minimal trusted receipt atomically and recompute its request,
      executor, output, artifact, identity, ordering, exit-status, and hash fields before
      acceptance; for non-batch actions assert that no receipt exists.
- [x] Reuse all existing canonical path/provenance/integrity checks and, for `batch`, require final
      interpretation to agree with the frozen request, receipt, and canonical summary; for
      non-batch actions validate agreement with the frozen plan and applicable existing evidence.
- [x] Detect mutation of supervisor-owned request/output/receipt files and unexpected worker output;
      hard-stop before journal/state commit.

## 5. Stage-aware recovery

- [x] Persist monotonic planning/request/execution/interpretation/commit stages and separate attempt
      metadata for planning and interpretation.
- [x] Resume completed canonical execution without rerunning the batch; retry interpretation with a
      fresh worker when required.
- [x] Recover interpretation-before-commit and journal-before-state crashes idempotently; fail
      closed on ambiguous executor outcome.
- [x] Resume a frozen non-batch plan directly at fresh interpretation and recover its prepared
      interpretation idempotently without creating execution intent, receipt, or executor process.

## 6. Focused verification

- [x] Add deterministic normal-flow tests covering plan -> supervisor executor -> receipt ->
      interpretation -> journal/state commit with fake AgentRunner processes and canonical test
      services only.
- [x] Add negative tests for direct worker execution claims, shims/monkeypatches, local services,
      raw DB files, dependency managers/lockfiles, non-canonical bundles, missing/forged/tampered
      receipts, changed requests, changed outputs, and artifact mismatches.
- [x] Add crash tests at every durable stage proving no duplicate batch execution or journal row.
- [x] Prove Codex and Claude command fixtures use the same generic contracts and that provider rules
      are optional defense in depth.
- [x] Prove supplementary analysis and negative research evidence remain allowed, and supervisor
      never ranks candidates or reconstructs scientific interpretation.
- [x] Add focused `artifact_diagnostic`, `terminal`, and `hard_stop` flow and recovery tests proving
      the executor is not invoked, no receipt is created, a fresh interpretation worker is used,
      the supervisor creates no research semantics, the applicable iteration commits correctly,
      and resume never launches the executor.

## 7. Documentation and release verification

- [x] Update AutoResearch README/operational documentation with brokered execution, recovery,
      compatibility, environment ownership, and operator guidance.
- [x] Run targeted AutoResearch tests, `make verify`, `openspec validate --all --strict`,
      `git diff --check`, and `git status --short`.
