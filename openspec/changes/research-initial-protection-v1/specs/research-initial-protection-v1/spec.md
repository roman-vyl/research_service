# Research initial protection v1

## Requirement: readiness-gated entry
A side SHALL be executable only when both its Strategy Engine entry decision and its `stop_ready` value are true on the same aligned bar.

## Requirement: authoritative ratios
Research Service SHALL consume `stop_loss_ratio` and `take_profit_ratio` from Strategy Engine and SHALL NOT recalculate strategy policy.

## Requirement: legacy-compatible anchor
Under compatibility profile `bbb_v1`, initial stop/take prices SHALL be anchored to the signal-bar close, even when explicit execution slippage changes the entry fill price.

## Requirement: side-aware levels
Long and short stop/take levels SHALL use the reviewed legacy formulas and SHALL reject invalid non-positive prices.

## Requirement: no legacy runtime
The implementation SHALL NOT import or execute `legacy_source`.
