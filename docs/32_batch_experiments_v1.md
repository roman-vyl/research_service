# Batch Experiments v1

`research-batch-experiments-v1` is step 13 of the 18-step Research Service function-porting plan.

## Boundary

The batch layer owns orchestration only. It does not calculate indicators, strategy decisions,
execution semantics, or accounting formulas. Each candidate delegates to the existing
`RunSingleInstanceBacktest` and `PersistSingleInstanceBacktest` use cases.

## Execution model

Candidates run strictly in the order supplied by `BatchExperimentRequest`. v1 intentionally has
no worker pool and no concurrent Strategy Engine requests. A candidate failure is captured as a
failed result and later candidates continue.

## Contracts

- `BatchCandidateRequest`: candidate identity, one complete single-instance backtest request, and
  optional metadata.
- `BatchExperimentRequest`: immutable experiment identity and ordered candidates.
- `BatchCandidateResult`: completed metrics/artifact reference or stable failure evidence.
- `BatchExperimentResult`: versioned ordered summary with completed/failed counts.

## Artifacts

Every successful candidate publishes the normal immutable run bundle. The batch summary is then
published atomically under:

```text
var/runs/batches/<experiment_id>/
├── request.json
├── summary.json
└── manifest.json
```

The batch summary never embeds full trade/evaluation payloads; it references candidate run
artifacts and exposes comparison-level accounting totals.

## Deferred optimization

Bounded concurrency, shared market loading, and a Strategy Engine range-batch endpoint are later
performance changes. They must preserve ordered result identity and per-candidate failure
isolation.
