## Why

BBB AutoResearch v1 correctly treats the Research evaluator as immutable and verifies the
provenance and integrity of persisted batch artifacts. Operational smoke testing exposed a gap
before those checks: the autonomous worker still owns the process that creates experiment truth.
Different CLI providers independently changed execution context, selected non-canonical artifact
roots, installed or synchronized dependencies, and attempted session-local Engine/MDS substitutes.
The supervisor rejected the outputs, but only after the worker had already controlled execution.

The corrective boundary is: **the agent owns research decisions, the supervisor owns experiment
execution, and the canonical evaluator owns truth**. This change moves the invocation of the
existing canonical batch adapter into the supervisor without changing Research, Strategy Engine,
MDS, accounting, or Research Quality Policy semantics.

## What Changes

- Split one logical AutoResearch iteration into planning, supervisor-owned canonical execution,
  and interpretation stages. Planning and interpretation use fresh CLI processes through one
  provider-agnostic `AgentRunner` boundary.
- Add a versioned planning contract carrying the hypothesis and immutable canonical
  `BatchExperimentRequest`, plus a minimal supervisor-owned execution receipt binding that request
  to the canonical result and persisted artifacts.
- Make the supervisor the only owner of executor cwd, invocation, Research runtime environment,
  service connectivity, and canonical artifact-root configuration.
- Require final interpretation acceptance to agree with the immutable request, trusted receipt,
  canonical artifacts, and the existing quality-aware iteration contract.
- Define fail-closed planning/execution/interpretation retry and crash recovery so a completed
  canonical batch is never repeated merely because interpretation or state commit crashed.
- Strengthen the worker constitution and prompts against dependency self-repair, local evaluator
  substitutes, raw market-store access, import/client monkeypatching, and direct experiment
  execution. Provider-specific rules, hooks, and sandbox settings remain defense in depth only.

## Capability

### Modified Capability

- `bbb-autoresearch-v1`: broker canonical experiment execution through the mechanical supervisor
  while preserving autonomous research decisions and the existing immutable evaluator.

## Impact

The later APPLY phase is expected to change AutoResearch scripts, prompts, schemas, documentation,
and tests. The existing `scripts/autoresearch_execute_batch.py` composition remains the canonical
executor. Existing Research Quality Policy assessment, promotion, lifecycle, and no-leaderboard
semantics remain unchanged. No production package under `src/research_service/**` is required by
this design.
