---

# Latest update — Initial-risk / pre-runner leakage before partial TP / BE / trailing

Дата обновления: 2026-06-09  
Purpose: перед шагами partial TP / BE / lock stop / trailing зафиксировать, какая часть сделок вообще не доходит до runner, сколько из них берёт initial TP, сколько утекает в initial SL, и где именно лежит основной leakage.

---

## 23. Definitions

В этой секции используется bucket split из `trade_management_summary.by_phase_reached`.

```text
initial-risk bucket:
  сделка НЕ дошла до runner phase.
  Она закрылась обычным initial TP или initial SL.

runner bucket:
  сделка дошла до ADX/DI runner phase.
  После runner initial TP отключается.
  Дальше сделка закрывается runtime exit или emergency initial SL.
```

Важно:

```text
initial TP / initial SL здесь НЕ одно и то же, что общий TP/SL всего кандидата.
Мы смотрим именно pre-runner bucket:
  сколько сделок не стали runner,
  сколько из них взяли initial TP,
  сколько умерли в initial SL.
```

---

## 24. Initial-risk / runner bucket table

| Candidate | Total | Runner | Initial-risk | Initial TP | Initial SL | Initial PnL | Initial PF | Runner PnL | Net PnL | PF | MaxDD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `strict rsi90` | 135 | 27 (20.0%) | 108 (80.0%) | 34 (25.2% total / 31.5% bucket) | 74 (54.8% total / 68.5% bucket) | -1893 | 0.923 | +18682 | +16789 | 1.558 | -31.3% |
| `strict rsi88` | 136 | 27 (19.9%) | 109 (80.1%) | 34 (25.0% total / 31.2% bucket) | 75 (55.1% total / 68.8% bucket) | -2273 | 0.909 | +18001 | +15728 | 1.535 | -35.1% |
| `strict rsi90+ema` | 135 | 27 (20.0%) | 108 (80.0%) | 34 (25.2% total / 31.5% bucket) | 74 (54.8% total / 68.5% bucket) | -1893 | 0.923 | +15549 | +13656 | 1.511 | -30.7% |
| `strict ema` | 134 | 27 (20.1%) | 107 (79.9%) | 34 (25.4% total / 31.8% bucket) | 73 (54.5% total / 68.2% bucket) | -1432 | 0.941 | +14302 | +12870 | 1.490 | -30.2% |
| `relaxed rsi90` | 352 | 32 (9.1%) | 320 (90.9%) | 97 (27.6% total / 30.3% bucket) | 223 (63.4% total / 69.7% bucket) | -12232 | 0.839 | +33967 | +21735 | 1.268 | -55.4% |
| `relaxed rsi88` | 355 | 32 (9.0%) | 323 (91.0%) | 98 (27.6% total / 30.3% bucket) | 225 (63.4% total / 69.7% bucket) | -12121 | 0.843 | +28186 | +16065 | 1.200 | -52.6% |
| `relaxed rsi90+ema` | 352 | 32 (9.1%) | 320 (90.9%) | 97 (27.6% total / 30.3% bucket) | 223 (63.4% total / 69.7% bucket) | -12232 | 0.839 | +23182 | +10950 | 1.139 | -52.9% |
| `relaxed ema` | 347 | 31 (8.9%) | 316 (91.1%) | 95 (27.4% total / 30.1% bucket) | 221 (63.7% total / 69.9% bucket) | -14304 | 0.811 | +22596 | +8292 | 1.106 | -42.2% |
| `loose rsi90` | 498 | 47 (9.4%) | 451 (90.6%) | 126 (25.3% total / 27.9% bucket) | 325 (65.3% total / 72.1% bucket) | -37827 | 0.680 | +39640 | +1813 | 1.014 | -100.9% |
| `loose rsi88` | 502 | 47 (9.4%) | 455 (90.6%) | 127 (25.3% total / 27.9% bucket) | 328 (65.3% total / 72.1% bucket) | -38219 | 0.681 | +38087 | -133 | 0.999 | -116.0% |

---

## 25. Main readout by candidate

### Strict RSI90 — quality benchmark

