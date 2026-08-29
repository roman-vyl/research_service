## ADDED Requirements

### Requirement: Canonical Run artifact parity proof, after I5, before I7

I6 of the `compact-strategy-evaluation-boundary-v1` Master Plan SHALL be
proven by running one strategy instance's full Run to persisted
artifacts through both the old-BBB reference and the new Research
Service Run pipeline, from the same frozen market dataset, and
comparing the canonical content of the two Runs for zero semantic
differences.

This is a distinct, later gate than `research-historical-execution-
parity-v1` (I5): I5 proves execution/accounting **facts** are identical
(entry, locked profile, initial protection, signal-exit behavior, exit,
attribution, accounting, `TradeRecord`, path metrics, aggregate
execution/accounting facts, provenance) — it does not require a
persisted Run artifact bundle to exist or be compared. I6 proves the
**persisted Run artifact bundle**, once materialized and written to
storage, carries the same canonical content as the old-BBB reference's
own persisted Run output — the full chain `strategy result → execution
→ accounting → metrics → result materialization → persisted Run
artifacts`. I6 SHALL NOT start until I5 passes; I7's `/range` cutover
and I8's batch redesign SHALL NOT start until I6 passes.

#### Scenario: I5 and I6 prove different things

- **WHEN** I5's proof reports zero semantic diffs
- **THEN** that alone does not satisfy I6 — I6 additionally requires
  running both sides' full Run-to-artifact pipeline and comparing the
  resulting persisted, canonicalized Run content
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
wrapper-identity fields (`instance_id`/`config_hash` as Research defines
them); the proof SHALL instead demonstrate the two sides consume
semantically equivalent strategy configuration (the same rule set,
parameters, and profile definitions expressed in each side's own
native spec shape) — it SHALL NOT fabricate a shared ID old BBB has no
concept of.

#### Scenario: Same strategy semantics

- **WHEN** the I6 proof harness prepares both sides' strategy
  configuration
- **THEN** the new side's `strategy_id`/`config_hash`/`instance_id`
  identify the canonical strategy configuration used
- **AND** the old-BBB side's configuration is shown to express the same
  rules/parameters/profile definitions, even without a shared ID field.

### Requirement: Canonical Run model and comparison surface

I6 SHALL compare, exactly (subject only to the explicit nondeterministic
allowlist below), a canonical Run model covering every content-bearing
field of both sides' actual Run output — not a field list invented for
this capability, but the union of what each side's real, already-
shipped Run artifacts actually carry:

- **Trades**: every `TradeRecord` field (`accounting/contracts.py`) on
  the new side, compared against old BBB's equivalent per-trade record
  fields (`execution/results.py::extract_trade_records`'s `direction`/
  `status`/`entry_time_ms`/`exit_time_ms`/`entry_price`/`exit_price`/
  `size`/`pnl`/`return_pct`/`exit_reason`/`gross_pnl`/`fees_paid`/
  `gross_return_pct`/`exit_group`/`exit_profile`/`exit_component_id`/
  `exit_instance_id`/`exit_kind`/`entry_idx`/`exit_idx`/`hold_bars`/
  `entry_profile`/`active_exit_profile` and its trade-quality-
  diagnostics fields) — see "Canonicalization" for the exact field-name
  mapping this requires (e.g. `entry_idx`↔`entry_bar_index`,
  `exit_instance_id`↔`exit_rule_id`).
