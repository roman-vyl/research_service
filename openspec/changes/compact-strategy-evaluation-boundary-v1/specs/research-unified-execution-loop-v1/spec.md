## MODIFIED Requirements

### Requirement: Aligned inputs

The execution loop MUST reject Strategy Engine and Market Data Service
inputs whose market identity, `market_data_hash`, `bar_count`, or
declared range differ. Every projection element's `bar_index` MUST fall
within `[0, bar_count)` for the aligned range; the loop MUST reject an
evaluation containing a `bar_index` outside that range. (Strategy
Engine no longer sends a per-bar timestamp array — `bar_index` plus
`market_data_hash` plus `bar_count` is the alignment contract; the
loop's own `MarketFrame` for that identical `market_data_hash` is the
sole source of each bar's actual timestamp.)

#### Scenario: Misaligned market identity

- **WHEN** the Strategy Engine and MDS inputs to the loop describe
  different market identity, `market_data_hash`, `bar_count`, or range
- **THEN** the loop rejects the run rather than executing against
  mismatched data.

#### Scenario: Out-of-range bar_index is rejected

- **WHEN** a projection element's `bar_index` falls outside `[0, bar_count)`
  for the aligned range
- **THEN** the loop rejects the run rather than executing against an
  ambiguous or out-of-bounds decision.

## ADDED Requirements

### Requirement: Locked exit profile and initial-protection lifecycle

At entry fill (`domain/execution.py::PositionState`, not
`execution/protection.py` — that module holds the resolution *function*,
`resolve_initial_protection`, not the state type), the loop SHALL:

1. capture the matching `ExecutableEntryOpportunity`'s
   `locked_exit_profile` value onto the resulting `PositionState` and
   hold it fixed for that position's entire life;
2. resolve `initial_stop`/`initial_take` **from that same entry
   opportunity** into Research-owned absolute levels (existing
   `InitialProtection`/`resolve_initial_protection` semantics), and
   store them on `PositionState` at this point only.

`initial_stop`/`initial_take` levels are **never re-resolved or
re-looked-up from the projection on a later bar** — this mirrors the
reference (old-monolith) execution model's entry-bar-only SL/TP read,
already established and unaffected by this revision. Every subsequent
bar the position remains open, the loop checks OHLC against the
already-stored initial/current protection levels per existing static-
exit-arbitration semantics (`research-static-exit-arbitration-v1`,
unchanged) — it does not perform a fresh per-bar protection lookup keyed
by profile.

**Only signal-exit lookup is per-bar and profile-keyed**: every
subsequent open bar, signal-exit candidate lookup SHALL be
`HistoricalExecutionProjection.signal_exit_events[side][position
.locked_exit_profile][current_bar_index]` — the position's own locked
profile, never whichever profile is active on the current bar. Managed
protection (`execution/managed_policy.py`) remains a separate channel,
unaffected by this requirement — confirmed zero overlap with range-
evaluation consumption.

#### Scenario: Locked profile survives a later profile change

- **WHEN** a position enters under one exit profile and the market's
  current exit profile changes on a later bar while that position
  remains open
- **THEN** signal-exit candidate lookups for that position continue to
  use the profile locked at entry, not the now-current profile.

#### Scenario: Locked profile and initial protection are captured once, at fill

- **WHEN** a position is opened
- **THEN** its `locked_exit_profile` and `initial_stop`/`initial_take`
  levels are set once, from the matching entry opportunity, at fill time
- **AND** none of these are reassigned or re-looked-up for the life of
  that position.

#### Scenario: A null leg from the entry opportunity means no fabricated protection level

- **WHEN** the matching entry opportunity's `initial_stop` (or
  `initial_take`) is `null` (no applicable rule configured for that leg)
- **THEN** `PositionState`'s corresponding protection level is absent,
  not synthesized or defaulted to any value
- **AND** this does not by itself prevent the position from opening —
  only the configured leg(s) participate in subsequent stop/take
  checking, matching the reference model's independent-leg readiness
  semantics.

#### Scenario: Subsequent bars check stored levels, not a fresh profile-keyed protection lookup

- **WHEN** an open position is evaluated on a bar after entry
- **THEN** its stop/take check is against the levels already stored on
  `PositionState` at fill time
- **AND** no `(side, locked_exit_profile, bar_index)`-keyed protection
  lookup against the projection occurs for this purpose — that lookup
  pattern applies to signal-exit candidates only.

### Requirement: Exit attribution restoration

Realised trade and execution-event records SHALL carry
`exit_reason`/`exit_rule_id`/`exit_component_id`/`exit_kind`/
`exit_layer` attribution sourced from Strategy Engine's `ExitAttribution`
(`rule_id`, `component_id`, `exit_kind` — see companion `strategy_engine`
capability) on the specific initial-protection leg or signal-exit
candidate that triggered the exit — not a coarse category synthesized
independently of that attribution. Where multiple applicable rules were
aggregated into a single reported ratio at entry, the attribution SHALL
reflect the same deterministic rule selection Strategy Engine's
projection used (Research does not independently re-select an
attribution owner).

`exit_layer` is **not** carried on Strategy Engine's wire —
`ExitAttribution` has no `layer` field (companion capability). Research
Service SHALL derive `exit_layer = "exit_policy"` as a canonical
constant for every exit attributed from
`HistoricalExecutionProjection` data; this is a fixed derivation, not an
independent Research decision.

#### Scenario: Exit attribution matches Engine's projection attribution

- **WHEN** a position closes
- **THEN** its trade record's `exit_rule_id`/`exit_component_id`/
  `exit_kind` match the `ExitAttribution` Strategy Engine's projection
  reported for the specific initial-protection leg or signal-exit
  candidate that triggered the exit
- **AND** `exit_layer` is the derived constant `"exit_policy"`.

#### Scenario: Attribution is not degraded to an always-on-only category

- **WHEN** a trade exits under a locked profile other than a default/
  always-on rule set
- **THEN** its attribution reflects that specific profile's rule/
  component, not a generic always-on category.

## ADDED Requirements

### Requirement: Single-instance production wiring (I7)

`RunSingleInstanceBacktest` SHALL drive this execution loop from a real
`HistoricalExecutionProjectionDTO` obtained from Strategy Engine's live
`/strategy-evaluations/range` route (post I7 cutover), not from an
in-process proof harness. The batch path
(`application/experiments/run_batch.py`) SHALL continue to use its
existing legacy-shape execution path unmodified — this loop's I7 wiring
change applies to the single-instance production caller only. Full
cutover requirements (shared-infrastructure handling, compatibility,
rollback, E2E gate) are normative in `research-production-cutover-v1`;
this requirement records only that this loop itself is the thing being
wired to a real route for the first time.

#### Scenario: Single-instance run is driven by the real route

- **WHEN** a production `RunSingleInstanceBacktest.execute()` call runs
  after I7
- **THEN** this execution loop consumes a `HistoricalExecutionProjectionDTO`
  decoded from a real HTTP response of the live, cut-over `/range` route
- **AND** batch's use of this loop's legacy-shape counterpart is
  unaffected.
