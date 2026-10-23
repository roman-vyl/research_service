## 1. Implementation

- [x] 1.1 Read the Market Data lower bound once per preview and clamp the warmup start to it in the one-off preview and in the stack preview.
- [x] 1.2 No fallback when bounds fail; invalid request for a range ending before the first stored bar.

## 2. Tests

- [x] 2.1 One-off EMA100 near the start of history begins at the first stored bar.
- [x] 2.2 Cold stack EMA200 near the start of history begins at the first stored bar and reports it as the calculation origin.
- [x] 2.3 Failing bounds: no Strategy Engine call for either preview and the stack preview slot is released.
- [x] 2.4 Range ending before the first stored bar is a 400 for both previews.
