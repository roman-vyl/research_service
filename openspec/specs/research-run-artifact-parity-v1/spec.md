# research-run-artifact-parity-v1 Specification

## Purpose
TBD - created by archiving change compact-strategy-evaluation-boundary-v1. Update Purpose after archive.
## Requirements
### Requirement: Persisted-artifact regression proof, after I5, before I7

I6 of the `compact-strategy-evaluation-boundary-v1` Master Plan SHALL
be proven by persisting one strategy instance's Run to artifacts and
confirming the persisted artifacts still carry the same common
execution/accounting/trade/path/summary facts I5 already proved equal
to the old-BBB reference in memory — not by re-deriving a full
structural model of both systems' Run output from scratch.

This is a distinct, later, and narrower gate than `research-
historical-execution-parity-v1` (I5): I5 proves execution/accounting
**facts** are identical between old-BBB semantics and the new path
in memory (entry, locked profile, initial protection, signal-exit
behavior, exit, attribution, accounting, `TradeRecord`, path metrics,
provenance). I6 is a **practical persistence-regression proof**: given
those facts are already known correct (I5), does writing them to the
new Run artifact bundle and reading them back preserve them exactly?
I6 SHALL NOT start until I5 passes; I7's `/range` cutover and I8's
batch redesign SHALL NOT start until I6 passes.

I6 is deliberately NOT a project to build a complete, general-purpose
canonicalizer that achieves full structural equality between old BBB's
entire Run artifact model and Research's entire Run artifact model.
The two systems' artifact shapes differ by design (different file
boundaries, different storage architecture, different optional
breakdowns) and reconciling every field of both into one union model
is not required to prove the thing that actually matters: that
persistence does not silently drop or corrupt a result.

#### Scenario: I5 and I6 prove different things

- **WHEN** I5's proof reports zero semantic diffs
- **THEN** that alone does not satisfy I6 — I6 additionally requires
  persisting a Run to artifacts and confirming the persisted content
  still matches, field for field, on the common comparison surface
  below
- **AND** conversely, I6 SHALL NOT be attempted before I5 has passed.

### Requirement: Same frozen market dataset on both sides

The old-BBB reference Run and the new Research Service Run SHALL be
produced from the same frozen, audited historical market dataset —
never from two independent live reads of the same nominal range, which
could observe different data if a new bar closes between them.

Dataset identity is the same identity `research-historical-execution-
parity-v1` already establishes for I5, reusing the same resolution
mechanism (`ResolveBacktestWindow`/`MarketDataPort.get_bounds`/
`audit_range`, resolved once): `ticker`, `timeframe` (Research's
canonical field name for what Strategy Engine's wire calls
`base_timeframe`), `from_ms`, `to_ms`, `bar_count`, `market_data_hash`.

The old-BBB reference does not consume Research's `MarketDataPort` at
all in its own architecture — it loads candles directly from its own
local store. A proof-only input adapter SHALL feed old BBB's reference
computation the exact same resolved candle set Research's pipeline
used (converted into old BBB's own expected in-memory OHLCV shape),
never letting old BBB independently query its own store for this
proof. This is a proof-only harness concern (I6.A) — it SHALL NOT
change old BBB's production architecture or Research's `MarketDataPort`
contract; no new Market Data Service interface is required.

#### Scenario: Same frozen market input

- **WHEN** the I6 proof harness resolves a `full_available` (or
  explicit) window once
- **THEN** both the old-BBB reference Run and the new Research Run are
  computed from that exact same resolved `market`/`market_data_hash`/
  candle set
- **AND** neither side performs its own independent live data
  resolution for this proof.

### Requirement: Same canonical strategy configuration

Both sides SHALL run an equivalent canonical strategy configuration.
Where Research's own identity mechanism applies (`strategy_id`,
`config_hash`, `instance_id` — `domain/strategy_instance.py`), it SHALL
be used to state the new side's identity. Old BBB has no equivalent
wrapper-identity fields; the proof SHALL instead demonstrate the two
sides consume semantically equivalent strategy configuration (the same
rule set, parameters, and profile definitions expressed in each side's
own native spec shape) — it SHALL NOT fabricate a shared ID old BBB has
no concept of.

#### Scenario: Same strategy semantics

- **WHEN** the I6 proof harness prepares both sides' strategy
  configuration
- **THEN** the new side's `strategy_id`/`config_hash`/`instance_id`
  identify the canonical strategy configuration used
- **AND** the old-BBB side's configuration is shown to express the same
  rules/parameters/profile definitions, even without a shared ID field.

### Requirement: Common-facts comparison surface (cross-system, narrow)

I6's cross-system comparison (persisted new-side artifacts vs. the
old-BBB reference) SHALL be scoped to only the facts both sides
actually, structurally have an equivalent for — not a union of every
field either side happens to carry. This is a closed, explicit list,
not an open-ended reconciliation exercise:

- **Trade facts** (per trade): side, entry/exit bar index or
  time-equivalent, entry/exit price, gross PnL, fees paid, net PnL
  (old BBB: `pnl`), return percentage, exit reason/kind
  (`exit_kind`↔`exit_kind`, `exit_instance_id`↔`exit_rule_id`,
  `exit_component_id`↔`exit_component_id`), hold duration
  (`hold_bars`), and — where old BBB's spec is profile-sensitive —
  entry/locked profile (`entry_profile`↔`locked_exit_profile`).
