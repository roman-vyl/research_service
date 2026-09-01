## 1. Contracts and state

- [x] Add versioned JSON schemas and a winner-free EMA session template.
- [x] Add atomic state, append-only journal, validation, and session ID handling.

## 2. Local lifecycle

- [x] Add init, read-only status, and graceful cancellation CLIs.
- [x] Add fresh-process supervisor, budgets, bounded retries, restart metadata, and logs.
- [x] Add fail-closed tracked/untracked repository mutation guard.

## 3. Canonical execution seam

- [x] Add a thin current-composition batch adapter with live config validation.
- [x] Reuse `RunBatchExperiment` and `PersistBatchExperiment`; add no evaluator semantics.

## 4. Policy and documentation

- [x] Add operational constitution, iteration/bootstrap prompts, quick start, recovery, safety,
      output example, and non-goals.
- [x] Link the root README to the AutoResearch guide.

## 5. Verification

- [x] Add state, supervisor, guard, program-contract, and adapter tests with fake processes/services.
- [x] Run `git diff --check`, `make verify`, and `openspec validate --all --strict`.