- **Execution events**: the new side's `ExecutionEvent` sequence
  (`domain/execution.py`) against old BBB's equivalent per-trade
  entry/exit facts (old BBB has no separate execution-event stream —
  its trade record already carries entry+exit together; the canonical
  model reconciles this structural difference explicitly, it does not
  drop either side's content — see "Artifact relocation is allowed").
- **Accounting**: every `TradeAccountingResult` field
  (`accounting/contracts.py`) against old BBB's equivalent `SideMetrics`/
  `VariantMetrics.total` aggregates (`execution/result_models.py`) —
  `realised_trade_count`↔`trades`, `gross_pnl`↔`pnl`+`fees_paid`
  reconciliation, `final_equity` (new-side-only concept; old BBB has no
  equity curve at N=1 — treated as new-side-only canonical content, not
  a diff, since old BBB's Run model never carried an equity field to
  compare against).
- **Path/exit-quality metrics**: the new side's `TradePathMetrics`
  (mfe/mae/captured/giveback) against old BBB's
  `build_trade_quality_diagnostics`/`path_diagnostics_summary` output
  (`execution/trade_analyzer.py`) — semantically equivalent trade-path
  quality facts, compared field-for-field where both sides compute the
  same underlying quantity (see "Canonicalization" for the mapping;
  fields either side computes that the other structurally cannot are
  new-side-only or old-side-only canonical content, not diffed against
  a fabricated counterpart on the other side).
- **Provenance**: `instance_id`, `config_hash`, `market_data_hash`,
  `bar_count`, market identity (`ticker`/`timeframe`/`from_ms`/`to_ms`)
  on the new side, against old BBB's `symbol`/`timeframe`/`candles`/
  `data_range{from_open_time_ms,to_open_time_ms}` (`execution/
  results.py::build_research_run_payload`).
- **Run-level summaries**: the new side's `metrics.json` content and
  compact run-view surface (`run_views.py`) against old BBB's
  `<run_id>.summary.json` (`build_compact_report_payload`) — both are
  lightweight projections of the same underlying trades/accounting
  facts; the canonical model compares the underlying facts they
  project from, not the two summary files' own differing shape.

Exhaustively enumerating old BBB's every optional breakdown field
(`profile_breakdown`, `exit_reason_breakdown`, `fee_diagnostics`,
`bounce_counter_breakdown`, `quality_flag_breakdown`, etc. —
`execution/result_models.py::VariantMetrics`) is not required by this
requirement: those are all pure aggregations *derived* from the
trade-level fields already in the comparison surface above. I6 SHALL
prove the underlying trade-level facts are identical; a derived
aggregate breakdown that disagrees while its underlying trades agree
would indicate a bug in the aggregation code being compared (Research's
`run_views`/old BBB's `results.py` breakdown builders), not a semantic
divergence this capability's Run-model comparison is scoped to catch on
its own — such an aggregation-layer bug, if found, is reported as its
own finding, not folded silently into this gate's pass/fail.

#### Scenario: Canonical Run equality

- **WHEN** both sides' canonical Run models are built from the same
  frozen dataset and the same strategy configuration, and canonicalized
  per the allowlist below
- **THEN** the two canonical Run models are structurally identical.

#### Scenario: Semantic difference fails

- **WHEN** any content-bearing field in the canonical Run model differs
  between the two sides (not on the nondeterministic allowlist)
- **THEN** I6 fails — `I6_GATE_FAIL` — regardless of how small the
  difference is.

### Requirement: Explicit, closed nondeterministic-metadata allowlist

The canonicalization step SHALL exclude from comparison only fields on
the explicit, closed allowlist below — every other field SHALL remain
in scope for exact comparison. Only the following fields MAY be
excluded from canonical comparison,
each because it is proven, by reading the actual code that generates
it, to be non-semantic storage/transport metadata rather than a
computed trading/strategy fact:

- `run_id` — Research: `f"run_{uuid.uuid4().hex}"`
  (`materialize_backtest_outcome.py::_generate_run_id`); old BBB:
  `build_run_id(utc, ...)`, embeds a UTC timestamp
  (`execution/results.py`). Neither is a function of trade/strategy
  content.
- `created_at`/`created_at_utc` — Research:
  `datetime.now(UTC).isoformat()` (`artifacts.py`'s manifest); old BBB:
  the same wall-clock value passed into `build_research_run_payload`.
- Absolute filesystem paths — Research's `artifact_path`
  (`PersistedRunArtifacts`) and old BBB's `default_results_dir()`-
  derived paths; both are storage locations, not Run content.
- Host/process metadata — neither side's canonical Run model as
  identified above carries any (confirmed by the field lists in
  "Canonical Run model" — if a future field of this kind is added to
  either side, it requires its own explicit addition to this allowlist,
  not an implicit exclusion).
- Serialization formatting — JSON key order, indentation, whitespace:
  governed by "Deterministic canonical serialization" below, not a
  content difference.

No other field, and no wildcard pattern (`metadata.*`, `diagnostics.*`,
`provenance.*`, or similar), MAY be excluded. An exclusion not on this
list requires its own explicit OpenSpec amendment to this requirement,
with the same code-backed justification given above for each existing
entry.

#### Scenario: Nondeterministic metadata does not create a false failure

- **WHEN** `run_id`, `created_at`/`created_at_utc`, or an artifact's
  absolute filesystem path differs between the two sides' Runs
- **THEN** this alone does not fail I6 — these fields are normalized
  (ignored, or replaced with a placeholder) before canonical comparison.

#### Scenario: An unlisted field cannot be excluded by wildcard

- **WHEN** a proof implementation proposes excluding a field or a
  wildcard-matched group of fields not explicitly named in the
  allowlist above
- **THEN** that exclusion is rejected — the field remains in scope for
  exact comparison, or its exclusion requires its own explicit
  amendment to this requirement first.

### Requirement: No information loss through storage relocation

I6's persistence/diagnostics split (`strategy_evaluation.json` becomes
the canonical `HistoricalExecutionProjection`; `result.json` references
it by identity; diagnostics become a separate, optional artifact — all
already normatively described in `research-run-artifacts-v1`) SHALL
NOT be used to justify excluding content-bearing information from the
canonical Run model comparison merely because its storage location or
file boundary changed. Content that old BBB's Run persisted and that
is execution-semantic (a trading/strategy fact, not diagnostic-only)
SHALL either:

1. appear in the new side's canonical Run model directly; or
2. be shown to have been relocated to a different canonical artifact
   the comparison already reads (e.g. an execution-semantic fact now
   living in `HistoricalExecutionProjection`/`execution_events.json`
   instead of a single monolithic file); or
3. have its removal separately, explicitly approved by its own
   OpenSpec amendment — never silently dropped from the comparison
   surface as an implementation convenience.

Diagnostic-only information (dense feature series, context data,
component evidence, potential-entry traces — the content `research-
diagnostics-projection-v1` already scopes as separate/optional) is
exempt from this requirement's "MUST appear in canonical Run model"
clause: it was never an execution-semantic fact, and its relocation to
an explicitly-generated, separate diagnostic artifact is the
architecture I6 implements, not information loss. Where EXPLORE work
for I6 finds a specific field is ambiguous between execution-semantic
and diagnostic-only, that ambiguity SHALL be resolved and recorded
(design.md) before I6's canonicalization step treats it either way.

#### Scenario: Missing information fails

- **WHEN** the new side's Run artifact bundle lacks a content-bearing
  field the old-BBB reference's Run carried, and that field is neither
  present in the new canonical Run model nor shown to have been
  relocated to another canonical artifact the comparison reads
- **THEN** I6 fails — the field's absence is not resolved by excluding
  it from comparison.

#### Scenario: Artifact relocation is allowed

- **WHEN** informational content moves from one file/artifact to
  another between old BBB's Run and the new Research Run (for example,
  entry+exit facts that were one old-BBB trade record now split across
  `execution_events.json` and `trades.json`)
- **THEN** this is not a failure by itself — the canonical Run model
  reads the content from wherever it now lives on each side, and the
  comparison proceeds on that reconciled canonical model.

#### Scenario: Diagnostics split preserves information

- **WHEN** the new side's mandatory Run bundle is compact (no dense
  diagnostic data) and diagnostics are generated separately/optionally
