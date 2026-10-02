# Spec Delta

## Purpose

Define how Research Service executes Strategy Engine's frozen partial take
ladder: decoding the legs, freezing their levels and quantities at entry,
the same-bar rule that orders stop, legs, final take and remaining exits,
and the reduction facts a position records before it closes.

## ADDED Requirements

### Requirement: Partial take decoding

Research SHALL decode an optional `partial_takes` list on an executable
entry opportunity. Each leg is `{take_id, ratio, fraction_of_initial,
attribution}`. Research SHALL reject the projection when:

- a ratio is not finite or not positive;
- `fraction_of_initial` is outside `(0, 1)`, or the fractions sum to 1 or
  more;
- a `take_id` repeats or differs from `attribution.rule_id`;
- an attribution `exit_kind` is not `"partial_take"`;
- `"partial_take"` appears outside `partial_takes`.

#### Scenario: Opportunity without legs

- **WHEN** an opportunity has no `partial_takes` key
- **THEN** it SHALL decode exactly as before this change, with an empty
  ladder.

#### Scenario: Fractions reaching one

- **WHEN** an opportunity carries legs with fractions 0.5 and 0.5
- **THEN** decoding SHALL fail and the candidate SHALL fail closed.

#### Scenario: Partial take kind on the final take

- **WHEN** `initial_take.attribution.exit_kind` is `"partial_take"`
- **THEN** decoding SHALL fail.

### Requirement: Frozen leg levels and quantities

When a position opens, Research SHALL resolve each leg of its opportunity
to an absolute level `anchor × (1 + ratio)` for long and
`anchor × (1 − ratio)` for short. The anchor and formula SHALL be the
ones used for the final take. The leg quantity SHALL be
`fraction_of_initial × Q0`, where Q0 is the entry fill quantity, without
rounding. Levels and quantities SHALL NOT change afterwards.

#### Scenario: Long leg level

- **WHEN** a long position opens with anchor 100 and a leg with ratio
  0.01 and fraction 0.25, and Q0 is 100
- **THEN** the leg level SHALL be 101 and its quantity 25.

#### Scenario: Non-positive short leg level

- **WHEN** a short leg ratio would put its level at zero or below
- **THEN** the position SHALL NOT open and the candidate SHALL fail
  closed, as for a non-positive final take.

#### Scenario: Leg beyond the final take

- **WHEN** a long position has a final take at 108 and a leg at 110
- **THEN** both levels SHALL be resolved and stored without comparing
  them.

### Requirement: Stop wins without take traversal

On a bar after the entry bar, if a stop-loss or managed-stop candidate
exists, Research SHALL run the existing arbitration unchanged. The stop
SHALL close all remaining exposure, and no leg SHALL fill on that bar.

#### Scenario: Stop and legs on one bar

- **WHEN** a long entry at 100 has a stop at 95 and legs at 101 and 103,
  and a bar has high 104 and low 94
- **THEN** the stop SHALL close the whole remaining quantity at 95
- **AND** no leg SHALL fill.

### Requirement: Price-ordered take traversal with a terminal final

On a bar after the entry bar without a stop candidate, Research SHALL
collect the touched take levels:

- every unfilled leg whose level the bar reached (high ≥ level for long,
  low ≤ level for short);
- the final take when its `take_profit` candidate exists.

Research SHALL traverse them by distance from the anchor, nearest first.
At an equal level a leg SHALL come before the final take, and legs
SHALL keep wire order. A leg SHALL fill at exactly its level and the
traversal SHALL continue. The final take SHALL close the remainder
through the existing `take_profit` candidate and SHALL end the
traversal.

#### Scenario: Legs then final on one bar

- **WHEN** a long position with Q0 100, legs 101 and 103 of 25% each and
  a final take at 108 meets a bar with high 109
- **THEN** Research SHALL fill 25 at 101 and 25 at 103
- **AND** close the remaining 50 at 108 through the final take.

#### Scenario: Leg beyond the final take never fills

- **WHEN** a long position with Q0 100 has legs at 102, 106 and 108
  (25% each) and a final take at 104, and a bar reaches high 110
