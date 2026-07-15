# Methodology — RSI 1h Edge Discovery

## Reset

Earlier base-ATR Phase 0 is not the intended start for this research branch.

The correct Phase 0 calibrates symmetric 1h ATR rails.

## Correct order

```text
Phase 0: 1h ATR symmetric ruler calibration
Phase 1: current width sweep on selected 1h ATR ruler(s)
Phase 2: recent/lookback sweep
Phase 3: asymmetric 1h/base ATR comparison if needed
Phase 4: RSI 1h bucket diagnostics
Phase 5: active RSI 1h gate/filter only if diagnostics justify it
```

## Isolation rule

Phase 0 changes only the exit-distance timeframe:

```text
distance.timeframe = 1h
```

It does not change:

```text
width ATR normalization
entry setup semantics
RSI filters
runner management
```
