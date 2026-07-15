# EMA200 ADX protected phase sweep configs

Generated configs for testing the hypothesis:

- 5m/base ADX + DI aligned impulse promotes an open EMA200 pullback trade to `protected`.
- `break_even_stop` activates from `protected` and can be compared against initial-only SL/TP behavior.

Profiles:

- `relaxed`: width current/recent 9/10 ATR, width lookback 20, untouched lookback 75, active bars 8, SL 4 ATR, safety TP 40 ATR.
- `strict`: width current/recent 12/14 ATR, width lookback 20, untouched lookback 75, active bars 8, SL 6 ATR, safety TP 40 ATR.

ADX thresholds: 20, 25, 30, 35, 40, 45.

## Batch specs

Diagnostic frequency only:

```powershell
python -m research.experiments.cli validate --spec research/experiments/specs/batches/ema200_adx_protected_frequency_diagnostic.json
python -m research.experiments.cli run-batch --spec research/experiments/specs/batches/ema200_adx_protected_frequency_diagnostic.json
```

Managed BE effect vs initial-only baseline:

```powershell
python -m research.experiments.cli validate --spec research/experiments/specs/batches/ema200_adx_protected_be_effect.json
python -m research.experiments.cli run-batch --spec research/experiments/specs/batches/ema200_adx_protected_be_effect.json
```

Combined batch:

```powershell
python -m research.experiments.cli validate --spec research/experiments/specs/batches/ema200_adx_protected_combined.json
python -m research.experiments.cli run-batch --spec research/experiments/specs/batches/ema200_adx_protected_combined.json
```

## How to inspect frequency

Batch summary gives PnL/trade metrics. To inspect how often the ADX threshold fired, open each candidate report under `research/results/runs/` and count `phase_changed` events with:

```text
metadata.condition_component_id == "adx_di_threshold"
to_phase == "protected"
```

Diagnostic batch is best for pure frequency because exits do not change. Managed BE batch is best for effect vs initial-only behavior.
