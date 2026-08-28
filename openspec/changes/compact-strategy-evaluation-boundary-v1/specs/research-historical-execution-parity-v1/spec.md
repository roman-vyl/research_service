## ADDED Requirements

### Requirement: N=1 end-to-end parity proof, both lanes mandatory

I5 of the `compact-strategy-evaluation-boundary-v1` Master Plan SHALL be
proven by running exactly one strategy instance (no batch, no N>1) end
to end through the new `HistoricalExecutionProjection`-consuming path —
real Strategy Engine strategy computation → Engine's I1 builder → a
normative `strategy_evaluation_execution.v2` JSON envelope → Research's
real `parse_historical_execution_projection`/`validate_projection_
alignment`/`HistoricalExecutionProjectionIndex` (I3) →
`run_projection_execution_loop` (I4) → the existing, unmodified
`account_execution_loop` (`accounting/service.py`) — and diffing the
resulting trade facts against an **independent** reference for zero
semantic differences.

This proof SHALL be run on two lanes, both mandatory; I5 passes only
when both report zero diffs:

- **Lane A** — a real `full_available` `BTCUSDT.P`/`5m` run against a
  canonical always-on-only strategy spec.
- **Lane B** — a profile-sensitive adversarial spec (three distinct
  `aligned`/`countertrend`/`neutral` exit profiles, each with its own
  stop/take/signal rules, and a real position-lifecycle profile-drift
  scenario), run through the identical full pipeline.

Lane A alone is insufficient: it cannot exercise `locked_exit_profile`
lifecycle correctness (an always-on spec never changes which profile is
active). Lane B alone is insufficient: it does not by itself prove the
new path behaves correctly against real, unconstrained market data at
full historical scale. Both are required.

#### Scenario: Lane A real full_available N=1 parity

- **WHEN** a real `BTCUSDT.P`/`5m` `full_available` range is run for one
  canonical always-on strategy instance, once through the new
  projection-driven path and once through Research's existing legacy
  `run_unified_execution_loop` path (Lane A's reference — see
  "Lane A reference" below), against the identical resolved market
  window
- **THEN** the resulting trade sequences are identical across every
  field in the "Zero-diff comparison surface" below
- **AND** the run reports zero semantic diffs.

#### Scenario: Lane B profile-sensitive adversarial full-pipeline proof

- **WHEN** a profile-sensitive adversarial strategy spec (matching the
  scenario shape already proven at `strategy_engine`'s I2 — three
  distinct profiles, distinct SL/TP/signal rules per profile, an exact
  aggregation tie case) is run through the full new-path pipeline
- **THEN** the resulting trade sequence matches an independent old-BBB
  reference (see "Lane B reference" below) across every field in the
  "Zero-diff comparison surface" below
- **AND** the run reports zero semantic diffs.

### Requirement: Independent reference, not self-comparison

Neither lane's reference mechanism SHALL reuse the specific
implementation under test as its source of expected values.

- **Lane A reference** is Research's own existing, unmodified legacy
  execution path (`execution/loop.py::run_unified_execution_loop` via
  `execution/entry.py`/`execution/protection.py`/`execution/static_
  exits.py`, fed by the legacy `.v1` `StrategyEvaluationResult` Engine
  contract through `adapters/http/strategy_engine_client.py::evaluate_
  range`) — a materially different code path (different entry/
  protection/candidate-collection modules; only the shared, already-
  proven-correct arbitration primitives `execution/unified_exits.py::
  arbitrate_unified_exit_candidates`/`execute_unified_exit` and
  `accounting/service.py::account_execution_loop` are common to both
  sides, and those are not what Lane A is proving). This reference is
  valid only for an always-on-only spec: it implements no
  `locked_exit_profile` semantics at all.
- **Lane B reference** SHALL be an independent old-BBB-grounded trade-
  lifecycle simulator — extending the verbatim, character-for-character
  old-BBB functions already established at `strategy_engine`'s I2
  (`tests/_old_bbb_exit_attribution_reference.py`, sourced from
  `roman-vyl/_bbb_new_gen` commit
  `cddc83663911f646c9bcf2ecfb37b3bed6f4b1d4`) to a full entry → locked-
  profile-capture → profile-drift → exit → attribution lifecycle. It
  SHALL NOT be built by calling `execution/projection_loop.py`,
  `execution/projection_entry.py`, `execution/projection_static_exits.
  py`, or any other code under test, and SHALL NOT be built by calling
  Research's legacy execution path either (which cannot reproduce
  locked-profile semantics and is therefore not independent evidence
  for this lane).

#### Scenario: A reference implementation reusing the code under test is rejected

- **WHEN** a proposed Lane A or Lane B reference mechanism is found to
  call the specific projection-driven execution/entry/candidate-
  collection code it is meant to validate
- **THEN** that mechanism is not an acceptable I5 reference and the
  proof does not count toward the gate.

### Requirement: Zero-diff comparison surface

