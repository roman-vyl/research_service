# EMA200 Pullback Research — Phase-gated Runner Exits v1

Дата: 2026-06-09  
Инструмент: BTCUSDT  
Базовый таймфрейм: 5m  
Объём данных: 646 029 свечей  
Fee model: `fees = 0.0004`, `slippage = 0.0001`  
Research branch: EMA200 pullback / width + untouched setup / ADX→runner / runtime exits

---

## 1. Что именно исследовали

Цель этой фазы — проверить новую архитектуру `exit_management.runtime_exit` на реальных research-прогонах, а не на smoke.

До этого RSI/EMA exits были always-on signal exits внутри `exit_policy`. Это загрязняло вывод: RSI/EMA могли закрывать сделку до того, как сделка реально дошла до runner-фазы.

После архитектурной правки старые primitives стали переиспользоваться в новой роли:

```text
rsi_signal_exit       -> exit_management.runtime_exit
ema_cross_loss_exit   -> exit_management.runtime_exit
```

То есть компоненты не дублировались. Не создавались новые `runner_rsi_exit`, `phase_gated_ema_cross_exit` и прочие копии.  
Изменился только consumer role: теперь тот же компонент может быть использован как runtime exit, активируемый только после достижения нужной фазы.

---

## 2. Базовая стратегия

Все прогоны этой серии держат одинаковый entry/setup контур.

```text
symbol: BTCUSDT
timeframe: 5m
sides: long + short

anchor stack:
  fast:   EMA100 close
  anchor: EMA200 close
  slow:   EMA496 close

setups:
  anchor_stack_width_setup:
    min_current_width_atr: 12
    min_recent_width_atr: 14
    width_lookback_bars: 20
    atr_period: 14
    atr_timeframe: base

  untouched_anchor_setup:
    lookback: 75
    active_bars: 8

trigger:
  touch_anchor

blockers:
  no_blockers

risk:
  no_risk_filter

initial exits:
  SL: 6 ATR
  TP: 14 ATR
```

Runner phase:

```text
phase rule:
  adx_di_threshold
  timeframe: base
  period: 14
  threshold: 40 or 45
  require_di_alignment: true

on runner:
  take_profile_switch disables initial TP
```

В текущей v1-модели initial SL остаётся аварийным fallback даже после runner.

---

## 3. Архитектурная проверка перед research

Market smoke подтвердил, что runtime exits реально phase-gated:

```text
runtime exits before runner = 0
exit_layer_breakdown contains exit_management.runtime_exit
runtime_exit_breakdown contains rsi_signal_exit / ema_cross_loss_exit
```

Контрольный smoke:

```text
strict_adx40_runner_runtime_rsi90_ema100_200_smoke
135 trades
PnL +13 656
PF 1.51
27 runner trades
24 runtime exits
3 runner trades closed by emergency SL
```

Это подтвердило, что новая runtime-архитектура работает на полном market range.

---

## 4. Control baseline

### 4.1 Initial control

```text
strict_initial_control_fee04

trades: 138
PnL: +2 639
PF: 1.357
Sharpe: 0.532
Max DD: -11.2%
long PF: 1.223
short PF: 1.585

exit mix:
  TP: 56
  SL: 82
```

Вывод: базовая стратегия уже положительная, но прибыль слабая. Основной потенциал находится не в обычном SL/TP, а в правильной обработке runner-сделок.

---

### 4.2 No-signal runner controls

ADX40 no-signal:

```text
strict_adx40_runner_no_signal_fee04

closed trades: 11
PnL: -639
PF: 0.204
open trades: 1
```

ADX45 no-signal:

```text
strict_adx45_runner_no_signal_fee04

closed trades: 63
PnL: -4 611
PF: 0.681
open trades: 1
```

Вывод: отключать initial TP после runner без replacement exits нельзя.  
Runner-фаза обязана иметь runtime exits: RSI, EMA, market close, trailing/lock и т.д.

---

## 5. ADX40 vs ADX45

ADX40 оказался лучше как trigger runner-фазы.

Лучший ADX40 вариант:

```text
strict_adx40_runner_only_rsi90_fee04

trades: 135
PnL: +16 789
PF: 1.558
Sharpe: 1.509
Max DD: -31.3%
long PF: 1.318
short PF: 1.936
```

Лучший ADX45 вариант:

```text
strict_adx45_runner_only_rsi90_fee04

trades: 138
PnL: +14 965
PF: 1.508
Sharpe: 1.482
Max DD: -33.7%
long PF: 1.298
short PF: 1.833
```

ADX45 чище/строже, но в этой серии он не улучшает итог. Он даёт меньше runner-возможностей и ниже total PnL.

Рабочий вывод:

```text
ADX40 > ADX45 for runner activation
```

ADX45 можно оставить как robustness comparison, но не как основной путь.

---

## 6. RSI-only runner exits

RSI-only — главный money-mode.

Таблица по RSI-only:

