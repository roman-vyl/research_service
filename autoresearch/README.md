# BBB AutoResearch

BBB AutoResearch is a local autonomous research-control plane over the existing Research Service.
It is not a strategy optimizer, evaluator, backtester, accounting engine, production promotion
mechanism, or live-trading system. A fresh planning worker chooses one information-gaining research
step; the supervisor alone runs any canonical batch; a fresh interpretation worker evaluates the
evidence; and the mechanical supervisor validates and persists knowledge. The two worker processes
are one logical autonomous researcher, not separate scientific roles.

The evaluator remains Strategy Engine + Research Service historical execution/accounting + Market
Data Service. Batch execution uses the current `RunBatchExperiment` path and its canonical per-run
artifacts, followed by the existing `PersistBatchExperiment` summary. AutoResearch state links to
those artifacts; it does not copy dense trades or calculate competing metrics.

## Quick start

### Select the supervisor runtime profile first

Before starting AutoResearch, the operator or agent **must determine where the supervisor process
itself runs** and use exactly one documented launch profile. Do not infer the profile from where the
services run, and do not rely on Research Settings defaults outside the runtime context for which
they are valid. AutoResearch has no separate Engine/MDS addressing scheme: both profiles populate
the existing Research `Settings` contract, and the supervisor passes its resolved settings only to
the canonical executor.

| Profile | Supervisor runtime | Strategy Engine | Market Data Service | Artifact/config roots |
| --- | --- | --- | --- | --- |
| HOST | macOS or Linux host | `http://127.0.0.1:8090` | `http://127.0.0.1:8080` | Required absolute host paths supplied by the operator |
| DOCKER | container attached to the BBB Docker network | `http://strategy-engine:8080` | `http://market-data-service:8080` | Explicit container paths; defaults are `/data/runs` and `/data/configs` |

For a host-run supervisor, export writable absolute host roots and use the host wrapper:

```bash
export RESEARCH_ARTIFACTS_ROOT=/Users/operator/bbb_data/autoresearch
export RESEARCH_CONFIGS_ROOT=/Users/operator/bbb_data/autoresearch/configs
export BBB_AUTORESEARCH_AGENT_COMMAND='codex exec -C . -s workspace-write -'
scripts/autoresearch_run_host.sh \
  --session ema-anchor-demo \
  --max-iterations 100
```

For a supervisor running inside the BBB Docker network, use the Docker wrapper. Override the roots
only when that container uses different mounted paths:

```bash
export BBB_AUTORESEARCH_AGENT_COMMAND='codex exec -C . -s workspace-write -'
scripts/autoresearch_run_docker.sh \
  --session ema-anchor-demo \
  --max-iterations 100
```

Both wrappers set only Research runtime configuration and forward every CLI argument unchanged to
`scripts/autoresearch_supervisor.py`. They use `python` from `PATH`, so activate the intended
environment before invoking them. Provider credentials, the agent command, and other ordinary
runtime variables remain operator-owned.

Initialize and inspect a session:

```bash
python scripts/autoresearch_init.py \
  --session ema-anchor-demo \
  --template autoresearch/templates/ema_anchor_session.json
python scripts/autoresearch_status.py --session ema-anchor-demo
```

The installed Codex CLI accepts a prompt on stdin via non-interactive `codex exec`. Agent command
syntax is deliberately operator-supplied and is split with `shlex`; the supervisor never uses
`shell=True`. One reasonable local example, with permissions chosen explicitly by the operator, is:

```bash
BBB_AUTORESEARCH_AGENT_COMMAND='codex exec -C . -s workspace-write -' \
scripts/autoresearch_run_host.sh \
  --session ema-anchor-demo \
  --max-iterations 100
```

The command may use `{stage}`, `{prompt_file}`, `{result_file}`, `{session_dir}`, `{iteration_dir}`,
and `{iteration_id}` placeholders. Without placeholders, each rendered stage prompt is delivered on
stdin. Provider permissions are defense in depth: correctness comes from supervisor-owned execution,
immutable request/receipt binding, stage output allowlists, and repository guards.

Planning and interpretation processes inherit the ordinary CLI/runtime environment, including
provider configuration, credentials, `PATH`, and `VIRTUAL_ENV`, but the supervisor removes the
entire case-insensitive `RESEARCH_*` namespace. The canonical executor receives a separate explicit
environment: the supervisor resolves one current `Settings` object and serializes all of its fields
back into authoritative `RESEARCH_*` values. Unknown inherited `RESEARCH_*` variables are not
forwarded to either environment contract.

Re-run the same supervisor command to resume. It reads committed state and starts the next iteration,
not the previous one. Request graceful cancellation with:

```bash
python scripts/autoresearch_cancel.py --session ema-anchor-demo
```

Cancellation writes a marker; it does not blindly kill a process. The supervisor consumes it before
the next worker and transitions the session to `cancelled`.

## Session layout and recovery

Runtime state is durable but ignored by git:

