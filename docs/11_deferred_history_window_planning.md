# Deferred history-window planning

The final architecture must separate:

1. MDS available history;
2. Research Service evaluation range;
3. Strategy Engine expanded market-input/warmup range.

This work is recorded normatively in:

```text
openspec/changes/research-history-window-planning-v1/
```

It is intentionally deferred until the end of the current BFF and Research Service cutover. Until then, the known EMA-window limitation remains explicit: the current cache origin is the first requested range, not the earliest available market candle.
