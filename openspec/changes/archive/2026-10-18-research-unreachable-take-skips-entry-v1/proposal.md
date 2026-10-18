## Why

On a volatile bar a take-profit of many ATR can reach a distance larger than the entry price.
For a short the take level `anchor * (1 - ratio)` is then zero or negative. Research Service
rejects this with `InvalidRequest("take-profit ratio produces a non-positive price")`, which
fails the whole Calculate job: on SOL (FTX crash short, ATR48 = 3.9% of price, take 44 ATR) every
cell of the surface failed. A take order at a non-positive price cannot be placed on the
exchange, so such an entry cannot be opened in live trading either.

## What Changes

- A take-profit price at or below zero is a distinct rejection (`UnreachableTakeProfit`, a subclass
  of `InvalidRequest`); the entry is not opened (`try_open_position` and
  `try_open_projection_position` return `None`) and the loop continues with the next bar.
- Stop-loss and partial-take legs keep failing closed as before.

## Out of Scope

Any change to Strategy Engine, to stop-loss handling, to partial takes, or to the replay
scripts used for research tables (those must apply the same rule separately).

## Capabilities

### Modified Capabilities

- `research-initial-protection-v1`: Side-aware levels.