```text
var/autoresearch/<session_id>/
  bootstrap.json
  state.json
  journal.jsonl
  cancel.requested.json          # only when requested
  iterations/0001/
    planning_prompt.txt
    planning.stdout.log
    planning.stderr.log
    execution_plan.json
    canonical_request.json       # batch only; supervisor-frozen
    execution_output.json        # batch only; supervisor-owned
    execution_receipt.json       # batch only; supervisor-owned
    executor.stdout.log          # batch only
    executor.stderr.log          # batch only
    interpretation_prompt.txt
    interpretation.stdout.log
    interpretation.stderr.log
    iteration_result.json
    iteration_control.json
    supervisor_metadata.json
```

`state.json` is a compact atomic snapshot. `journal.jsonl` is append-only research history. Detailed
trade truth remains under the configured canonical Research artifact root; batch locations and run
IDs are references in the iteration result/journal. Each retry is another fresh process and retains
separate retry logs. If a process dies before state commit, the same iteration number is resumed and
its durable attempt metadata bounds retries.

New sessions are marked with `bbb_autoresearch_supervisor_execution.v1`; sessions initialized before
the brokered protocol fail closed and must not be silently migrated. A frozen non-batch plan resumes
at interpretation without an executor or receipt. A completed valid batch receipt resumes at
interpretation without recompute. An ambiguous executor launch fails closed.

The bundled EMA session template is quality-aware and initializes
`bbb_autoresearch_state.v2`. Its immutable nested policy is
`bbb_research_quality_policy.v1`; workers return `bbb_autoresearch_iteration.v2` containing
`bbb_research_quality_assessment.v1`, and the journal uses `bbb_autoresearch_journal.v2`.
State retains the latest full assessment and compact promotion history; iteration results and
journal rows retain the full assessment.

Legacy templates without `research_quality_policy` still initialize exact
`bbb_autoresearch_state.v1` sessions, accept only `bbb_autoresearch_iteration.v1`, and write
`bbb_autoresearch_journal.v1`. There is no silent migration. To adopt quality policy, the operator
initializes a new session from a fully resolved quality-aware template and explicitly carries over
only reviewed research context.

Inspect the files directly when needed:

```bash
python scripts/autoresearch_status.py --session ema-anchor-demo --journal-rows 10
less var/autoresearch/ema-anchor-demo/state.json
tail -n 20 var/autoresearch/ema-anchor-demo/journal.jsonl
```

## Safety and hard stops

Workers may write only below their session runtime root (plus canonical artifacts written by the
existing application path). Before and after every invocation, the supervisor examines unstaged,
staged, and untracked git paths. Any repository change outside the allowed ignored session root is a
hard stop. Evidence is preserved; no reset or cleanup is attempted. This is a deterministic,
fail-closed repository guard, not an absolute OS sandbox.

Hard stops cover contract/catalog mismatch, data-integrity/hash mismatch, evaluator inconsistency,
forbidden mutation, bounded repeated process failure, budgets, cancellation, causal-phase violation,
and work that would require production changes. Ordinary phase progression continues without human
approval.

## Iteration result example

```json
{
  "contract_version": "bbb_autoresearch_iteration.v1",
  "session_id": "ema-anchor-demo",
  "iteration_id": 12,
  "status": "completed",
  "phase": "structural_1d",
  "hypothesis": "A live-catalog structural proxy changes anchor response topology.",
  "market_property_proxy": "A catalog-confirmed parameter and its market-state meaning.",
  "experiment": {
    "kind": "batch", "experiment_id": "ema-anchor-demo-0012",
    "axes": [{"name": "catalog_parameter", "values_ref": "analysis/axis.json"}],
    "candidate_ids": ["c001", "c002"], "candidate_count": 2,
    "window_policy": {"range_policy": "explicit_range", "from_ms": 0, "to_ms": 1},
    "strategy_context": {"strategy_id": "ema_pullback"},
    "execution_accounting_assumptions": {"source": "batch request artifact"}
  },
  "execution_result": {
    "batch_artifact_path": "/data/runs/batches/ema-anchor-demo-0012",
    "run_ids": ["run_a", "run_b"], "market_data_hash": "sha256-value",
    "completed_candidates": 2, "failed_candidates": 0, "analysis_path": "analysis.md"
  },
  "observed_response": {
    "topology": "broad_ridge", "structural_dimensions": ["catalog_parameter"],
    "tested_ranges": [{"axis": "catalog_parameter", "range": "see request artifact"}],
    "promising_regions": [{"description": "broad interior region"}],
    "rejected_regions": [{"description": "unstable boundary"}]
  },
  "side_interpretation": {
    "aggregate": "mixed", "long": "stable", "short": "uncertain",
    "asymmetry": "The aggregate improvement is predominantly long-side."
  },
  "risk_assessment": {
    "thinning_risk": "Trade count declines materially in the interior region.",
    "temporal_regime_concentration_concern": "Requires a validation diagnostic.",
    "other_confounders": ["possible broad trend-regime selection"]
  },
  "conclusion": "The response is regional, not an isolated scalar winner.",
  "next_discriminating_question": "Does the shape persist without concentration?",
  "proposed_next_experiment": {"kind": "validation", "reason": "distinguish topology from thinning"},
  "hard_stop_reason": null
}
```

## Non-goals

V1 has no distributed or parallel hypotheses, multi-agent swarm, web dashboard, remote orchestration,
scheduler daemon, queue, external database, automatic production promotion, live trading, parameter
optimizer, model training, code self-modification, or runtime modification of the EMA skill.