| Candidate | Trades | Total PnL | PF | Sharpe | Max DD | Long PF | Short PF | Runner PnL | Runner mix | Median capture | Median giveback |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| `rsi90_10` | 135 | **+16 789** | **1.558** | 1.509 | -31.3% | 1.318 | **1.936** | **+18 682** | 15 RSI / 12 SL | 0.374 | 1.82% |
| `rsi88_12` | 136 | +15 728 | 1.535 | **1.681** | -35.1% | **1.637** | 1.388 | +18 001 | 17 RSI / 10 SL | 0.738 | 1.25% |
| `rsi86_14` | 137 | +14 858 | 1.499 | 1.585 | -38.4% | 1.572 | 1.391 | +17 685 | 18 RSI / 9 SL | **0.888** | **0.52%** |
| `rsi87_13` | 137 | +14 750 | 1.495 | 1.582 | -38.4% | 1.568 | 1.388 | +17 576 | 18 RSI / 9 SL | 0.833 | 0.52% |
| `rsi85_15` | 138 | +13 544 | 1.455 | 1.460 | -38.5% | 1.550 | 1.315 | +16 411 | 19 RSI / 8 SL | 0.720 | 0.58% |
| `rsi89_11` | 136 | +11 643 | 1.382 | 1.273 | -35.5% | 1.368 | 1.404 | +13 916 | 15 RSI / 12 SL | 0.374 | 1.65% |

### 6.1 Главный вывод по RSI-only

RSI90/10 остаётся лучшим по максимальной прибыли.

```text
RSI90/10:
  max total PnL
  max total PF
  strongest short side
  highest runner PnL
```

Но RSI90/10 допускает 12 runner→SL сделок. Это цена ожидания экстремального RSI.

RSI88/12 — лучший balanced candidate:

```text
RSI88/12:
  PnL only ~1.06k below RSI90
  PF close to RSI90
  Sharpe higher than RSI90
  runner SL reduced from 12 to 10
  median capture much better
  median giveback lower
```

RSI86/14 и RSI87/13 ещё сильнее улучшают capture/giveback и снижают runner SL до 9, но начинают резать хвосты. Они становятся более defensive, но хуже по прибыли.

RSI89/11 провалился. Он не дал логичной середины между 88 и 90: runner mix остался как у RSI90, но PnL резко ниже.

---

## 7. EMA-only runner exits

EMA100/200 protective exit работает как защитный выход, а не как максимизатор прибыли.

Основной EMA-only кандидат:

```text
strict_adx40_runner_only_ema100_200_fee04

trades: 134
PnL: +12 870
PF: 1.490
Sharpe: 1.584
Max DD: -30.2%
long PF: 1.333
short PF: 1.754

runner:
  24 EMA exits
  3 SL
  runner PnL: +14 302
```

EMA100/200 почти убирает runner→SL:

```text
RSI90-only:
  12 runner SL

EMA100/200-only:
  3 runner SL
```

Но за эту защиту стратегия платит хвостами: EMA закрывает сделки раньше, чем они успевают дойти до экстремального RSI.

EMA50/200 feature probe тоже прошёл успешно:

```text
strict_adx40_runner_only_ema50_200_fee04_FEATURE_PROBE

trades: 135
PnL: +11 057
PF: 1.408
Sharpe: 1.374
Max DD: -40.9%
long PF: 1.399
short PF: 1.422
```

Это важно технически: runtime-only EMA periods outside anchor stack работают. Feature planning для EMA50 не сломан.

Но EMA50/200 как кандидат слабее EMA100/200.

---

## 8. RSI + EMA100/200 combo

Комбинация RSI + EMA100/200 подтвердила защитную гипотезу, но не стала лучшей по total PnL.

Таблица combo:

| Candidate | Trades | Total PnL | PF | Sharpe | Max DD | Long PF | Short PF | Runner PnL | Runner mix |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `rsi90 + ema100/200` | 135 | **+13 656** | **1.511** | 1.578 | -30.7% | 1.208 | **2.038** | **+15 549** | 7 RSI / 17 EMA / 3 SL |
| `rsi88 + ema100/200` | 136 | +12 565 | 1.467 | **1.576** | -34.5% | **1.354** | 1.654 | +14 838 | 11 RSI / 13 EMA / 3 SL |
| `rsi87 + ema100/200` | 137 | +12 134 | 1.442 | 1.509 | -37.7% | 1.317 | 1.654 | +14 961 | 13 RSI / 11 EMA / 3 SL |
| `rsi86 + ema100/200` | 137 | +11 805 | 1.430 | 1.471 | -37.6% | 1.296 | 1.658 | +14 631 | 13 RSI / 11 EMA / 3 SL |
| `rsi89 + ema100/200` | 136 | +11 369 | 1.419 | 1.432 | -34.8% | 1.266 | 1.676 | +13 642 | 10 RSI / 14 EMA / 3 SL |
| `rsi85 + ema100/200` | 138 | +10 760 | 1.391 | 1.359 | -38.3% | 1.280 | 1.582 | +13 626 | 15 RSI / 9 EMA / 3 SL |

