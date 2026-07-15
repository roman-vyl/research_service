# Phase-gated runner exit v1 — continuation package

Why this exists:

The original batch had 15 candidates, but the uploaded reports show only 6 finished:

```text
strict_initial_control_fee04
strict_adx40_runner_no_signal_fee04
strict_adx45_runner_no_signal_fee04
strict_adx40_runner_only_rsi90_fee04
strict_adx40_runner_only_rsi85_fee04
strict_adx40_runner_only_ema100_200_fee04
```

The next candidate in the original order was likely `strict_adx40_runner_only_ema50_200_fee04`.

That candidate uses EMA50, which is not part of the anchor stack 100/200/496. EMA100/200 works because both EMAs are already available from anchor stack features, so the successful smoke did not fully prove arbitrary runtime EMA feature planning.

## Safe continuation

This continuation excludes EMA50/200 and continues with only EMA100/200 + RSI candidates.

Run:

```powershell
python -m research.experiments.cli validate --spec research/experiments/configs/ema_pullback/runner_exit_sweeps/batches/ema200_phase_gated_runner_exit_v1_fee04_continuation_safe.json

python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/runner_exit_sweeps/batches/ema200_phase_gated_runner_exit_v1_fee04_continuation_safe.json
```

## Diagnostic probe

Run this separately only to confirm whether EMA50 runtime feature planning works:

```powershell
python -m research.experiments.cli validate --spec research/experiments/configs/ema_pullback/runner_exit_sweeps/batches/ema200_phase_gated_runner_exit_v1_fee04_ema50_feature_probe.json

python -m research.experiments.cli run-batch --spec research/experiments/configs/ema_pullback/runner_exit_sweeps/batches/ema200_phase_gated_runner_exit_v1_fee04_ema50_feature_probe.json
```

If probe fails, fix feature planning for runtime-only EMA periods outside anchor stack before doing broader EMA-cross sweeps.
