# Research Managed Policy Consumption v1 Specification

## Requirements

### Policy ownership
Research Service MUST consume managed policy artifacts from Strategy Engine and MUST NOT recalculate managed phases or rules.

### Effective timing
A managed decision created at the end of bar N MUST NOT be executable on bar N and MUST become effective only at `effective_from_time_ms`.

### Managed stop execution
A managed stop crossed at bar open MUST fill at the open. An intrabar touch MUST fill at the stop level.

### Runtime exits
Runtime exit rules active for the inherited bar MUST become close-price candidates with the legacy candidate class derived from `exit_kind`.

### Attribution
Rule IDs, component IDs, and exit kinds available in Strategy Engine events MUST be preserved on Research execution candidates.
