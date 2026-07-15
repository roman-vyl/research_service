# Research Batch Experiments v1 Specification

## Requirements

1. A batch MUST contain at least one candidate and unique candidate/run identities.
2. Candidates MUST execute in request order.
3. One candidate failure MUST NOT prevent later candidates from running.
4. Successful candidates MUST use the existing authoritative single-instance backtest and atomic
   run artifact path.
5. Batch output MUST retain candidate order and expose completed/failed counts.
6. Batch artifacts MUST publish atomically and MUST be immutable for an experiment ID.
7. Production code MUST NOT import or execute `legacy_source`.
