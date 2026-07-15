# Design

`ExecutionLoopResult + MarketFrame + AccountingPolicy -> TradeAccountingResult`.

The accounting layer owns fees, realised gross/net PnL, equity progression and trade-path diagnostics. Open positions are not force-closed or counted as realised trades.
