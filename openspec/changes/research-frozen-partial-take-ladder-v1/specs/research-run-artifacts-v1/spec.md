## ADDED Requirements

### Requirement: Partial take content in run artifacts

When a run has partial takes:

- `strategy_evaluation.json` SHALL carry each opportunity's
  `partial_takes`;
- `execution_events.json` SHALL carry `position_reduced` events;
- `trades.json` SHALL carry each record's `exit_fills` and
  `average_exit_price`.

Previously persisted artifacts without these fields SHALL still be read.

#### Scenario: Read an artifact written before this change

- **WHEN** `trades.json` from a run before this change is read
- **THEN** every record SHALL load with an empty `exit_fills` and no
  `average_exit_price`.

### Requirement: Byte-identical artifacts without partial takes

For a strategy without partial takes, on market data where no bar opens
beyond an active stop, managed-stop or final take level, every persisted
artifact SHALL be byte-identical to the artifact the same run produced
before this change:

- `strategy_evaluation.json`;
- `trades.json`;
- `execution_events.json`;
- `metrics.json`.

`result.json` SHALL differ only by its run identity.

Empty ladder fields SHALL be omitted rather than written as an empty list
or null.

A bar that opens beyond such a level MAY change the stop or final fill
from the open to the level, as the level-fill model requires. That
change SHALL NOT count as a regression.

#### Scenario: Regression gate without legs

- **WHEN** a recorded run without partial takes is re-executed and
  persisted after this change
- **THEN** each of those files SHALL have the same sha256 as before
- **AND** `result.json` SHALL equal the earlier one once `run_id` is
  removed.

#### Scenario: Gap-through bar without legs

- **WHEN** a run without partial takes has a long stop at 95 and a bar
  opens at 90
- **THEN** the trade SHALL close at 95, where it closed at 90 before
  this change
- **AND** the regression gate SHALL NOT treat that difference as a
  failure.
