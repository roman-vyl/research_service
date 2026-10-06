## Context

Facts from the code (main at 5694bc4):

- Strategy Engine `/strategy-evaluations/range-batch` takes `market`, a list of
  `variants` `{variant_id, strategy}` where `strategy` is a complete spec, and an
  optional `expected_market_data_hash`. `/strategies/{strategy_id}/validate`
  returns `{valid, config_hash}` for one spec. Engine has no notion of Surfaces,
  rows or columns, and this change keeps it so.
- Research runs a batch through `RunBatchExperiment` with a
  `BatchExperimentRequest`: one `strategy_id`, ticker, base timeframe and window
  for the whole experiment; per candidate a `DeployableStrategyInstance`
  (`enabled`, `strategy_id`, `ticker`, `base_timeframe`, `raw_spec`), an
  `ExecutionPolicy`, an `AccountingPolicy` and `managed_policy_enabled`. Each
  completed candidate gets a run folder `<artifacts_root>/<run_id>/` with
  `request.json` and a `BatchCandidateResult` summary (`realised_trade_count`,
  `net_pnl`, `return_pct`, `win_rate`, `profit_factor`, `max_drawdown`,
  `cumulative_*_r`, `long`/`short` side summaries, `market_data_hash`, ...).
- The Experiment manifest `result_schema` declares the table, `run_id_column`,
  provenance (constant or column), dimensions (with grids), arms and metrics with
  `format` (`fraction`, `number`, `integer`). The legacy `varied_params` and
  `fixed_params` describe the strategy for a human; for example the ratio axis is
  written as `"distance.multiplier / sl_distance.multiplier"` and sizing as
  `"full_equity (production default)"`. They cannot be executed.
- Run deletion (`research-run-deletion-v1`) is the only write path to the result
  table today: backup, atomic rewrite, journal, stateless plan token.

## Goals / Non-Goals

**Goals:** an Experiment that by itself says which strategy it studies; a spec
for any row built without component knowledge in Research or the frontend;
Engine results reach the Surface only after they agree with what the row already
says; the table is never left half-written.

**Non-Goals:** see proposal.

## Decisions

### D1. The manifest owns the strategy template

New optional manifest block, next to `result_schema`:

```json
"materialize": {
  "contract_version": "research_experiment_materialize.v1",
  "strategy_template": {
    "enabled": true,
    "strategy_id": "ema_pullback",
    "ticker": "BTCUSDT.P",
    "base_timeframe": "5m",
    "raw_spec": { "...": "complete spec: direction, setups, trigger, blockers, exits, managed policy" }
  },
  "bindings": [
    { "column": "min_width_atr",     "path": "/raw_spec/setups/0/params/min_width_atr", "type": "number" },
    { "column": "lookback",          "path": "/raw_spec/setups/1/params/lookback",      "type": "integer" },
    { "column": "sl_atr_multiplier", "path": "/raw_spec/exits/stop_loss/distance/multiplier", "type": "number" },
    { "column": "tp_atr_multiplier", "path": "/raw_spec/exits/take_profit/distance/multiplier", "type": "number" }
  ],
  "result_bindings": {
    "realised_trade_count": "realised_trade_count",
    "win_rate": "win_rate",
    "max_drawdown_pct": "max_drawdown",
    "long_trades": "long.trades"
  },
  "research_policy": {
    "range_policy": "explicit_range",
    "range": { "from_ms": 0, "to_ms": 0 },
    "execution": { },
    "accounting": { "entry_fee_rate": "0.0004", "exit_fee_rate": "0.0004" },
    "managed_policy_enabled": true
  }
}
```

(Paths and values above are illustrative.) Rules:

- `strategy_template` is a complete `DeployableStrategyInstance`. Every value that
  is not a binding is frozen by the Experiment, including components and
  parameters that never appear on the Surface (trigger, blockers, EMA stack, the
  exact width component).
- A binding is `column` (a column of the result table), `path` (RFC 6901 JSON
  Pointer into the template) and `type` (`number`, `integer`, `string`). The path
  must already exist in the template. No formulas and no unit conversion: a
  derived value such as TP = SL × ratio, or a distance in ATR for an axis shown in
  R, must be its own column in the table.
- `result_bindings` maps each metric column of the row to a field of the Research
  run summary (`BatchCandidateResult`, dotted path into `long`/`short`).
- `research_policy` holds what belongs to Research, not to the strategy: window,
  execution and accounting policy (fees, equity, sizing) and the managed policy
  flag. Its shapes are the existing `BatchExperimentRequest` /
  `BatchCandidateRequest` fields.
- The block is the primary definition of the research. A `request.json` of an
  existing run is evidence that the block is right (see D9), not its source.
- Once the table has rows, the block is not edited. A different template is a
  different Experiment.

An Experiment without the block is served as today; Calculate answers 409
`materialize_missing` for it.

### D2. Rows are addressed by coordinates

The frontend has no row id. A row is addressed by `coords`: one value per
dimension column of `result_schema` (for a grid dimension: the grid column and
the value column of that grid; plus the arm column when arms are declared).
Values are compared as numbers for numeric columns and as text otherwise. Exactly
one row must match; zero is `row_not_found`, more than one is `ambiguous_row`.

### D3. Materialize is mechanical

