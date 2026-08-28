## 1. Consume the sparse contract

- [ ] 1.1 Update `adapters/http/strategy_engine_client.py`
      (`evaluate_range`/`evaluate_range_batch`/`_parse_evaluation_result`)
      to parse the new sparse `StrategyEvaluationExecution` shape; remove
      `raw=body` retention entirely.
- [ ] 1.2 Split `domain/contracts.py::StrategyEvaluationResult` into a
      lean execution-contract type (decision events + provenance) and a
      separate diagnostic type (only populated when a diagnostic
      evaluation was actually requested).
- [ ] 1.3 Update `execution/entry.py`, `execution/static_exits.py`,
      `execution/protection.py`, `execution/loop.py` to point-query the
      sparse event structure instead of dense array indexing — same call
      sites, same semantics, per the companion change's per-field proof.
- [ ] 1.4 Update `application/backtests/strategy_contract.py`
      (`accept_strategy_execution_contract`/`_validate_side_series` and
      friends) to validate the sparse contract's shape/provenance instead
      of dense-length equality checks; drop the `time_ms` cross-check
      along with the field.

## 2. Single-instance parity proof (must complete before task 5)

- [ ] 2.1 Run old contract vs new contract against the same
      `full_available` BTCUSDT.P/5m request; diff trade-by-trade fields,
      accounting totals, exit reasons, provenance.
- [ ] 2.2 Measure and record CPU/RSS/response body size for both.
- [ ] 2.3 Do not proceed to task 5 until 2.1 shows zero diffs.

## 3. Persistence split

- [ ] 3.1 `application/backtests/artifacts.py::PersistSingleInstanceBacktest`
      — persist the lean execution evaluation once as
      `strategy_evaluation.json`; `result.json` references it by
      identity instead of re-embedding.
- [ ] 3.2 `application/backtests/read_artifacts.py::ReadResearchRuns` —
      each call site reads only the fields it actually uses (confirmed:
      `market`, `accounting.trades` for every current BFF call site).

## 4. Diagnostics become explicit/optional

- [ ] 4.1 Add a diagnostic-evaluation generation use case: given a
      persisted run's identity + `market_data_hash`/range, call Strategy
      Engine's new diagnostic-evaluation entrypoint (companion change
      task 3.2), persist the result as a separate `diagnostics.json` for
      that `run_id`.
- [ ] 4.2 Update `application/diagnostics/projection.py` to read from
      `diagnostics.json` instead of `strategy_evaluation.raw`/
      `component_evidence` — return a stable "diagnostics not yet
      generated" response (not an error masquerading as data) when the
      artifact doesn't exist yet for a run.
- [ ] 4.3 Confirm the existing "No read-time upstream calls" requirement
      still holds for the projection read path — only the new generation
      use case in 4.1 calls upstream, never a projection/read route.

## 5. Batch (only after task 2 passes)

- [ ] 5.1 Confirm `RunBatchExperiment`/`_settle_candidate` need no
      structural change — re-run and confirm.
- [ ] 5.2 Re-run the N=1/2/4/11 memory/CPU harness; confirm
      approximately constant memory in N.

## 6. Spec

- [ ] 6.1 `openspec archive compact-strategy-evaluation-boundary-v1`
      after implementation lands, parity is proven, and both this
      change's and the companion `strategy_engine` change's acceptance
      criteria are met.
