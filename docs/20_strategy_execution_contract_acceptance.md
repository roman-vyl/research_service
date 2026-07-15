# Strategy execution contract acceptance v1

## Why this exists

Before implementing the Research Service simulator, the consumer must prove that the Strategy Engine response is executable without reading legacy BBB code or guessing missing semantics.

This acceptance layer does not execute a trade. It validates the hand-off at the exact seam:

`StrategyEvaluationResult + MarketFrame → future execution simulator`.

## Checks

- the HTTP request uses the real nested Strategy Engine request schema;
- response contract versions are supported;
- ticker, timeframe and half-open range match MDS;
- every Strategy Engine timestamp matches the corresponding MDS candle `open_time_ms`;
- entry masks contain one value per bar;
- static exit policy contains one value per bar for signal exit, stop loss, take profit and stop readiness;
- `market_data_hash` is present for provenance;
- managed decisions explicitly state next-bar effectiveness.

## Important current limitation

MDS does not yet expose the same canonical `market_data_hash`. Until the deferred history-window/coverage work is implemented, Research Service verifies exact market identity using ticker, timeframe, range, bar count and every candle timestamp. It records the Strategy Engine hash but cannot independently compare it to an MDS hash yet.

## Defect found and fixed

The previous Research Service range client used an obsolete flat request and expected a nonexistent `identity` response object. The new client uses the implemented Strategy Engine request and response contracts and adds managed replay to the typed port.
