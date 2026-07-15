# Research Unified Execution Loop v1 Specification

## Requirements

### Aligned inputs
The execution loop MUST reject Strategy Engine and MDS inputs whose market identity, bar count or timestamps differ.

### Position cardinality
The loop MUST maintain at most one open position for one strategy instance.

### Bar ordering
A position present at bar open MUST be evaluated for exit before any entry decision on that bar.

### Entry-bar isolation
A position opened at the current bar close MUST NOT be evaluated for exit on the same bar.

### Replacement-entry isolation
When a position existed at bar open, the loop MUST NOT open a replacement position on that bar, even if the existing position closes.

### Managed timing
Managed replay MUST be resolved once per opened position and MUST only affect bars identified by `effective_from_time_ms`.

### End-of-range state
The loop MUST preserve an unclosed position as `open`; it MUST NOT create a synthetic exit fill at the final candle.

### Output boundary
The v1 result MUST contain execution facts and events only. Fees, PnL, equity and trade metrics MUST NOT be calculated in this slice.