- **Accounting facts**: realised trade count, gross PnL, fees paid, net
  PnL, summed across the Run (`TradeAccountingResult` ↔ old BBB's
  `VariantMetrics.total`).
- **Path/exit-quality facts**: MFE/MAE price and percentage
  (`TradePathMetrics.mfe_*`/`mae_*` ↔ old BBB's
  `build_trade_quality_diagnostics` MFE/MAE fields) — only the
  quantities both sides actually compute the same way; fields either
  side computes that the other structurally cannot (e.g. `capture_
  ratio`/`giveback_*` on the new side, `quality_flag_breakdown` on the
  old side) are out of this comparison, not forced into it.
- **Summary facts**: trade count and aggregate PnL/fees as reported by
  each side's own lightweight summary (`metrics.json` ↔
  `<run_id>.summary.json`) — a sanity cross-check that the summary
  agrees with the underlying trades, on both sides.

Fields not on this list — old BBB's optional breakdowns
(`profile_breakdown`, `exit_reason_breakdown`, `fee_diagnostics`,
`bounce_counter_breakdown`, `quality_flag_breakdown`, etc.) and
Research's provenance/manifest/storage fields alike — are explicitly
OUT of the cross-system comparison. This is not an omission requiring
justification per field; it is this requirement's actual scope.

#### Scenario: Common facts match after persistence

- **WHEN** a Run is persisted on the new side and the same scenario is
  run through the old-BBB reference from the same frozen dataset and
  equivalent strategy configuration
- **THEN** every field on the common-facts comparison surface above
  agrees, trade for trade and in aggregate.

#### Scenario: A common-fact difference fails the gate

- **WHEN** any field on the common-facts comparison surface differs
  between the persisted new-side Run and the old-BBB reference
- **THEN** I6 fails — `I6_GATE_FAIL`.

#### Scenario: Fields outside the common surface are not compared cross-system

- **WHEN** old BBB's optional breakdowns, or Research's provenance/
  manifest/storage fields, are inspected
- **THEN** they are not diffed against the other side — see "New-side
  provenance/storage fields are verified, not cross-compared" below for
  how the new side's own fields are checked instead.

### Requirement: Persistence preserves the in-memory Run I5 already proved

I6's cross-system proof above establishes correctness once. Its
practical regression purpose is narrower and repeatable: for the same
Run, the common-facts values read back from the **persisted** artifact
bundle (`trades.json`, `metrics.json`, `execution_events.json`) SHALL
be identical to the values on the **in-memory** `SingleInstanceBacktestResult`
before persistence — i.e. serialization/storage/read-back introduces no
loss or corruption. This is the check I6 SHALL run every time the
persistence layer changes, without needing to re-run the old-BBB
reference each time.

#### Scenario: Read-back matches the in-memory result

- **WHEN** a `SingleInstanceBacktestResult` is persisted and its
  `trades.json`/`metrics.json`/`execution_events.json` are read back
- **THEN** every common-facts field (per the surface above) read back
  from the artifact bundle equals the corresponding field on the
  in-memory result that was persisted.

### Requirement: New-side provenance/storage fields are verified, not cross-compared

`run_id`, `manifest.json` (contract versions, per-file hashes,
`created_at_utc`), `artifact_path`, `instance_id`, `config_hash`,
`market_data_hash`, and market identity (`ticker`/`timeframe`/
`from_ms`/`to_ms`/`bar_count`) exist only on the new side (old BBB has
no equivalent wrapper-identity or content-hash concept) and are
therefore never compared against an old-BBB counterpart. I6 SHALL
instead verify these fields are internally correct on their own terms:
`market_data_hash`/market identity match the one frozen dataset both
sides actually ran against (see "Same frozen market dataset"); per-file
`sha256`/`size_bytes` in `manifest.json` match the actual persisted
file bytes; `instance_id`/`config_hash` match what
`derive_strategy_instance_id` computes for the request's own identity
subset (already an existing invariant — see
`artifacts.py::PersistSingleInstanceBacktest.execute`).

#### Scenario: Provenance is checked for internal correctness, not old-BBB equality

- **WHEN** a persisted Run's `manifest.json`/provenance fields are
  inspected
- **THEN** they are checked against the frozen dataset identity and the
  actual persisted file bytes/request identity
- **AND** they are never diffed against old BBB, which carries no
  equivalent field to compare them to.

### Requirement: No silent loss of common-surface content through the diagnostics split

I6's persistence/diagnostics split (`strategy_evaluation.json` becomes
the canonical `HistoricalExecutionProjection`; `result.json` references
it by identity; diagnostics become a separate, optional artifact — all
already normatively described in `research-run-artifacts-v1`) SHALL
NOT drop any field on the common-facts comparison surface above.
Diagnostic-only information (dense feature series, context data,
component evidence, potential-entry traces — already scoped as
separate/optional by `research-diagnostics-projection-v1`) was never
part of the common-facts surface and is unaffected by this requirement.

#### Scenario: Diagnostics split does not remove a common-facts field

- **WHEN** the persistence/diagnostics split is implemented
- **THEN** every field on the common-facts comparison surface is still
  present, in `trades.json`/`metrics.json`/`execution_events.json` or
  by direct reference from `result.json`
- **AND** no common-facts field is only reachable through the separate,
  optional diagnostic artifact.