- **THEN** every content-bearing, execution-semantic field old BBB's
  Run carried is still traceable through the canonical Run model (the
  mandatory bundle, the separate diagnostic artifact, or both)
- **AND** no execution-semantic content is simply absent with no
  canonical home.

### Requirement: Deterministic canonical serialization

Canonical Run models on both sides SHALL be produced by a deterministic
serialization procedure (sorted keys, a fixed numeric representation,
fixed whitespace, UTF-8) so that repeated canonicalization of the same
underlying Run content is stable and reproducible. Where both sides'
canonical models are serialized by that same one deterministic
serializer, their canonical JSON representations SHOULD be
byte-identical after the allowlisted fields are normalized —
byte-identical **canonical** JSON is a natural consequence of exact
canonical structural equality plus deterministic serialization, not an
independent new requirement to prove separately.

This requirement does NOT mandate byte equality of the two sides'
*original, native* production artifact files (old BBB's own JSON
report shape and Research's own bundle files legitimately differ in
envelope/storage structure, file boundaries, and formatting) — only the
derived canonical representation used for comparison is held to
deterministic (and consequently byte-identical, once canonicalized)
output.

#### Scenario: Deterministic serialization

- **WHEN** the same canonical Run model is serialized twice by the
  canonical serializer
- **THEN** the two serialized outputs are byte-identical
- **AND** where both sides' canonical models are equal per "Canonical
  Run equality," their canonical serialized JSON is byte-identical too.

#### Scenario: Native artifact byte equality is not required

- **WHEN** old BBB's native Run JSON file and Research's native Run
  artifact bundle files are compared directly, without canonicalization
- **THEN** byte-for-byte equality of those native files is not a
  requirement of this capability — only their canonicalized
  representations are held to that standard.
