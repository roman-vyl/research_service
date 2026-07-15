# Diagnostics Projection v1

## Purpose

`research-diagnostics-projection-v1` restores the Workbench diagnostics seam without recalculating strategy semantics inside Research Service.

The projection combines:

- immutable `StrategyEvaluationResult.component_evidence` from Strategy Engine;
- contexts and feature mappings already preserved in the Strategy Engine response;
- Research-owned `ExecutionEvent` facts from the unified execution loop.

## Endpoints

- `GET /api/research/runs/{run_id}/signal-trace`
- `GET /api/research/runs/{run_id}/chart-events`

The existing Workbench query parameters remain supported: `variant`, `from`, `to` or `to_open_time_ms`, and optional `context_overlay_ref`.

## Ownership boundary

Strategy Engine remains authoritative for direction, blockers, setups, triggers, risk, entries, contexts and exit-policy evidence. Research Service only slices, labels and projects those immutable facts.

Research Service is authoritative for entry/exit fills, position lifecycle and same-bar arbitration markers. It adds those facts from `ExecutionLoopResult.events`.

No strategy component is re-evaluated in this projection.

## Dense signal trace

The dense trace contains aligned per-bar lanes for both sides:

- `direction_ok`;
- `blockers_ok`;
- `setup_ok`;
- `trigger_ok`;
- `risk_ok`;
- `signal_entry`;
- `stop_ready`;
- `portfolio_entry`.

`portfolio_entry` is the Research execution gate `signal_entry AND stop_ready`.

## Sparse component events

Sparse chart markers are projected from:

1. active Strategy Engine component masks for direction/blockers/setups/triggers/risk;
2. Research execution events such as `entry_filled`, `exit_filled`, and `position_left_open`.

Execution markers retain position/fill identity and arbitration metadata.

## HTF context

When Strategy Engine preserved context output and mapped HTF EMA series, the selected context is projected into `htf_context`. `context_overlay_ref` selects a declared context and is rejected when it is not present in the immutable run evaluation.

## Artifact model

Diagnostics are generated only from the new immutable run bundle. The projector does not access legacy result directories, MDS, or Strategy Engine at read time.