```text
strict rsi90:
  total trades: 135
  runner: 27 (20.0%)
  initial-risk: 108 (80.0%)
  initial TP: 34 (25.2% of total / 31.5% of initial-risk)
  initial SL: 74 (54.8% of total / 68.5% of initial-risk)
  initial-risk PnL: -1893
  runner PnL: +18682
  net PnL: +16789
  PF: 1.558
  maxDD: -31.3%
```

Interpretation:

```text
Strict RSI90 имеет маленький initial-risk leakage:
  initial-risk PnL: -1 893

Runner bucket перекрывает его:
  runner PnL: +18 682

Проблема strict не в pre-runner leakage,
а в том, что сделок мало:
  runner only 27 trades.
```

---

### Relaxed RSI90 — volume/PnL candidate, но с большим pre-runner leakage

```text
relaxed rsi90:
  total trades: 352
  runner: 32 (9.1%)
  initial-risk: 320 (90.9%)
  initial TP: 97 (27.6% of total / 30.3% of initial-risk)
  initial SL: 223 (63.4% of total / 69.7% of initial-risk)
  initial-risk PnL: -12232
  runner PnL: +33967
  net PnL: +21735
  PF: 1.268
  maxDD: -55.4%
```

Interpretation:

```text
Relaxed RSI90 выигрывает по total PnL,
но качество ниже из-за большой утечки до runner.

Initial-risk bucket:
  320 trades
  -12 232 PnL

Runner bucket:
  32 trades
  +33 967 PnL

То есть relaxed живёт за счёт того,
что редкие runner-хвосты перекрывают большой шумовый pre-runner leakage.
```

---

### Relaxed RSI88 — меньше runner SL, но хуже tail capture

```text
relaxed rsi88:
  total trades: 355
  runner: 32 (9.0%)
  initial-risk: 323 (91.0%)
  initial TP: 98 (27.6% of total / 30.3% of initial-risk)
  initial SL: 225 (63.4% of total / 69.7% of initial-risk)
  initial-risk PnL: -12121
  runner PnL: +28186
  net PnL: +16065
  PF: 1.200
  maxDD: -52.6%
```

Interpretation:

```text
Relaxed RSI88 имеет почти тот же initial-risk leakage,
что relaxed RSI90,
но runner bucket зарабатывает меньше.

Значит в relaxed universe RSI88 хуже,
потому что не решает главную проблему initial-risk,
а хвосты режет сильнее.
```

---

### Loose RSI90 — reject as-is

```text
loose rsi90:
  total trades: 498
  runner: 47 (9.4%)
  initial-risk: 451 (90.6%)
  initial TP: 126 (25.3% of total / 27.9% of initial-risk)
  initial SL: 325 (65.3% of total / 72.1% of initial-risk)
  initial-risk PnL: -37827
  runner PnL: +39640
  net PnL: +1813
  PF: 1.014
  maxDD: -100.9%
```

Interpretation:

```text
Loose показывает важную диагностику:
  runner bucket всё ещё мощный: +39 640
  но initial-risk bucket почти полностью его съедает: -37 827

Это не рабочий setup universe.
Это negative control:
  runner edge real,
  entry universe too noisy.
```

---

## 26. What the leakage table changes in the plan

До этой таблицы можно было думать:

```text
раз runner exits работают,
значит дальше надо делать partial TP / BE / trailing.
```

После bucket split видно:

```text
partial TP / BE / trailing после runner
решают только runner bucket.

Но relaxed и loose сильно текут ДО runner.
```

Поэтому план должен разделиться:

### Track A — runner management

Актуально прежде всего для strict:

```text
strict RSI90
strict RSI88
strict RSI90+EMA
```

Проблема strict:

```text
runner есть,
edge хороший,
но нужно уменьшить runner->SL
и лучше монетизировать хвост.
```

Здесь логичны:

```text
partial TP
BE / lock stop
MFE giveback trailing
ATR trailing
```

### Track B — pre-runner leakage / setup quality

Актуально прежде всего для relaxed и loose:

