# Research entry execution v1

## Requirement: aligned decisions
Entry execution SHALL consume only a StrategyEvaluationResult and MarketFrame that describe the same canonical bar grid.

## Requirement: legacy-compatible signal semantics
When both long and short entry decisions are true on a flat bar, long SHALL win. The reference entry price SHALL be the signal bar close.


## Requirement: ready entry policy
An entry decision SHALL be executable only when the same side is ready according to Strategy Engine `stop_ready`.

## Requirement: one open position
An open position for an instance SHALL block subsequent entry decisions until a later execution change closes it.

## Requirement: no legacy runtime
The implementation SHALL NOT import or execute `legacy_source`.