### 8.1 Почему combo не стал лучшим

RSI и EMA не складываются как два независимых источника прибыли. Они конкурируют за одни и те же runner-сделки.

RSI90-only:

```text
runner:
  15 RSI exits
  12 SL
  runner PnL: +18 682
```

EMA100/200-only:

```text
runner:
  24 EMA exits
  3 SL
  runner PnL: +14 302
```

RSI90+EMA100/200:

```text
runner:
  7 RSI exits
  17 EMA exits
  3 SL
  runner PnL: +15 549
```

Combo действительно спасает от SL:

```text
runner SL:
  RSI90-only: 12
  RSI90+EMA: 3
```

Но одновременно EMA забирает часть сделок до того, как они дошли бы до RSI90:

```text
RSI exits:
  RSI90-only: 15
  RSI90+EMA: 7
```

Итого EMA снижает хвостовой риск, но режет часть жирных хвостов. Поэтому combo полезен как defensive mode, но не как money-max mode.

---

## 9. Интерпретация поведения RSI и EMA

### RSI как сниматель сильного движения

RSI-exit работает как late take-profit / exhaustion exit.

Он ждёт экстремального импульса:

```text
long:  RSI >= 85/86/87/88/89/90
short: RSI <= 15/14/13/12/11/10
```

Сильная сторона RSI:

```text
позволяет хвосту развиться
собирает большие движения
даёт максимальный PnL
```

Слабая сторона RSI:

```text
если движение не дошло до экстремума, сделка может вернуться в аварийный SL
```

### EMA-cross как protective loss-of-momentum exit

EMA100/200 cross работает как защитный выход при потере momentum.

Сильная сторона EMA:

```text
резко уменьшает runner→SL
лучше защищает открытый runner
стабилизирует хвостовой риск
```

Слабая сторона EMA:

```text
часто выходит слишком рано
срезает сделки, которые позже могли дойти до RSI90
уменьшает total PnL
```

### Почему вместе хуже, чем кажется

Многие трендовые движения идут не идеально прямо:

```text
импульс → откат / потеря momentum → продолжение → экстремальный RSI
```

EMA может закрыть сделку на промежуточной потере momentum, а RSI90 сработал бы позже и дал больше денег.

Поэтому combo:

```text
лучше защищает
но хуже максимизирует прибыль
```

---

## 10. Текущие финальные кандидаты

### Primary money candidate

```text
strict_adx40_runner_only_rsi90_fee04
```

Почему:

```text
max total PnL
max PF
strongest short side
best runner PnL
```

Минусы:

```text
12 runner→SL
median capture only 0.374
giveback higher than RSI86/87/88
```

---

### Balanced candidate

```text
strict_adx40_runner_only_rsi88_12_fee04
```

Почему:

```text
PnL close to RSI90
PF close to RSI90
highest Sharpe in RSI-only midpoint sweep
runner SL lower than RSI90
much better capture/giveback
```

Минусы:

```text
~1.06k less PnL than RSI90
short side weaker than RSI90
```

---

### Defensive / quality candidate

```text
strict_adx40_runner_only_rsi86_14_fee04
```

Почему:

```text
runner SL only 9
median capture ~0.888
median giveback ~0.52%
still strong total PnL
```

Минусы:

```text
cuts tails earlier
lower total PnL than RSI88/90
```

---

### Protective baseline

```text
strict_adx40_runner_only_ema100_200_fee04
```

Почему:

```text
24 EMA exits
only 3 runner SL
validates EMA as protective exit
```

Минусы:

```text
lower PnL than RSI-only variants
not a money-max candidate
```

---

### Defensive combo

```text
strict_adx40_runner_rsi90_plus_ema100_200_fee04
```

Почему:

```text
runner SL only 3
PF 1.511
short PF 2.038
good risk-reduction behavior
```

Минусы:

```text
lower PnL than RSI90-only and RSI88-only
EMA steals too many future RSI exits
```

---

## 11. Что НЕ стоит делать дальше

Не стоит дальше просто расширять RSI-сетку вслепую.

Уже видно:

```text
85 слишком рано
86/87 защитные
88 лучший баланс
90 максимум денег
89 странный провал
```

Также не стоит сейчас считать EMA100/200 обязательным улучшением. Она полезна, но как защитный режим, а не как основной money-mode.

---

## 12. Следующий research шаг

Следующий шаг должен быть не новый огромный sweep, а проверка устойчивости кандидатов.

Сравнить по годам и по trade-id:

```text
strict_adx40_runner_only_rsi90_fee04
strict_adx40_runner_only_rsi88_12_fee04
strict_adx40_runner_only_rsi86_14_fee04
strict_adx40_runner_rsi90_plus_ema100_200_fee04
strict_adx40_runner_only_ema100_200_fee04
```

