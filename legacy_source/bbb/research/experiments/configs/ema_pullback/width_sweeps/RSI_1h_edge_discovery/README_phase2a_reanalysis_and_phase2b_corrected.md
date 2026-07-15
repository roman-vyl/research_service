# RSI 1h Edge Discovery - Phase 2A Reanalysis and Corrected Phase 2B

## Status

Phase 2A completed successfully.

```text
experiment_id: ema200_rsi_1h_edge_phase2a_width_params_tuning_fee04
candidates: 72
ok: 72
failed: 0
duration_sec: 2181.5
```

## What changed after reanalysis

Initial reading overemphasized the best point:

```text
w11 / r12 / lb10
```

That point remains important, but Phase 2A heatmap and aggregated statistics show that:

```text
lb20 is the better stability center.
```

Correct interpretation:

```text
lb10:
  sharp peak / fast freshness comparator

lb20:
  best stability center

lb35:
  slow/stale comparator, still viable but slightly more delayed
```

## Lookback summary

`width_lookback_bars` is measured in base 5m candles.

```text
lb10 = 50 minutes
lb20 = 100 minutes
lb35 = 175 minutes
```

| lb | mean PF | median PF | mean WR | median WR | mean PnL | PF >= 1.10 | PF >= 1.15 | both sides PF > 1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lb10 | 1.116 | 1.108 | 55.9% | 56.3% | 2 883 | 13 | 9 | 20 |
| lb20 | 1.132 | 1.156 | 56.1% | 56.5% | 3 318 | 19 | 13 | 21 |
| lb35 | 1.128 | 1.148 | 56.1% | 56.5% | 3 213 | 18 | 12 | 21 |

## Why lb20 is preferred as stability center

Compared with lb10, lb20 has:

```text
higher mean PF
higher median PF
higher mean PnL
more candidates with PF >= 1.10
more candidates with PF >= 1.15
slightly better mean/median win rate
slightly softer average drawdown
```

So Phase 2A should no longer be summarized as "w11/r12/lb10 is the center".

Better summary:

```text
w11/r12/lb10 is the best sharp point.
lb20 is the more stable lookback area.
The next test must compare lb10/lb20/lb35, not lb5/lb10/lb15.
```

## Strong balanced candidates from Phase 2A

| rail | w/r/lb | trades | PnL | PF | WR | DD | long PF | short PF |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2.15 | w11/r12/lb10 | 197 | 4 088 | 1.218 | 57.9% | -20.3% | 1.214 | 1.222 |
| 2.35 | w11/r12/lb10 | 196 | 4 312 | 1.205 | 57.1% | -23.6% | 1.222 | 1.187 |
| 2.15 | w11/r12/lb20 | 200 | 3 812 | 1.202 | 57.5% | -20.3% | 1.184 | 1.224 |
| 2.45 | w11/r12/lb10 | 196 | 4 174 | 1.192 | 57.1% | -24.4% | 1.238 | 1.145 |
| 2.35 | w11/r12/lb20 | 199 | 4 009 | 1.190 | 56.8% | -25.0% | 1.191 | 1.189 |
| 2.15 | w11/r8/lb10 | 204 | 3 568 | 1.190 | 56.9% | -20.9% | 1.151 | 1.234 |
| 2.15 | w11/r8/lb20 | 204 | 3 568 | 1.190 | 56.9% | -20.9% | 1.151 | 1.234 |
| 2.15 | w11/r8/lb35 | 204 | 3 568 | 1.190 | 56.9% | -20.9% | 1.151 | 1.234 |
| 2.15 | w11/r10/lb10 | 204 | 3 568 | 1.190 | 56.9% | -20.9% | 1.151 | 1.234 |
| 2.15 | w11/r10/lb20 | 204 | 3 568 | 1.190 | 56.9% | -20.9% | 1.151 | 1.234 |

## Corrected next step: Phase 2B

Previous Phase 2B plan used:

```text
lb5 / lb10 / lb15
```

That was wrong after reanalysis because it centered the search too tightly around lb10.

Corrected Phase 2B uses:

```text
lb10 / lb20 / lb35
```

## Corrected Phase 2B matrix

```text
current_width:
  w10
  w11
  w12

recent_width:
  r11
  r12
  r13

width_lookback:
  lb10
  lb20
  lb35

rails:
  2.15 / 2.15
  2.35 / 2.35
  2.45 / 2.45
```

Total:

```text
3 current widths x 3 recent widths x 3 lookbacks x 3 rails = 81 candidates
```

## Corrected Phase 2B batch

```text
batches/ema200_rsi_1h_edge_phase2b_corrected_width_stability_fee04.json
```

## Corrected Phase 2B candidate folder

```text
candidates/phase2b_ridge_robustness_corrected_lb10_lb20_lb35/
```

## Commands

Validate:

```powershell
python -m research.experiments.cli validate --spec research/experiments/configs/ema_pullback/width_sweeps/RSI_1h_edge_discovery/batches/ema200_rsi_1h_edge_phase2b_corrected_width_stability_fee04.json
```

Run:

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/width_sweeps/RSI_1h_edge_discovery/batches/ema200_rsi_1h_edge_phase2b_corrected_width_stability_fee04.json
```

## Decision rules for corrected Phase 2B

### Good result

```text
lb20 remains strong across neighboring w/r values;
lb10 remains useful but not uniquely necessary;
lb35 does not dominate by stale over-permission;
long and short PF stay alive;
PF improves without maxDD expansion;
result survives at least two rails.
```

### Bad result

```text
only one exact point survives;
lb20 collapses after moving w/r neighbors;
best results become short-only;
PF improves only with much larger drawdown;
trade count collapses too much.
```

## Still excluded

```text
RSI blocker
RSI gate
ADX runner
runtime exits
BE / lock
partial TP
trailing
HTF context
asymmetric rails
wide continuation rails
high-selectivity w16 branch
```

Reason:

```text
This phase still isolates the entry edge. RSI comes only after width stability is confirmed.
```
