# Width Phase 2 — SL/TP sweep

Drop this folder into repo root so files end up at:

```text
research/experiments/configs/ema_pullback/width_sweeps/
```

## Why

Phase 1 showed `min_current_width_atr=12`, `min_recent_width_atr=1`, `width_lookback_bars=35`
as the best current-width point from the first sweep:

- 144 trades
- PF ~1.262
- win rate ~35.4%
- long PF ~1.348
- short PF ~1.147

Now we search ATR SL / ATR TP before spending time on recent-width and lookback.

## Files

### Main run

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/width_sweeps/width_phase2a_sl_tp_sweep_w12_r1_lb35.json
```

Grid:

```text
width = 12
recent = 1
lookback = 35
SL = 4, 5, 6, 7, 8
TP = 10, 12, 14, 16, 18, 20
candidates = 30
```

### Cross-check run

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/width_sweeps/width_phase2b_sl_tp_crosscheck_w10_w12.json
```

Grid:

```text
width = 10, 12
recent = 1
lookback = 35
SL = 4, 5, 6, 7
TP = 10, 12, 14, 16, 18
candidates = 40
```

Use this if Phase 2A looks overfiltered or if w10 with a better exit policy may beat w12.

### Optional runner probe

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/width_sweeps/width_phase2c_high_tp_runner_probe_w12.json
```

Grid:

```text
width = 12
recent = 1
lookback = 35
SL = 5, 6, 7, 8
TP = 22, 24, 28, 32
candidates = 16
```

Run only after Phase 2A if high TP still looks viable.

## What to compare

Do not select only by max PF. Compare:

```text
trades
PF
win_rate
pnl
max_drawdown
long_profit_factor
short_profit_factor
high_mfe_high_capture_count
high_mfe_low_capture_count
stop_loss_after_low_mfe
stop_loss_after_bad_context
fees_paid
```

Good candidate:

```text
PF > 1
both long and short not broken
enough trades, not just 20-30 lucky trades
stop_loss_after_low_mfe decreases
high_mfe_low_capture does not explode
max_drawdown improves or stays acceptable
```

No break-even in this phase.