### 12.1 Year-by-year

Нужно проверить:

```text
PnL by year
PF by year
trades by year
long/short by year
runner trades by year
runner PnL by year
drawdown by year
```

Ключевой вопрос:

```text
RSI90 выигрывает за счёт пары редких хвостов
или стабильно лучше по большинству лет?
```

Если RSI90 выигрывает только 1–2 жирными годами, а RSI88 стабильнее — RSI88 может быть лучше как production candidate.

Если RSI90 выигрывает большинство лет — RSI90 остаётся главным.

### 12.2 Runner→SL trade-id comparison

Нужно взять runner-сделки, которые у RSI90-only закрылись в SL:

```text
12 runner→SL trades
```

И посмотреть, что с ними делает:

```text
RSI88-only
EMA100/200-only
RSI90+EMA100/200
```

Вопросы:

```text
сколько SL RSI90 превращаются в прибыль на RSI88?
сколько SL RSI90 закрываются EMA protective?
сколько больших RSI90 winners режутся EMA?
какая чистая цена защиты?
```

### 12.3 Side stability

Особенно важно по short side:

```text
RSI90 short PF: very strong
RSI88 short PF: weaker
combo short PF: strong, but total lower
```

Нужно понять, какой компонент реально держит short edge.

---

## 13. Текущее рабочее решение

На текущий момент:

```text
Main candidate:
  ADX40 + RSI90-only

Balanced candidate:
  ADX40 + RSI88-only

Defensive candidate:
  ADX40 + RSI86-only

Protective research baseline:
  ADX40 + EMA100/200-only

Defensive combo:
  ADX40 + RSI90 + EMA100/200
```

Итоговая формулировка:

```text
Runner edge подтверждён.
ADX40 лучше ADX45.
RSI90 даёт максимум денег.
RSI88 даёт лучший баланс прибыли и качества выхода.
EMA100/200 — хороший protective exit, но не основной profit-max exit.
Combo RSI+EMA снижает runner→SL, но режет слишком много хвостовой прибыли.
```

---

# Trade outcome diagnostics — EMA200 phase-gated runner exits

Метрики посчитаны по closed `trade_records` из full report JSON.

Определения:

- `Win rate` — доля сделок с `pnl > 0`.

- `Avg win` — средняя net-отдача прибыльной сделки: `pnl / (entry_price * size)`.

- `Avg loss` — средняя net-отдача убыточной сделки: `pnl / (entry_price * size)`.

- `Avg trade` — средняя net-отдача по всем закрытым сделкам.

- `Avg/Median hold` — удержание в часах по `hold_minutes`.


### Key candidates

| Candidate | Trades | Win rate | Avg win | Avg loss | Avg trade | Avg hold | Median hold | PnL | PF | Runner mix |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `strict_initial_control` | 138 | 40.6% | 1.66% | -0.83% | 0.180% | 9.9h | 4.8h | 2639 | 1.357 |  |
| `only_rsi90` | 135 | 36.3% | 2.22% | -0.84% | 0.274% | 13.6h | 4.8h | 16789 | 1.558 | 15 RSI / 0 EMA / 12 SL |
| `only_rsi88_12` | 136 | 37.5% | 1.95% | -0.84% | 0.209% | 12.0h | 4.9h | 15728 | 1.535 | 17 RSI / 0 EMA / 10 SL |
| `only_rsi86_14` | 137 | 38.0% | 1.80% | -0.84% | 0.163% | 9.9h | 4.8h | 14858 | 1.499 | 18 RSI / 0 EMA / 9 SL |
| `only_ema100_200` | 134 | 41.0% | 1.80% | -0.78% | 0.279% | 11.7h | 4.8h | 12870 | 1.490 | 0 RSI / 24 EMA / 3 SL |
| `rsi90_plus_ema100_200` | 135 | 40.7% | 1.75% | -0.79% | 0.242% | 10.3h | 4.8h | 13656 | 1.511 | 7 RSI / 17 EMA / 3 SL |
| `rsi88_12_plus_ema100_200` | 136 | 41.2% | 1.63% | -0.80% | 0.199% | 9.5h | 4.9h | 12565 | 1.467 | 11 RSI / 13 EMA / 3 SL |

### RSI-only sweep 85–90

