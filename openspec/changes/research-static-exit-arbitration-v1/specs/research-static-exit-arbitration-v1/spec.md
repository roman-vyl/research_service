# Research static exit arbitration v1

## Requirement: static policy ownership
Research Service SHALL consume Strategy Engine signal-exit decisions and existing `InitialProtection` levels and SHALL NOT recalculate strategy exit policy.

## Requirement: bar-open eligibility
Static exits SHALL be evaluated only for positions that were open at the start of the bar. The entry bar SHALL NOT close the newly opened position.

## Requirement: distance fill semantics
A stop or take level crossed by the bar open SHALL fill at the open. Otherwise an intrabar touch SHALL fill at the level.

## Requirement: signal fill semantics
A true aligned signal-exit decision SHALL create a candidate filled at the current bar close.

## Requirement: deterministic same-bar priority
Policy `v1` SHALL select stop loss before take profit before signal and SHALL retain losing candidates.

## Requirement: no legacy runtime
Production code SHALL NOT import or execute `legacy_source`.