- **THEN** Research SHALL fill 25 at 102 and close the remaining 75 at
  104
- **AND** SHALL NOT fill the legs at 106 and 108.

#### Scenario: Short mirror

- **WHEN** a short position with Q0 100 and anchor 100 has legs at 99
  and 97 (25% each) and a final take at 92, and a bar reaches low 91
- **THEN** Research SHALL fill 25 at 99 and 25 at 97, then close 50 at
  92.

#### Scenario: Leg level equals the final level

- **WHEN** a leg and the final take share one level and the bar
  touches it
- **THEN** the leg SHALL fill first and the final take SHALL close the
  remainder at the same price.

### Requirement: Remainder after an incomplete traversal

When the traversal does not reach the final take and the position is
still open, Research SHALL arbitrate the remaining runtime and signal
candidates of that bar exactly as before this change, against the
remaining quantity.

#### Scenario: Leg and signal on one bar

- **WHEN** a leg fills on a bar that also has a signal exit
- **THEN** the leg SHALL fill at its level first
- **AND** the signal SHALL close the remainder at the bar close.

#### Scenario: Leg earlier, stop later

- **WHEN** a 25% leg filled on an earlier bar and a later bar touches
  the stop
- **THEN** the stop SHALL close the remaining 75%.

### Requirement: Leg eligibility

A leg SHALL fill at most once per position and never on the entry bar.
`disable_initial_tp` SHALL suppress only the final take; legs SHALL stay
eligible. A leg SHALL fill at exactly its level, under the same
level-fill model as the stop and the final take
(`research-static-exit-arbitration-v1` "Distance fill semantics").

#### Scenario: Entry bar reaches every level

- **WHEN** the entry bar's high exceeds every leg level
- **THEN** no leg SHALL fill on that bar.

#### Scenario: Final take disabled

- **WHEN** managed policy has set `disable_initial_tp`, and a later bar
  reaches both 25% legs and the former final level
- **THEN** both legs SHALL fill
- **AND** the remaining 50% SHALL stay open.

#### Scenario: Bar opens beyond a leg

- **WHEN** a long bar opens above an unfilled leg level
- **THEN** the leg SHALL fill at exactly its level, not at the open.

#### Scenario: Bar opens beyond legs and final

- **WHEN** a long position with Q0 100 has a leg at 103 (25%) and a
  final take at 108, and a bar opens at 112
- **THEN** Research SHALL fill 25 at 103 and close the remaining 75 at
  108, not at 112.

### Requirement: Reduction facts

Each leg fill SHALL be recorded as a position reduction with:

- the fill identity `reduce:{position_id}:{take_id}`;
- the bar and time;
- the level and fill price, which are equal;
- the quantity and `fraction_of_initial`;
- the attribution (`rule_id`, `component_id`, `exit_kind`
  `"partial_take"`).

The remaining quantity SHALL be derived as Q0 minus the sum of
reductions, never stored. The closing exit fill SHALL keep its current
meaning: the fill that closes the remainder.

#### Scenario: Closed position with reductions

- **WHEN** a position closes after two reductions
- **THEN** its execution SHALL list both reductions in bar and traversal
  order
- **AND** its exit fill SHALL close the remaining quantity.

### Requirement: Reduction events

Every reduction SHALL emit a `position_reduced` execution event. The
event SHALL come after the position's `entry_filled` event and before
any `exit_filled` event of the same bar, carrying the reduction's facts
and the remaining quantity after it. An `entry_filled` event SHALL list
the resolved leg levels only when the position has legs.

#### Scenario: Leg and final on one bar

- **WHEN** a leg and the final take fill on one bar
- **THEN** the events SHALL be `position_reduced` then `exit_filled`.

### Requirement: Open position with reductions

A position still open at range end SHALL stay open, with its reductions
reported in execution events. It SHALL NOT produce a trade record or a
realised equity update.

#### Scenario: Range ends after a leg

- **WHEN** a 25% leg filled and the range ends with the position open
- **THEN** `execution_events.json` SHALL contain the `position_reduced`
  event and the `position_left_open` event
- **AND** `trades.json` SHALL contain no record for that position.