| Candidate | Trades | Win rate | Avg win | Avg loss | Avg trade | Avg hold | Median hold | PnL | PF | Runner mix |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `only_rsi85` | 138 | 38.4% | 1.69% | -0.83% | 0.136% | 9.3h | 4.8h | 13544 | 1.455 | 19 RSI / 0 EMA / 8 SL |
| `only_rsi86_14` | 137 | 38.0% | 1.80% | -0.84% | 0.163% | 9.9h | 4.8h | 14858 | 1.499 | 18 RSI / 0 EMA / 9 SL |
| `only_rsi87_13` | 137 | 38.0% | 1.82% | -0.84% | 0.171% | 10.6h | 4.8h | 14750 | 1.495 | 18 RSI / 0 EMA / 9 SL |
| `only_rsi88_12` | 136 | 37.5% | 1.95% | -0.84% | 0.209% | 12.0h | 4.9h | 15728 | 1.535 | 17 RSI / 0 EMA / 10 SL |
| `only_rsi89_11` | 136 | 36.0% | 1.93% | -0.84% | 0.161% | 12.3h | 4.9h | 11643 | 1.382 | 15 RSI / 0 EMA / 12 SL |
| `only_rsi90` | 135 | 36.3% | 2.22% | -0.84% | 0.274% | 13.6h | 4.8h | 16789 | 1.558 | 15 RSI / 0 EMA / 12 SL |

### RSI + EMA100/200 combo sweep

| Candidate | Trades | Win rate | Avg win | Avg loss | Avg trade | Avg hold | Median hold | PnL | PF | Runner mix |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `rsi85_plus_ema100_200` | 138 | 40.6% | 1.49% | -0.80% | 0.132% | 8.5h | 4.8h | 10760 | 1.391 | 15 RSI / 9 EMA / 3 SL |
| `rsi86_14_plus_ema100_200` | 137 | 40.9% | 1.55% | -0.80% | 0.160% | 8.8h | 4.8h | 11805 | 1.430 | 13 RSI / 11 EMA / 3 SL |
| `rsi87_13_plus_ema100_200` | 137 | 40.9% | 1.58% | -0.80% | 0.172% | 9.0h | 4.8h | 12134 | 1.442 | 13 RSI / 11 EMA / 3 SL |
| `rsi88_12_plus_ema100_200` | 136 | 41.2% | 1.63% | -0.80% | 0.199% | 9.5h | 4.9h | 12565 | 1.467 | 11 RSI / 13 EMA / 3 SL |
| `rsi89_11_plus_ema100_200` | 136 | 40.4% | 1.63% | -0.79% | 0.187% | 9.7h | 4.9h | 11369 | 1.419 | 10 RSI / 14 EMA / 3 SL |
| `rsi90_plus_ema100_200` | 135 | 40.7% | 1.75% | -0.79% | 0.242% | 10.3h | 4.8h | 13656 | 1.511 | 7 RSI / 17 EMA / 3 SL |

## Readout


### RSI90-only

- Лучший money-mode: PnL `16789`, PF `1.558`.
- Win rate `36.3%` — формально невысокий, но средний win `2.22%` сильно больше среднего loss `-0.84%`.
- Средняя сделка `0.274%`, среднее удержание `13.6h`, медиана `4.8h`.
- Runner mix: `15 RSI / 0 EMA / 12 SL`.

### RSI88-only

- Лучший balanced-mode: PnL `15728`, PF `1.535`, Sharpe `1.681`.
- Win rate `37.5%`, avg win `1.95%`, avg loss `-0.84%`, avg trade `0.209%`.
- Runner SL меньше, чем у RSI90: `10` против `12`, но total PnL ниже примерно на `1061`.

### EMA100/200-only

- Protective-mode: PnL `12870`, PF `1.490`.
- Runner mix `0 RSI / 24 EMA / 3 SL`: почти убирает runner→SL, но средний win ниже, чем у RSI90/88.

### RSI+EMA combos

- Лучший combo: RSI90+EMA, PnL `13656`, PF `1.511`.
- Win rate `40.7%` и avg trade `0.242%` хорошие, но total PnL ниже RSI90-only: EMA уменьшает SL, но срезает часть RSI-хвостов.

---

# Latest update — Step 0 setup universe + long/short concentration

Дата обновления: 2026-06-09  
Статус: добавлены результаты Step 0 после проверки `strict / relaxed / loose_probe` и отдельный long/short concentration analysis.

---

## 14. Step 0 — зачем был нужен

После phase-gated runner exits стало понятно, что strict-кандидаты дают хороший edge, но выборка маленькая:

```text
strict:
  ~135 closed trades
  ~27 runner trades
```

Поэтому был добавлен нулевой шаг:

```text
Step 0:
  проверить не только strict,
  но и relaxed / loose_probe setup universe
```

Цель Step 0:

```text
найти, существует ли более широкий entry universe
с 300–500 сделками,
но без полного разрушения PF / maxDD / avg trade.
```

---

## 15. Setup profiles Step 0

### strict

```text
width:
  min_current_width_atr: 12
  min_recent_width_atr: 14
  width_lookback_bars: 20

untouched:
  lookback: 75
  active_bars: 8

initial exits:
  SL: 6 ATR
  TP: 14 ATR
```

### relaxed

```text
width:
  min_current_width_atr: 9
  min_recent_width_atr: 10
  width_lookback_bars: 20

untouched:
  lookback: 75
  active_bars: 8

initial exits:
  SL: 4 ATR
  TP: 10 ATR
```

### loose_probe