I5 SHALL compare, exactly, the following fields (all sourced from
existing, already-shipped domain models — no new fields are introduced
by this capability):

- **Entry**: `EntryFill.bar_index`, `.side`, `.time_ms`, `.reference_
  price`, `.fill_price`.
- **Locked profile**: `PositionState.locked_exit_profile` — captured
  once at fill and held fixed for the position's life (Lane B only;
  Lane A's canonical spec never changes profile, so this field is
  trivially constant there).
- **Initial protection**: `InitialProtection.stop_loss_price`/`.take_
  profit_price` (Decimal, exact) and `.stop_loss_attribution`/`.take_
  profit_attribution` (`rule_id`/`component_id`/`exit_kind`/`layer`,
  exact string equality) — independently nullable per leg, matching
  whichever leg the reference resolved.
- **Signal candidate stream while open**: for every bar an independent
  position remains open, the candidate(s) the locked-profile signal
  stream carries at that bar (via `HistoricalExecutionProjectionIndex.
  lookup_signal_event`), compared against the reference's own per-bar
  signal facts for the same locked profile.
- **Exit**: `ExitFill.bar_index`, `.time_ms`, `.candidate_type`, `.fill_
  price`, `.reference_level`.
- **Exit attribution**: `ExitFill.rule_id`/`.component_id`/`.exit_kind`/
  `.layer` — exact string equality; `layer` MUST equal the canonical
  constant `"exit_policy"` on both sides (never read from Engine's wire,
  which carries no `layer` field).
- **Accounting / trade record**: every field of `TradeRecord`
  (`accounting/contracts.py`) — `entry_bar_index`/`exit_bar_index`/
  `entry_time_ms`/`exit_time_ms`/`entry_price`/`exit_price`/`quantity`/
  `entry_notional`/`exit_notional`/`gross_pnl`/`entry_fee`/`exit_fee`/
  `fees_paid`/`net_pnl`/`gross_return_pct`/`net_return_pct`/`equity_
  before`/`equity_after`/`hold_bars`/`hold_ms`/`exit_candidate_type`/
  `exit_reason`/`exit_layer`/`exit_rule_id`/`exit_component_id`/`exit_
  kind`/`path` (`TradePathMetrics`, every field) — all Decimal/int
  fields compared exactly (Decimal arithmetic throughout this pipeline;
  no float rounding is introduced downstream of the wire ratio itself).
- **Aggregate metrics**: every field of `TradeAccountingResult`
  (`realised_trade_count`, `open_position_count`, `gross_pnl`, `fees_
  paid`, `net_pnl`, `final_equity`) compared exactly. There is no
  long/short-split aggregate at N=1 scope in this codebase today
  (`application/experiments/candidate_summary.py`'s long/short split is
  a batch-only artifact, `research-batch-experiments-v1`, out of I5
  scope) — I5 SHALL NOT introduce one.
- **Provenance**: `instance_id`, `config_hash`, `market_data_hash`,
  `bar_count`, and market identity (`ticker`/`timeframe`/`from_ms`/
  `to_ms`) — compared exactly, semantically (not byte-identical
  serialized JSON).

Tolerance: exact equality throughout, with exactly one pre-existing
exception carried over unchanged, not newly introduced by this
capability — comparing an Engine wire `ratio: float` value itself
(before its one-time conversion to a Research-owned Decimal price) uses
the same `eps = 1e-9 * max(1.0, abs(value))` epsilon `strategy_engine`'s
I1 corrective pass already established for its own attribution
algorithm (`historical_execution_projection.py::_close_enough`) — I5
does not define a new tolerance, it reuses that one, and only where a
float value from the wire is the thing being compared. Every Decimal-
typed field in the list above is compared with zero tolerance.

#### Scenario: Any semantic diff fails the gate

- **WHEN** any field in the zero-diff comparison surface above differs
  between the new path and its lane's independent reference, for either
  lane
- **THEN** I5 fails; the migration does not proceed to I6.

#### Scenario: Provenance mismatch fails the proof before comparison begins

- **WHEN** the new path's resolved `market_data_hash`/`bar_count`/market
  identity differs from the reference's own resolved window for the
  same request
- **THEN** the proof fails closed before any trade-level comparison is
  attempted — a provenance mismatch means the two paths were not run
  against the same input, and any trade-level agreement or disagreement
  under that condition is not meaningful evidence.

### Requirement: Locked-profile full lifecycle, with negative control

Lane B SHALL include at least one scenario where a position enters
under one profile and the market's current profile changes at least
once while that position remains open, and the position's actual exit
is governed by the profile locked at entry — not the profile active on
the exit bar.