```
spec = deepcopy(strategy_template)
for b in bindings: set(spec, b.path, parse(row[b.column], b.type))
Engine POST /strategies/{strategy_id}/validate (spec without `enabled`) → config_hash
```

An empty or unparsable cell is `binding_value_invalid`. An Engine validation
error is `invalid_spec` with Engine's message. Research never inspects the spec.

### D4. Who can be calculated

Experiment-level checks (409, nothing runs): `materialize_missing`; a metric
column of `result_schema.metrics` without a result binding (`unbound_metric`),
because the gate could not check it; provenance declared as a constant other than
`engine` (`provenance_not_per_row`), because one row could not become `engine`;
another calculation job is running (`job_running`).

Row-level skips: `row_not_found`, `ambiguous_row`, `has_run` (`run_id` set and
the folder exists; a set `run_id` whose folder is missing counts as no run),
`binding_value_invalid`, `invalid_spec`.

Both replay rows and Engine rows whose run was deleted can be calculated. The
gate is the same for both: the stored metrics are the expected result.

### D5. Routes

`POST /api/research/experiments/{experiment_id}/runs/calculate-plan`
`{ "rows": [ { "coords": {...} } ] }` → per row `calculable` or `skipped` with a
reason, `calculable_count`, and `plan_token`. It runs materialize and Engine
validation, changes nothing. At most 2 000 rows per request (`too_many_rows`,
422).

`POST .../runs/calculate` `{ "rows": [...], "plan_token": "..." }` → recomputes
the token, 409 `plan_stale` if it differs, else starts a job and answers 202
`{ "job_id": "..." }`.

`GET .../calculations/{job_id}` → state (`running`, `completed`, `cancelled`,
`failed`), counts per outcome, per row outcome with `run_id` and parity
differences when present.

`POST .../calculations/{job_id}/cancel` → stops before the next chunk; rows
already published stay published.

**Token**: SHA-256 over the content hash of the result table, the SHA-256 of the
canonical `materialize` block, and the sorted list of (row key, `config_hash`) of
calculable rows. Stateless, same idea as the delete plan token.

### D6. Job execution

One job at a time in the service, in-process. Calculable rows are grouped by the
row's market data hash when the table declares one in `row_columns`; each group
is sent in chunks of 50 rows through `RunBatchExperiment`, with the group hash as
`expected_market_data_hash`, so Engine refuses data that differ from the data
the row was computed on. Batch experiment id:
`calc-<experiment_id>-<UTC timestamp>` (truncated to the id pattern). Job state
is kept in memory and in the journal (D8). A restart loses a running job; rows
published before it stay published, the rest are untouched.

### D7. Parity gate

For every result binding the row's stored value (expected) is compared with the
Engine run summary value (actual):

- metric `format` `integer`: equal exactly;
- otherwise: `|a − e| ≤ max(1e-6 × max(|a|, |e|), 1e-9)`;
- both empty passes; one empty fails.

The tolerance is fixed by this contract and is not configurable. Any difference
fails the row: outcome `parity_failed` with the list `{column, expected,
actual}`. The run folder is kept as a diagnostic artifact and is not linked to the
row. A failed Engine candidate is `engine_failed` with Engine's error.

With this tolerance a replay row passes only if the replay reproduces the Engine
execution model trade for trade. That is intended: the system never claims replay
equals Engine; the gate only lets through what agrees.

### D8. Publish

After each chunk, rows that passed the gate are published in one atomic rewrite
of the result table, under a per-Experiment lock that run deletion also takes:

1. Reread the table. A row whose cells changed since the plan (row hash) is not
   published: outcome `row_stale`, run kept as diagnostic.
2. On the first publish of the job, copy the table to
   `runs.pre_calculate_<UTC>.csv`.
3. For each published row write: every result-binding column (Engine value),
   `run_id_column` (new run id), the provenance column to `engine` when
   provenance is a column. No other cell changes.
4. Write to a temporary file in the same folder and rename over the table.
5. Append one line per row (every outcome, not only published) to
   `runs_calculated.jsonl`: job id, row key, `config_hash`, outcome, `run_id`,
   parity differences, UTC time.

"Calculated" is derived by consumers from `provenance=engine` and a non-empty
`run_id`; nothing else is stored.

### D9. Existing Surfaces

A `materialize` block for an existing Surface is written by hand (or by the agent
that built it) and checked before use: every row with a live run is materialized
and its `config_hash` must equal the Engine `config_hash` of the spec in the
run's `request.json`. A check script reports mismatches; it is not part of the
service. For replay Surfaces without runs there is nothing to compare, and the
gate (D7) is the only check.

For new Experiments the block is written first, agreed with the owner, validated
by Engine, and only then is the Surface computed.

## Risks / Trade-offs

- With the fixed tolerance most replay rows of the current replay Surfaces will
  likely fail the gate. Their Engine runs remain available as diagnostics through
  the journal.
- Diagnostic runs are not referenced by any table, so the delete route cannot
  remove them. Cleaning them is a later change.
- Engine version is not recorded per run; a different Engine image on the same
  template can fail the gate on Engine rows. The failure is visible in the
  journal.
- Rewriting a large table per chunk costs time (hundreds of thousands of rows).
  Chunk size is a constant and can be raised.