```text
width:
  min_current_width_atr: 8
  min_recent_width_atr: 9
  width_lookback_bars: 30

untouched:
  lookback: 50
  active_bars: 12

initial exits:
  SL: 4 ATR
  TP: 10 ATR
```

`loose_probe` был именно exploratory probe, не production-кандидат.

---

## 16. Step 0 full ranking

| Rank | Setup | Mode | Trades | PnL | PF | MaxDD | Win rate | Avg trade | Long PF | Short PF | Runner PnL | Runner mix | Initial bucket |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 1 | relaxed | RSI90 | 352 | **+21 735** | 1.268 | -55.4% | 32.7% | +0.147% | 1.322 | 1.202 | +33 967 | 18 RSI / 14 SL | 320 tr, -12 232 |
| 2 | strict | RSI90 | 135 | +16 789 | **1.558** | -31.3% | 36.3% | **+0.274%** | 1.318 | **1.936** | +18 682 | 15 RSI / 12 SL | 108 tr, -1 893 |
| 3 | relaxed | RSI88 | 355 | +16 065 | 1.200 | -52.6% | 33.5% | +0.101% | 1.328 | 1.050 | +28 186 | 21 RSI / 11 SL | 323 tr, -12 121 |
| 4 | strict | RSI88 | 136 | +15 728 | 1.535 | -35.1% | 37.5% | +0.209% | **1.637** | 1.388 | +18 001 | 17 RSI / 10 SL | 109 tr, -2 273 |
| 5 | strict | RSI90+EMA | 135 | +13 656 | 1.511 | **-30.7%** | 40.7% | +0.242% | 1.208 | **2.038** | +15 549 | 7 RSI / 17 EMA / 3 SL | 108 tr, -1 893 |
| 6 | strict | EMA100/200 | 134 | +12 870 | 1.490 | **-30.2%** | **41.0%** | +0.279% | 1.333 | 1.754 | +14 302 | 24 EMA / 3 SL | 107 tr, -1 432 |
| 7 | relaxed | RSI90+EMA | 352 | +10 950 | 1.139 | -52.9% | 33.8% | +0.091% | 1.119 | 1.163 | +23 182 | 10 RSI / 15 EMA / 7 SL | 320 tr, -12 232 |
| 8 | relaxed | EMA100/200 | 347 | +8 292 | 1.106 | -42.2% | 33.7% | +0.080% | 1.157 | 1.044 | +22 596 | 24 EMA / 7 SL | 316 tr, -14 304 |
| 9 | strict | initial | 138 | +2 639 | 1.357 | -11.2% | 40.6% | +0.180% | 1.223 | 1.585 | — | — | — |
| 10 | relaxed | initial | 357 | +2 286 | 1.122 | -19.9% | 34.7% | +0.068% | 1.248 | 0.981 | — | — | — |
| 11 | loose | RSI90 | 498 | +1 813 | 1.014 | -100.9% | 29.7% | +0.017% | 0.957 | 1.080 | +39 640 | 23 RSI / 24 SL | 451 tr, -37 827 |
| 12 | loose | RSI88 | 502 | -133 | 0.999 | -116.0% | 30.5% | -0.015% | 1.042 | 0.951 | +38 087 | 27 RSI / 20 SL | 455 tr, -38 219 |
| 13 | loose | initial | 508 | -1 775 | 0.926 | -32.5% | 31.7% | -0.029% | 0.970 | 0.876 | — | — | — |
| 14 | loose | EMA100/200 | 488 | -4 604 | 0.962 | -97.0% | 31.4% | -0.008% | 0.941 | 0.986 | +32 951 | 34 EMA / 12 SL | 442 tr, -37 555 |
| 15 | loose | RSI90+EMA | 498 | -8 893 | 0.928 | -113.1% | 31.1% | -0.026% | 0.909 | 0.950 | +28 934 | 12 RSI / 23 EMA / 12 SL | 451 tr, -37 827 |

---

## 17. Главные выводы Step 0

### 17.1 Relaxed RSI90 — новый лидер по absolute PnL и объёму сделок

```text
relaxed_adx40_runner_rsi90_fee04

trades: 352
PnL: +21 735
PF: 1.268
MaxDD: -55.4%
Win rate: 32.7%
Long PF: 1.322
Short PF: 1.202
Runner PnL: +33 967
Initial-risk PnL: -12 232
```

Это первый кандидат, который отвечает на идею:

```text
не 130 сделок,
а около 350 сделок
```

Но relaxed RSI90 нельзя считать однозначной заменой strict RSI90.

Проблема:

```text
strict RSI90:
  PF 1.558
  MaxDD -31.3%
  Avg trade +0.274%

relaxed RSI90:
  PF 1.268
  MaxDD -55.4%
  Avg trade +0.147%
```

Relaxed выигрывает по total PnL и числу сделок, но проигрывает по качеству сделки и risk profile.

---

### 17.2 Strict RSI90 остаётся quality benchmark

