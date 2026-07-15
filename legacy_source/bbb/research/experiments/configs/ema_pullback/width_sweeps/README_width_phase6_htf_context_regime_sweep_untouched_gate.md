# Phase 6 — HTF context regime sweep for EMA 200 candidates, fixed version

This package replaces the previous Phase 6 package.

## What was fixed

The first package attached `context_consumption` to:

```text
anchor_stack_width_setup
```

That is rejected by the current backend:

```text
ValueError:
setups['setup_width'].context_consumption is not supported
for component_id 'anchor_stack_width_setup';
supported setups: ['ema_bounce_counter_setup', 'untouched_anchor_setup']
```

This fixed package attaches the same HTF gate to:

```text
untouched_anchor_setup.context_consumption
```

The width setup remains unchanged and still provides the discovered EMA-stack width edge.

## Why this is acceptable

The setup composition is AND:

```text
untouched_anchor_setup
AND
anchor_stack_width_setup
```

So gating `untouched_anchor_setup` by HTF regime still gates the whole entry setup. It is not as semantically clean as gating width directly, but it is equivalent for entry permission in the current AND-composed setup.

Do not interpret this as “HTF belongs to untouched forever”. This is a current-backend-compatible experiment. Later we should either:

```text
1. add context_consumption support to anchor_stack_width_setup
or
2. add a dedicated htf_regime_setup / context_gate_setup
```

## HTF contexts

### h1_20_50_100

```text
timeframe: 1h
fast/anchor/slow: 20 / 50 / 100
```

Fast hourly context.

### h1_50_100_200

```text
timeframe: 1h
fast/anchor/slow: 50 / 100 / 200
```

Slower classic hourly trend context.

## Regime policies

```text
aligned
countertrend
aligned_neutral
```

Where:

```text
aligned:
  allowed_regimes = ["aligned"]

countertrend:
  allowed_regimes = ["countertrend"]

aligned_neutral:
  allowed_regimes = ["aligned", "neutral"]
```

## Base candidates

```text
strict_continuation:
  w12/r14/wlb20/SL6/TP14

relaxed_medium:
  w9/r10/wlb20/SL4/TP10

relaxed_cleaner_recent:
  w9/r12/wlb20/SL4/TP10
```

## Full run

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/width_sweeps/width_phase6_htf_context_regime_sweep_untouched_gate.json
```

## Subset runs

Strict continuation only:

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/width_sweeps/width_phase6_htf_context_strict_continuation_untouched_gate.json
```

Relaxed medium only:

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/width_sweeps/width_phase6_htf_context_relaxed_medium_untouched_gate.json
```

Cleaner relaxed recent-width check:

```powershell
python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/width_sweeps/width_phase6_htf_context_relaxed_cleaner_recent_untouched_gate.json
```

## What to compare

Compare against naked baselines:

```text
strict naked:
  w12/r14/wlb20/SL6/TP14
  trades ~138
  PF ~1.410
  DD ~-0.110
  long PF ~1.270
  short PF ~1.647
  bad_context ~82

relaxed naked:
  w9/r10/wlb20/SL4/TP10
  trades ~357
  PF ~1.168
  DD ~-0.182
  long PF ~1.300
  short PF ~1.024
  bad_context ~233
```

Good HTF filter:

```text
PF improves or stays close
drawdown improves
short PF improves materially
bad_context stops decrease
trade count does not collapse too hard
high_mfe_low_capture does not explode
```

Interpretation:

```text
aligned better than countertrend:
  HTF trend is useful as entry filter.

aligned_neutral better than aligned:
  pure aligned is too strict, neutral still has valid EMA200 pullbacks.

countertrend strong:
  HTF definition may be wrong or EMA200 setup behaves as mean-reversion in that regime.

strict improves but relaxed does not:
  HTF context is mainly for continuation branch.

relaxed short PF improves:
  HTF context may be missing piece for relaxed both-side trading.
```
