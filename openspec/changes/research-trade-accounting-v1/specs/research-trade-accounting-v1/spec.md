# Research Trade Accounting v1 Specification

## Requirements

1. Only closed `PositionExecution` items produce `TradeRecord` objects.
2. Gross PnL is side-aware and multiplied by executed quantity.
3. Entry and exit fees are calculated independently from actual fill notionals.
4. Net PnL equals gross PnL less all fees.
5. Equity changes only by realised net PnL.
6. MFE and MAE use candle high/low from entry through exit, inclusive.
7. Open positions at range end are reported but not force-closed.