```text
strict_adx40_runner_rsi90_fee04

trades: 135
PnL: +16 789
PF: 1.558
MaxDD: -31.3%
Win rate: 36.3%
Long PF: 1.318
Short PF: 1.936
Runner PnL: +18 682
Initial-risk PnL: -1 893
```

Strict branch остаётся более чистым:

```text
меньше сделок,
но выше PF,
ниже DD,
выше avg trade,
сильнее short-side PF,
гораздо меньше initial-risk leakage.
```

---

### 17.3 Relaxed edge живёт за счёт runner-хвостов

У relaxed RSI90:

```text
runner bucket:
  32 trades
  +33 967 PnL

initial-risk bucket:
  320 trades
  -12 232 PnL
```

Это значит:

```text
relaxed не потому хорош,
что все 350 сделок качественные.

relaxed хорош потому,
что runner-хвосты перекрывают большую утечку
на non-runner / initial-risk сделках.
```

Это критично для будущих исследований:

```text
partial TP / BE / trailing после runner
не решат всю проблему relaxed,
потому что большая часть утечки происходит ДО runner.
```

---

### 17.4 Loose_probe rejected as-is

Loose_probe дал много сделок:

```text
488–508 trades
```

Но качество развалилось:

```text
best loose:
  loose_probe_adx40_runner_rsi90_fee04
  PnL +1 813
  PF 1.014
  MaxDD -100.9%
```

При этом runner внутри loose всё ещё положительный:

```text
loose RSI90:
  runner +39 640
  initial-risk -37 827
```

Вывод:

```text
runner-селекция реальная,
но loose entry universe слишком шумный.

loose_probe as-is отклоняется.
```

---

## 18. Long/short concentration analysis

После Step 0 появилась гипотеза:

```text
relaxed RSI90 мог заработать
только за счёт long-trend или 1–2 гигантских сделок.
```

Проверка показала более тонкую картину.

---

### 18.1 Relaxed RSI90 side split

```text
relaxed_adx40_runner_rsi90_fee04

total:
  trades: 352
  PnL: +21 735
  PF: 1.268
  MaxDD: -55.4%
  Win rate: 32.7%

long:
  trades: 198
  PnL: +14 272
  PF: 1.322
  Win rate: 32.8%

short:
  trades: 154
  PnL: +7 463
  PF: 1.202
  Win rate: 32.5%
```

Short side формально не убыточный.

Но short-side concentration плохой:

```text
relaxed RSI90 short:
  total short PnL: +7 463
  top-1 short trade: +6 656
  short PnL without top-1: +807
  short PnL without top-3: -4 963
```

Крупнейшая short-сделка:

```text
trade_id: short:222596
entry: 2022-05-07
exit: 2022-05-13
PnL: +6 656
return: +18.51%
exit: runner_rsi90_10_take
hold: 1915 bars
```

Вывод:

```text
relaxed RSI90 не является чисто long-only,
но его short edge сильно зависит от одного bear-market хвоста.
```

---

### 18.2 Relaxed long side здоровее short side

```text
relaxed RSI90 long:
  total long PnL: +14 272
  top-1 long trade: +5 210
  long PnL without top-1: +9 061
  long PnL without top-3: +2 262
```

Long side тоже имеет fat-tail concentration, но не разваливается после удаления одной сделки.

---

### 18.3 Strict RSI90 side split

```text
strict_adx40_runner_rsi90_fee04

total:
  trades: 135
  PnL: +16 789
  PF: 1.558
  MaxDD: -31.3%
  Win rate: 36.3%

long:
  PnL: +5 835
  PF: 1.318

short:
  PnL: +10 954
  PF: 1.936
```

Strict RSI90 тоже имеет концентрацию, но short side выглядит лучше:

```text
strict RSI90 short:
  total short PnL: +10 954
  top-1 short trade: +6 656
  short PnL without top-1: +4 298
  short PnL without top-3: -903
```

Сравнение после удаления top-1 short:

```text
strict short ex-top1:
  +4 298

relaxed short ex-top1:
  +807
```

Вывод:

```text
strict RSI90 остаётся более надёжным both-side quality benchmark.
```

---

### 18.4 Relaxed RSI88 side split

```text
relaxed_adx40_runner_rsi88_fee04

total:
  trades: 355
  PnL: +16 065
  PF: 1.200
  MaxDD: -52.6%

long:
  PnL: +14 221
  PF: 1.328

short:
  PnL: +1 844
  PF: 1.050
```

Relaxed RSI88 почти полностью держится на long side. Short side еле живой.

---

## 19. Updated interpretation after Step 0

До Step 0 рабочая картина была:

```text
strict RSI90 = main money candidate
strict RSI88 = balanced candidate
strict RSI90+EMA = defensive candidate
```

После Step 0 картина стала двухветочной:

```text
Track A — strict quality:
  strict RSI90
  strict RSI88
  strict RSI90+EMA

Track B — relaxed volume:
  relaxed RSI90
  relaxed RSI88
```

