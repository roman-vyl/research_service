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
  exits.py`), fed by Research's legacy `.v1` `StrategyEvaluationResult`
  domain model built proof-only, in-process, from `strategy_engine`'s
  legacy dense computation (`EmaPullbackRangeEvaluator.evaluate()` /
  `StrategyRangeResult`) against the same resolved market window —
  **not** through `adapters/http/strategy_engine_client.py::evaluate_
  range`/Engine's live `/range` route. Engine's production `/range`
  route already serves the superseded sparse `.v1`
  `StrategyEvaluationExecution` contract (`strategy_serialization.py::
  serialize_strategy_evaluation_execution`, per this change's own
  earlier route cutover), which Research's legacy client cannot parse
  (it expects `StrategyRangeResult`'s dense `features`/`entries`/
  `exit_policy`/`component_evidence` shape) — see "Known intermediate
  incompatibility" below. Using Engine's still-present, unmodified
  `evaluate()` method directly (proof-only, in-process, exactly as
  I5.A's own Engine-side script already calls `_evaluate_frame_native`
  directly rather than through a route) is a materially different code
  path from the new path under test (different entry/protection/
  candidate-collection modules; only the shared, already-proven-correct
  arbitration primitives `execution/unified_exits.py::arbitrate_
  unified_exit_candidates`/`execute_unified_exit` and `accounting/
  service.py::account_execution_loop` are common to both sides, and
  those are not what Lane A is proving). This reference is valid only
  for an always-on-only spec: it implements no `locked_exit_profile`
  semantics at all.
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

### Requirement: Known intermediate incompatibility — production `/range` vs. legacy Research client

Engine's production `/range` route already serves the sparse `.v1`
`StrategyEvaluationExecution` contract; Research's production HTTP
client (`adapters/http/strategy_engine_client.py::evaluate_range`/
`_parse_evaluation_result`) still expects the older dense
`StrategyRangeResult` shape and cannot parse the actual current
response. This is a real, pre-existing intermediate state of the
migration — not something I5 introduces or is required to fix. It is
resolved by I7's coordinated `.v2` cutover (both repos land the new
consumer/producer together), not by I5. I5's Lane A reference SHALL NOT
route through this broken HTTP path in either direction (neither
production `/range` nor the legacy client) — it uses Engine's legacy
in-process `evaluate()` directly, as described in "Independent
reference, not self-comparison" above, precisely because the HTTP path
between the two repos is not currently a working reference mechanism.

#### Scenario: Lane A reference does not depend on the broken HTTP path

- **WHEN** I5's Lane A reference is constructed
- **THEN** it calls `EmaPullbackRangeEvaluator.evaluate()` directly,
  in-process, against the same resolved market window — it does not
  call Engine's live `/range` route or Research's `evaluate_range`
  HTTP client method
- **AND** the fact that those two would not currently interoperate is
  recorded here, not silently worked around, and is explicitly out of
  I5's scope to fix (I7's responsibility).

### Requirement: Zero-diff comparison surface

I5's comparison surface is scoped PER LANE, to what each lane's
reference mechanism actually, independently produces — not one
identical field list forced onto both lanes regardless of what their
references are capable of. A proof implementation SHALL NOT claim a
field was compared when its lane's reference does not independently
compute it.

**Lane A** (legacy Research execution path as reference) SHALL compare,
exactly, every field of `TradeRecord` (`accounting/contracts.py`) both
sides actually produce — `entry_bar_index`/`exit_bar_index`/`entry_
time_ms`/`exit_time_ms`/`entry_price`/`exit_price`/`quantity`/`entry_
notional`/`exit_notional`/`gross_pnl`/`entry_fee`/`exit_fee`/`fees_
paid`/`net_pnl`/`gross_return_pct`/`net_return_pct`/`equity_before`/
`equity_after`/`hold_bars`/`hold_ms`/`exit_candidate_type`/`exit_
reason`/`exit_layer`, plus every field of `path` (`TradePathMetrics`,
every field — both sides compute this identically since both route
through the same, unmodified `account_execution_loop`), plus every
field of `TradeAccountingResult` (`realised_trade_count`, `open_
position_count`, `initial_equity`, `gross_pnl`, `fees_paid`, `net_pnl`,
`final_equity`), plus provenance (below). `exit_rule_id`/`exit_
component_id`/`exit_kind` are EXCLUDED from Lane A's pass/fail
comparison and reported informationally only — Lane A's legacy
reference path structurally never populates them (`execution/static_
exits.py` never sets `rule_id`/`component_id`/`exit_kind` on an
`ExitCandidate`; this is the exact pre-existing gap I4 restored on the
new path, not a defect this proof is scoped to catch on Lane A). There
is no long/short-split aggregate at N=1 scope in this codebase today
(`application/experiments/candidate_summary.py`'s long/short split is a
batch-only artifact, `research-batch-experiments-v1`, out of I5 scope)
— I5 SHALL NOT introduce one.

**Lane B** (independent old-BBB-grounded lifecycle simulator as
reference) SHALL compare, exactly: `side`, `entry_bar_index`, `exit_
bar_index`, `entry_price`, `exit_price`, `hold_bars`, `gross_pnl`/`net_
pnl` (comparable only because the harness asserts its `AccountingPolicy`
is zero-fee — the independent simulator has no fee model, so `gross_pnl
== net_pnl` is the only valid comparison point, not full fee/notional/
equity bookkeeping), `exit_candidate_type`, `locked_exit_profile`
(`PositionState.locked_exit_profile`, captured once at fill and held
fixed for the position's life — Lane B only; Lane A's canonical spec
never changes profile, so this field carries no evidentiary value
there), and exit attribution (`exit_rule_id`/`exit_component_id`/
`exit_kind`/`exit_layer` — MANDATORY exact match on Lane B, unlike Lane
A, since the independent simulator DOES produce real attribution from
the same declared-order selection algorithm `strategy_engine`'s I2
verified). Also: **initial protection** (`InitialProtection.stop_loss_
price`/`.take_profit_price` and their attribution, independently
nullable per leg) and **signal candidate stream while open** (for every
bar an independent position remains open, the locked-profile signal
stream's candidates at that bar, via `HistoricalExecutionProjectionIndex
.lookup_signal_event`, against the reference's own per-bar signal
facts) are proven as an intrinsic part of how the Lane B reference
lifecycle is constructed (`_reference_lifecycle` resolves protection
and looks up signal events from the same real projection data the new
path consumes, then independently reimplements selection/arbitration on
top of it) — not restated as separate top-level bullets, since Lane B's
Zero-diff comparison surface above already is that resolved lifecycle's
observable output.

**Deliberately NOT part of Lane B's comparison surface**: `entry_
notional`/`exit_notional`/`entry_fee`/`exit_fee`/`equity_before`/
`equity_after` and `TradePathMetrics` (`path`, every field) — the
independent old-BBB-grounded simulator does not compute accounting
bookkeeping or intrabar MFE/MAE tracking, so there is no independent
expected value to compare against for these fields on Lane B. This is
not a gap silently left unchecked: these exact fields ARE independently
verified, on real full-scale data, by Lane A (whose reference — the
existing, unmodified legacy execution path — DOES route through the
same `account_execution_loop`/`TradePathMetrics` computation the new
path uses). This split is consistent with the "Existing accounting math
is reused unmodified" requirement below: accounting/path-metrics
correctness is not an independent claim per lane, it is a consequence
of execution-fact correctness plus one shared, unmodified computation,
and Lane A already establishes that consequence holds.

**Provenance** (both lanes): `instance_id`, `config_hash`, `market_
data_hash`, `bar_count`, and market identity (`ticker`/`timeframe`/
`from_ms`/`to_ms`) — compared exactly, semantically (not byte-identical
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
typed field in the lists above is compared with zero tolerance.

#### Scenario: Lane A excludes exit attribution from pass/fail, Lane B requires it

- **WHEN** Lane A's comparison completes with `exit_rule_id`/`exit_
  component_id`/`exit_kind` differing between the legacy reference (always
  `None`) and the new path (real attribution)
- **THEN** this is reported informationally and does NOT fail Lane A
- **AND** the identical fields differing on Lane B, where the independent
  reference DOES produce real attribution, DOES fail Lane B.

#### Scenario: A proof does not claim fields its reference cannot independently produce

- **WHEN** Lane B's comparison is evaluated
- **THEN** `TradePathMetrics`/notional/fee/equity fields are not asserted
  equal and are not reported as passing — they are simply outside Lane
  B's comparison surface, because its independent reference does not
  compute them
- **AND** this is stated explicitly in the proof's own scope
  documentation, not left to be inferred from what the code happens not
  to check.

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

`locked_exit_profile` itself SHALL be sourced only from the matching
`ExecutableEntryOpportunityDTO.locked_exit_profile` at fill time
(`HistoricalExecutionProjectionIndex.lookup_entry`), exactly as I4
already established — this requirement does not change that. What this
requirement adds is evidence that the drift fixture is genuinely
adversarial, not a mechanism the new execution path reads from.

**Post-entry current-profile evolution is proof-only evidence, not a
`HistoricalExecutionProjection` field.** `strategy_evaluation_execution
.v2` carries no current-bar-profile timeline anywhere — Engine's
`HistoricalExecutionProjection` is intentionally per-opportunity
(`locked_exit_profile` on each `ExecutableEntryOpportunityDTO`) and
per-profile-indexed (`signal_exit_events[side][profile]`), never a flat
"what is the active profile on bar N" series (`strategy-research-
execution-contract-v1`: "never a flattened current-bar-profile
series"). The negative control therefore SHALL derive the current-
profile value at each post-entry bar from a source outside the v2
wire — either Strategy Engine's native `EmaPullbackEvaluation`
(`exit_policy.profile_long`/`profile_short`, the same native series I2
already reads for this exact purpose) captured directly from the same
in-process run that produced the projection, or the Lane B old-BBB
reference's own profile-resolution output. This evidence SHALL be used
only to construct and verify the fixture and to compute the negative-
control comparison value — it SHALL NOT be added to the `.v2` envelope,
SHALL NOT be passed to `parse_historical_execution_projection`/
`HistoricalExecutionProjectionIndex`, and SHALL NOT be read by
`run_projection_execution_loop`, `execution/projection_entry.py`, or
`execution/projection_static_exits.py` at any point. The new execution
path's actual behavior under test continues to depend on nothing but
the already-shipped v2 projection and `PositionState.locked_exit_
profile`; the current-profile series exists only in the proof
harness's own comparison logic, alongside the run, never inside it.

This scenario SHALL include explicit negative-control evidence: a
computed value showing what a **deliberately incorrect** current-
profile interpretation — one that re-reads the proof-only current-
profile evidence above on every post-entry bar instead of using the
value locked at fill — would have selected (a different bar and/or a
different rule), compared against the actual, correct, locked-profile
result produced by the real new path, asserting they differ. Without
this negative control, a profile-drift fixture cannot be trusted to
actually distinguish the two interpretations (this mirrors the
negative-control discipline `research_service`'s I4 already established
at the execution-loop unit level — `test_i4_execution_parity.py::
test_negative_control_current_profile_lookup_would_have_chosen_a_
different_bar` — extended here to the full real pipeline, with the
current-profile side now explicitly sourced outside the v2 wire).

#### Scenario: Locked profile survives a real drift, full pipeline

- **WHEN** a real position enters under profile P through the full new
  path (`locked_exit_profile` read only from the matching entry
  opportunity), and the market's current profile — per Engine's native
  `EmaPullbackEvaluation` output or the old-BBB reference, captured
  proof-only alongside the run and never passed into the new execution
  path — changes to a different profile while the position remains
  open, and a later bar's locked-profile (P) signal stream fires
- **THEN** the position exits according to P's own signal fact, not
  whatever the current-bar profile's signal fact would have been at any
  earlier bar
- **AND** a deliberately incorrect current-profile interpretation,
  computed proof-only from that same outside-the-wire evidence, is
  shown to select a different bar and/or a different attributed rule
  than the actual, correct, locked-profile result.

#### Scenario: Lane A does not need to hold current profile constant

- **WHEN** Lane A's canonical always-on strategy spec is run
- **THEN** Lane A is not evidence for or against locked-profile
  lifecycle correctness either way — an always-on spec has no per-
  profile signal-exit indexing to diverge from a current-profile
  reading in the first place, so Lane A is simply non-discriminating
  for this property, not a case where "current profile" is asserted to
  stay constant
- **AND** locked-profile lifecycle correctness is proven exclusively by
  Lane B.

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
