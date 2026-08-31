# BBB AutoResearch v1

BBB AutoResearch is a local autonomous research-control plane over the existing Research Service.
It is not a strategy optimizer, evaluator, backtester, accounting engine, production promotion
mechanism, or live-trading system. A fresh worker chooses one information-gaining research step;
the mechanical supervisor validates its structured result, guards repository immutability, persists
knowledge, and launches the next fresh worker.

The evaluator remains Strategy Engine + Research Service historical execution/accounting + Market
Data Service. Batch execution uses the current `RunBatchExperiment` path and its canonical per-run
artifacts, followed by the existing `PersistBatchExperiment` summary. AutoResearch state links to
those artifacts; it does not copy dense trades or calculate competing metrics.

## Quick start

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
BBB_AUTORESEARCH_AGENT_COMMAND='codex exec -C . -s workspace-write -a never -' \
python scripts/autoresearch_supervisor.py \
  --session ema-anchor-demo \
  --max-iterations 100
```

The command may use `{prompt_file}`, `{result_file}`, `{session_dir}`, `{iteration_dir}`, and
`{iteration_id}` placeholders. Without placeholders, the rendered prompt is still delivered on
stdin. Do not add `--dangerously-bypass-approvals-and-sandbox` to tracked examples. The worker needs
process access required for research, while the independent git guard verifies it made no tracked
write.

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
    prompt.txt
    stdout.log
    stderr.log
    iteration_result.json
    supervisor_metadata.json
```

`state.json` is a compact atomic snapshot. `journal.jsonl` is append-only research history. Detailed
trade truth remains under the configured canonical Research artifact root; batch locations and run
IDs are references in the iteration result/journal. Each retry is another fresh process and retains
separate retry logs. If a process dies before state commit, the same iteration number is resumed and
its durable attempt metadata bounds retries.

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