Но relaxed branch пока имеет статус:

```text
volume/PnL candidate,
not proven robust both-side candidate.
```

Причины:

```text
PF ниже
MaxDD выше
initial-risk leakage сильнее
short side сильно концентрирован
```

---

## 20. Updated winners

### Best absolute PnL / volume

```text
relaxed_adx40_runner_rsi90_fee04
```

Почему:

```text
352 trades
+21.7k PnL
оба направления формально положительные
runner bucket очень сильный
```

Ограничения:

```text
PF 1.268
MaxDD -55.4%
Initial-risk bucket -12.2k
short side heavily top-1 concentrated
```

---

### Best quality / PF / risk profile

```text
strict_adx40_runner_rsi90_fee04
```

Почему:

```text
PF 1.558
MaxDD -31.3%
avg trade +0.274%
short PF 1.936
initial-risk leakage small
```

---

### Best strict balanced

```text
strict_adx40_runner_rsi88_fee04
```

Почему:

```text
PF 1.535
Sharpe 1.681
runner SL lower than RSI90
better capture/giveback
```

---

### Best strict defensive

```text
strict_adx40_runner_rsi90_plus_ema100_200_fee04
```

Почему:

```text
PF 1.511
MaxDD -30.7%
runner SL only 3
short PF 2.038
```

---

### Rejected as-is

```text
loose_probe_*
```

Почему:

```text
PF around 1 or below
huge maxDD
initial-risk bucket destroys runner edge
```

---

## 21. Updated next research plan

### Step 1 — bucket decomposition report

Сделать детальную bucket-декомпозицию для:

```text
strict RSI90
strict RSI88
strict RSI90+EMA
relaxed RSI90
relaxed RSI88
relaxed RSI90+EMA
loose RSI90 as negative control
```

Buckets:

```text
initial TP
initial SL
runner RSI
runner EMA
runner SL
open / end exits if any
```

Fields:

```text
count
PnL
PF
win rate
avg win
avg loss
avg trade
avg hold
long/short split
year split
```

---

### Step 2 — year-by-year + side-by-year

Mandatory для:

```text
strict RSI90
strict RSI88
relaxed RSI90
relaxed RSI88
```

Главный вопрос:

```text
relaxed RSI90 short side живёт вне 2022 года
или почти весь short edge — это один bear-market tail?
```

Если relaxed short без 2022 разваливается:

```text
relaxed нельзя считать полноценным both-side candidate.
```

---

### Step 3 — partial TP

Тестировать на двух ветках, но с разными ожиданиями.

Strict:

```text
partial TP may reduce runner SL
while preserving RSI90 tail upside
```

Relaxed:

```text
partial TP may improve runner bucket,
but it will not solve initial-risk leakage.
```

Первичная матрица:

```text
strict RSI90
strict RSI90 + partial 25%
strict RSI90 + partial 33%
strict RSI90 + partial 50%

relaxed RSI90
relaxed RSI90 + partial 25%
relaxed RSI90 + partial 33%
relaxed RSI90 + partial 50%
```

---

### Step 4 — BE / lock stop

Не делать naive BE immediately at runner.

Тестировать только после bucket/year analysis:

```text
BE after MFE >= 1R
BE after MFE >= 1.5R
BE after initial TP touched
lock entry + fees
lock entry + 0.25 ATR
lock entry + 0.5 ATR
```

---

### Step 5 — trailing

Кандидаты:

```text
MFE giveback trailing
ATR trailing
Chandelier-style trailing
EMA trailing stop
swing-low / swing-high trailing
```

Самый логичный первый вариант:

```text
mfe_giveback_trailing_stop
```

---

### Step 6 — refined setup universe

Не продолжать loose as-is. Искать между strict и relaxed:

```text
width current:
  10 / 11 / 12

width recent:
  12 / 13 / 14

untouched:
  keep 75 / 8 first
```

Цель:

```text
найти середину:
  больше сделок, чем strict,
  но меньше leakage, чем relaxed.
```

---

## 22. Current final status

```text
Runner edge confirmed.
ADX40 remains primary runner phase trigger.
RSI90 remains best tail-capture exit.
RSI88 remains best strict balanced exit.
EMA100/200 remains protective, not profit-max.
Relaxed RSI90 is new volume/PnL leader but not yet robust.
Strict RSI90 remains quality benchmark.
Loose_probe rejected as-is.
```

Current candidate map:

```text
Quality benchmark:
  strict_adx40_runner_rsi90_fee04

Balanced strict:
  strict_adx40_runner_rsi88_fee04

Defensive strict:
  strict_adx40_runner_rsi90_plus_ema100_200_fee04

Volume/PnL candidate:
  relaxed_adx40_runner_rsi90_fee04

Volume balanced candidate:
  relaxed_adx40_runner_rsi88_fee04

Negative control:
  loose_probe_adx40_runner_rsi90_fee04
```

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
