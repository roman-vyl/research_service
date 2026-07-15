# Market candles-window migration

`GET /api/market/candles-window` is the first real BFF route migrated from BBB storage to Market Data Service.

## Preserved frontend contract

```text
symbol
 time frame
from
one of: to | to_open_time_ms
```

The response remains `{candles, coverage}`. Candle timestamps remain Unix seconds and OHLCV remains numeric JSON for Lightweight Charts.

## Internal replacement

```text
legacy: BFF → Db.range_get
new:    BFF → MarketDataPort → MDS /v1/candles
```

The compatibility adapter accepts both `BTCUSDT` and `BTCUSDT.P`, but always calls MDS with `BTCUSDT.P`.

MDS returns Decimal text; Research Service converts it to chart numbers only at the BFF presentation boundary.

## Coverage difference

Legacy storage could return a partial window and mark it truncated. MDS serves ready-only complete ranges and refuses out-of-bounds requests. Therefore successful migrated responses always have exact coverage and `truncated=false`. Errors remain errors rather than partial chart payloads.
