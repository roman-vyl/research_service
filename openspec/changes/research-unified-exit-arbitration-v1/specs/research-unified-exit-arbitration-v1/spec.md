# Research Unified Exit Arbitration v1 Specification

## Requirements

### One candidate pipeline
Research Service MUST arbitrate static and managed candidates together for each executable bar.

### Priority
The v1 order MUST be stop loss, managed stop, take profit, runtime protective, runtime take, runtime close/runtime exit, then signal.

### Active take profile
`disable_initial_tp` MUST suppress only the initial fixed take-profit candidate. It MUST NOT suppress stop, managed stop, runtime take or signal candidates.

### Bar identity
Candidates from different bar indices or timestamps MUST NOT be arbitrated together.

### Attribution
The selected `ExitFill` MUST preserve the winning candidate layer, rule ID, component ID and exit kind when present.
