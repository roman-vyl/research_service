## Context

See `proposal.md` for motivation. Research already maintains monotonic
`best_price`/`worst_price`, calculates MFE, freezes entry-to-initial-stop risk in
managed trade state, advances decisions onto `next_time_ms`, and performs
side-relative tighten-only stop arbitration. The eager timeline and incremental
production path currently duplicate the legacy entry-offset candidate formula
and must remain parity-equivalent.

The incoming Engine projection hides strategy components and parameters. The
new fields are therefore a closed execution contract, not permission for
Research to interpret strategy policy.

## Goals / Non-Goals

**Goals:**

- Strictly decode old and new projected stop actions.
- Execute all formulas from generic position state and opaque distance series.
- Keep eager and incremental state identical and preserve current events/timing.
- Integrate new candidates through the existing managed-stop and unified-exit path.

**Non-Goals:**

- Evaluating Engine component ids or validating raw strategy configuration.
- Recomputing initial risk from an active stop.
- Changing managed stop hit/fill, gap, partial-take, accounting, or arbitration semantics.
- Calling managed replay once per historical trade.

## Decisions

### D1. DTO defaults old wire to `entry_offset`

The stop-action DTO adds `stop_formula` with an in-memory default of
`entry_offset` and optional `trigger_distance_id`. Validation requires:

- `entry_offset`: existing `distance_id`, no trigger reference;
- `initial_r_lock` or `initial_r_trailing`: existing action `distance_id` plus
  an existing `trigger_distance_id`.

The projection-level dangling-reference validator checks both references. An
unknown formula fails discriminated DTO decoding. This accepts old documents
without weakening malformed-new-document handling.

### D2. One formula helper serves eager and incremental paths

A generic helper receives the decoded stop rule, projection, bar index, side,
entry price, current monotonic MFE price, and frozen initial risk. It returns no
candidate when phase is inactive, an R trigger is unmet, a referenced value is
unavailable, or initial risk is absent/non-positive. Otherwise it returns:

- entry offset: current `entry +/- price_distance` behavior;
- R lock: `entry +/- lock_r * initial_risk`;
- R trailing: long `mfe - trail_r * initial_risk`, short
  `mfe + trail_r * initial_risk`.

Both timeline builders call this helper before the unchanged `_tightened_stop`.
This removes formula duplication without moving strategy policy into Research:
all branches are named by the closed projection enum.

### D3. Frozen risk and MFE remain state facts

Eager consumption derives initial risk once before its loop. Incremental
initialization derives it once from initial protection and every returned state
carries the same value. Neither path reads `active_stop_price` when computing
risk. Existing max-high/min-low updates remain the only source of MFE.

### D4. Timing, events, and execution remain unchanged

The helper produces a candidate during source bar N processing. Existing state
construction exposes a tightened stop only at `next_time_ms`; event metadata
continues to identify `effective_from_bar: N+1`. The current rule-id retention
for non-tightening candidates remains unchanged. `collect_managed_exit_candidates`
and unified arbitration receive the same effective-state shape as before.

### D5. Compatibility is tested at both contract and production boundaries

DTO tests cover old payloads and all invalid field combinations. Formula tests
cover eager/incremental parity and both sides. Production-loop tests prove that
multiple advances lead to execution at the latest effective stop, without a
managed-replay HTTP fallback. Existing entry-offset fixtures remain unchanged.

## Risks / Trade-offs

- [A permissive default could hide malformed new payloads] → Default only an
  omitted formula; validate trigger presence/absence based on the resolved enum.
- [Eager and incremental calculations could drift] → Centralize candidate
  calculation and retain a bar-for-bar parity test containing both new formulas.
- [NaN/None distance values could produce candidates] → Treat unavailable or
  non-finite referenced values as no candidate, consistent with projection
  fail-closed behavior.
- [Engine may emit new payloads before Research deploys] → Deploy Research's
  backward-compatible decoder first and activate new strategy specs last.

## Migration Plan

1. Deploy Research with the backward-compatible DTO and formula executor.
2. Deploy the coordinated Engine projection change.
3. Enable strategy specs using initial-R stops only after both services are compatible.
4. Roll back active usage by removing new components; legacy entry-offset payloads
   continue to decode and execute unchanged.
