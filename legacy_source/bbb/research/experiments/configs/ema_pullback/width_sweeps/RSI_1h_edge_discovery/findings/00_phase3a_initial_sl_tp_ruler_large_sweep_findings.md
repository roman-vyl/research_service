# Phase 3A Findings — Initial SL/TP Ruler Large Sweep

Status: not filled yet.

## Batch

```text
ema200_rsi_1h_edge_phase3a_initial_sl_tp_ruler_large_sweep_fee04
```

## Main question

Can 1h ATR TP with proper old-style RR ratios beat or match old base ATR initial candidates?

```text
YES / NO / ONLY SHORT-HEAVY / ONLY TREND-CAPTURE
```

## Locked old litmus candidates

| Candidate | Width TF | Width | SL TF | SL | TP TF | TP | RR | Trades | PnL | PF | WR | DD | Long PF | Short PF | Gap |
|---|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|

## Best base ATR initial candidates

| Candidate | Width core | SL | TP | RR | Trades | PnL | PF | WR | DD | Long PF | Short PF | Gap |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|

## Best 1h ATR initial candidates

| Candidate | Width core | SL | TP | RR | Trades | PnL | PF | WR | DD | Long PF | Short PF | Gap |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|

## Best cross-ruler candidates

| Candidate | Width core | SL TF | SL | TP TF | TP | RR | Trades | PnL | PF | WR | Long PF | Short PF | Gap |
|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|

## Decision

Choose one:

```text
A. Old base initial litmus remains best.
B. 1h ATR initial TP beats old litmus cleanly and symmetrically.
C. 1h ATR initial TP only wins as short-heavy / trend-capture branch.
D. Need exit management; fixed initial TP cannot solve capture.
```

## Candidates to carry forward

```text

```