This scenario SHALL include explicit negative-control evidence: a
computed value showing what the current-bar-profile interpretation
would have selected (a different bar and/or a different rule), compared
against the actual, correct, locked-profile result, asserting they
differ. Without this negative control, a profile-drift fixture cannot
be trusted to actually distinguish the two interpretations (this
mirrors the negative-control discipline `research_service`'s I4 already
established at the execution-loop unit level — `test_i4_execution_
parity.py::test_negative_control_current_profile_lookup_would_have_
chosen_a_different_bar` — extended here to the full real pipeline).

#### Scenario: Locked profile survives a real drift, full pipeline

- **WHEN** a real position enters under profile P through the full new
  path, the market's current profile (per the same run's projection
  data) changes to a different profile while the position remains open,
  and a later bar's locked-profile (P) signal stream fires
- **THEN** the position exits according to P's own signal fact, not
  whatever the current-bar profile's signal fact would have been at any
  earlier bar
- **AND** the negative-control computation confirms the current-profile
  interpretation would have produced a different bar and/or a different
  attributed rule.

### Requirement: Existing accounting math is reused unmodified

I5 SHALL use `accounting/service.py::account_execution_loop` and
`accounting/contracts.py`'s existing models exactly as they exist
today. No I5-specific fee/PnL/equity formula, rounding rule, or
accounting model variant SHALL be introduced.

#### Scenario: Accounting parity is a consequence, not a separate computation

- **WHEN** the new path's `ExecutionLoopResult` differs from the
  reference's execution facts in any way
- **THEN** the resulting accounting divergence is expected and does not
  indicate an accounting-layer defect — accounting parity SHALL be
  interpreted only in light of execution-fact parity already holding.

### Requirement: Transport-equivalent v2 envelope proof

Although Strategy Engine's production `/range` route remains on the
`.v1` contract until I7, I5 SHALL prove that a normative
`strategy_evaluation_execution.v2` JSON envelope (per `strategy_engine`
capability `strategy-research-execution-contract-v1`, `contract_
version`, nested `market{ticker, base_timeframe, from_ms, to_ms, bar_
count, market_data_hash}`) — produced from a `HistoricalExecutionProjection`
built by Strategy Engine's real, already-shipped I1 builder
(`build_historical_execution_projection`) against real production
strategy computation (`EmaPullbackRangeEvaluator`'s native evaluation
path, the same one `evaluate_execution` already uses) — decodes,
without modification, through Research's actual, already-shipped
`parse_historical_execution_projection`/`validate_projection_
alignment`/`HistoricalExecutionProjectionIndex.build` (`domain/
contracts.py`, I3).

This SHALL be proven via a real, materialized JSON artifact — not an
in-process Python object handoff — since Strategy Engine and Research
Service run in separate processes/environments in production. Strategy
Engine's side of this proof (real computation → builder → normative v2
JSON) is `strategy_engine`'s I5 contribution; no new Engine production
route or serializer is required by this requirement — a proof-only
serialization mechanism producing the wire-normative shape is
sufficient, since `strategy_engine`'s `strategy-research-execution-
contract-v1` capability already normatively fixes what that shape must
be (commit `dae5b4e`).

#### Scenario: v2 envelope decodes through the real Research parser unmodified

- **WHEN** a real v2 JSON envelope produced from Strategy Engine's real
  computation and I1 builder is handed to
  `parse_historical_execution_projection`
- **THEN** it decodes successfully into a `HistoricalExecutionProjectionDTO`
  with no field coercion, no schema patching, and no manual correction
  of the JSON before decode
- **AND** `validate_projection_alignment` against the same run's
  resolved `MarketFrame` succeeds.

### Requirement: Production routes and batch remain out of scope

I5 is a proof-only checkpoint. It SHALL NOT modify, and its passing
SHALL NOT be interpreted as approval to modify:

- Strategy Engine's `/range` or `/range-batch` routes;
- Research's production `/range` HTTP consumer
  (`adapters/http/strategy_engine_client.py::evaluate_range`, the
  legacy `.v1` contract call `RunSingleInstanceBacktest`/
  `MaterializeBacktestOutcome` actually use in production);
- persistence artifact shape (`research-run-artifacts-v1`,
  `research-diagnostics-projection-v1`) — that is I6, gated on I5
  passing, not designed by this capability;
- `research-batch-experiments-v1`'s N-candidate aggregation pattern —
  that is I8, gated on I7;
- Strategy Runtime or any live-facing contract.

#### Scenario: Production /range remains on the legacy contract during I5

- **WHEN** I5's proof harness runs
- **THEN** Research's production backtest orchestration
  (`RunSingleInstanceBacktest`) continues to call Strategy Engine's
  legacy `/range` route and consume the `.v1` contract, unmodified
- **AND** the new projection-driven path is exercised only by the I5
  harness, not by any production request.

#### Scenario: Batch path is untouched and out of scope

- **WHEN** I5's proof is evaluated
- **THEN** `/range-batch` and `application/experiments/run_batch.py`'s
  aggregation pattern are not part of the proof and are not modified by
  it — I8 remains the only checkpoint authorized to redesign batch
  lifetime, and only after I7.