```text
relaxed RSI90
relaxed RSI88
loose RSI90 as negative control
```

Проблема relaxed:

```text
много сделок,
но initial-risk bucket слишком отрицательный.
```

Здесь нужны не только exits, а:

```text
setup refinement
pre-runner filter
side-specific filters
initial SL/TP retune
possibly earlier phase / quality gate
```

---

## 27. New future research idea — RSI period sweep

Появилась новая гипотеза по RSI runtime exits.

Текущий RSI exit использует:

```text
RSI period: 14
timeframe: base 5m
long take: RSI >= 88/90
short take: RSI <= 12/10
```

Проблема наблюдения:

```text
После большого движения цена может долго и медленно подползать к EMA200.
За время такого спокойного pullback RSI сильно затухает.
Когда потом появляется ADX impulse,
RSI стартует с очень низкой базы.
Из-за этого RSI threshold может сработать слишком рано
и take оказывается маленьким относительно потенциального движения.
```

То есть проблема не только в уровне threshold 88/90, но и в `period`.

### Hypothesis

```text
RSI period 14 может быть слишком чувствительным / коротким
для runner take после спокойного EMA200 pullback.

Более длинный RSI может медленнее реагировать
и позже фиксировать exhaustion,
позволяя runner дольше развиться.
```

### First RSI period sweep

Тестировать только после bucket/year analysis, не смешивать с partial TP v1.

Candidate matrix:

```text
RSI period:
  14  baseline
  21
  28
  34

Thresholds:
  88/12
  90/10

Setup branches:
  strict RSI90/88
  relaxed RSI90/88
```

Минимальный первый sweep:

```text
strict_adx40_runner_rsi90_period14
strict_adx40_runner_rsi90_period21
strict_adx40_runner_rsi90_period28
strict_adx40_runner_rsi90_period34

strict_adx40_runner_rsi88_period14
strict_adx40_runner_rsi88_period21
strict_adx40_runner_rsi88_period28
strict_adx40_runner_rsi88_period34

relaxed_adx40_runner_rsi90_period14
relaxed_adx40_runner_rsi90_period21
relaxed_adx40_runner_rsi90_period28
relaxed_adx40_runner_rsi90_period34
```

What to inspect:

```text
runner PnL
runner SL count
avg runner win
avg runner hold
capture ratio
giveback
bars_to_mfe
side-by-side short robustness
year-by-year stability
```

Expected possible outcomes:

```text
longer RSI period:
  fewer premature takes
  larger avg win
  longer hold
  maybe more runner SL

shorter/current RSI period:
  safer / earlier take
  better capture
  less tail
```

This is a separate research branch:

```text
RSI exit semantics tuning
```

It should not be mixed with partial TP / BE / trailing in the same sweep.

---

## 28. Updated next research order

Новый порядок после leakage analysis:

```text
0. Step 0 setup universe — done
1. Initial-risk / runner bucket decomposition — current update
2. Year-by-year + side-by-year for strict vs relaxed
3. Trade-id comparison for runner SL and big winners
4. RSI period sweep as separate exit-semantics branch
5. Partial TP design / OpenSpec
6. BE / lock stop after partial or MFE threshold
7. MFE/giveback trailing
8. Refined setup universe between strict and relaxed
```

Reasoning:

```text
Сначала понять устойчивость strict/relaxed по годам и сторонам.
Потом отдельно проверить RSI period,
потому что это может изменить саму природу runtime take.
Только затем проектировать более сложные execution mechanics.
```

---

## 29. Current interpretation after leakage analysis

```text
strict RSI90:
  best quality benchmark.
  low pre-runner leakage.
  main issue: few trades + runner management.

relaxed RSI90:
  best absolute PnL / volume candidate.
  main issue: large pre-runner leakage and side concentration.
  partial TP alone will not solve it.

loose:
  confirms runner edge survives even in noisy universe.
  rejected as-is because pre-runner leakage kills the system.

RSI period:
  new promising branch.
  Current RSI14 may be too fast after slow EMA200 pullback.
  Need test RSI21/28/34 before overengineering partial/BE/trailing.
```
