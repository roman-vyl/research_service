# EMA200 Anchor Stack Width Research — Consolidated Historical README

Дата консолидации: 2026-06-09  
Проект: Bybit Data Engine v2 / `ema_pullback` research  
Тема: поиск naked edge вокруг EMA200 через `anchor_stack_width_setup`

---

## 1. Зачем был нужен этот эксперимент

Изначальная идея была простой:

```text
искать сделки около EMA200 pullback / touch
```

Но ранние результаты показали, что сам по себе EMA200 touch не даёт edge.

Без нормального фильтра контекста входы были почти бесполезны:

```text
no width / SL5 / TP14:
  trades: ~1205
  PF: ~0.916
  win rate: ~26.3%
  pnl: ~-6614
  maxDD: ~-0.757
```

То есть это была не “почти рабочая стратегия”, а реально плохая база:

```text
слишком много сделок
низкий win rate
PF ниже 1
большой drawdown
EMA200 touch сам по себе не фильтрует качество
```

Поэтому первая цель была не “максимальная прибыль”, а поиск условий, при которых EMA200 pullback хотя бы перестаёт быть плохой монеткой.

Практический вопрос:

```text
При каких условиях около EMA200 win rate становится не 10–25%,
а хотя бы 30–40%,
и PF выходит выше 1?
```

---

## 2. Главный прорыв: width setup

Первый реальный сдвиг дал `anchor_stack_width_setup`.

Идея:

```text
Не торговать любой touch EMA200.
Торговать pullback к EMA200 только тогда,
когда EMA stack уже достаточно расширен.
```

Anchor stack:

```text
fast:   EMA100 close
anchor: EMA200 close
slow:   EMA496 close
timeframe: base 5m
```

Width setup проверяет, насколько широко разошлись EMA внутри stack.

Торговая интерпретация:

```text
Если EMA stack узкий:
  рынок не имеет выраженного импульса / структуры;
  EMA200 touch часто является шумом.

Если EMA stack широкий:
  перед pullback был значимый directional move;
  EMA200 pullback может быть continuation setup.
```

Первый sanity width point уже резко улучшил baseline:

```text
w7 / r14 / lb35 / SL5 / TP14:
  trades: ~318
  PF: ~1.052
  win rate: ~31.4%
  pnl: ~+1083
  maxDD: ~-0.175
```

Это был первый доказанный вывод:

```text
EMA200 touch itself is not the edge.
EMA200 pullback after expanded EMA stack is the first real edge.
```

---

## 3. Термины width setup

В экспериментах использовались параметры:

```text
min_current_width_atr
min_recent_width_atr
width_lookback_bars
```

Сокращения:

```text
w12 = min_current_width_atr 12
r14 = min_recent_width_atr 14
lb20 = width_lookback_bars 20
```

Смысл:

```text
current width:
  насколько широк EMA stack прямо сейчас

recent width:
  была ли достаточная ширина в недавнем окне

lookback:
  насколько далеко назад смотрим recent width
```

Важно: recent window включает текущий бар. Поэтому если:

```text
current width >= 12
```

то:

```text
recent width <= 12
```

часто становится redundant, потому что текущий бар уже удовлетворяет recent condition.

---

## 4. Phase 0 — sanity: no width vs first width

Цель:

```text
Понять, помогает ли width вообще.
```

Результат:

```text
no width / SL5 / TP14:
  trades: ~1205
  PF: ~0.916
  win rate: ~26.3%
  pnl: ~-6614
  maxDD: ~-0.757

w7 / r14 / lb35 / SL5 / TP14:
  trades: ~318
  PF: ~1.052
  win rate: ~31.4%
  pnl: ~+1083
  maxDD: ~-0.175
```

Вывод:

```text
anchor_stack_width_setup работает как entry-quality filter.
```

Это был первый момент, когда стало понятно, что EMA200 pullback можно продолжать исследовать.

---

## 5. Phase 1 — current width search

Цель:

```text
Изолировать min_current_width_atr.
```

Фиксировали:

```text
recent = 1
width_lookback_bars = 35
SL5 / TP14
```

Ключевые точки:

```text
w9:
  PF ~0.989
  pnl ~-227

w10:
  PF ~1.021
  pnl ~+311

w12:
  PF ~1.262
  pnl ~+1784
```

Вывод:

```text
Главный параметр качества входа — current stack width.
Низкие thresholds 2–8 не чистят входы достаточно.
Серьёзный edge начинается ближе к w12.
```

Первый рабочий baseline:

```text
w12 / r1 / lb35
```

---

## 6. Phase 2 — SL/TP search on w12/r1/lb35

Цель:

```text
Подобрать ATR SL/TP после нахождения первого серьёзного width baseline.
```

Phase 2A grid:

```text
width = 12
recent = 1
lookback = 35
SL = 4, 5, 6, 7, 8
TP = 10, 12, 14, 16, 18, 20
```

Главный clean baseline:

```text
w12 / r1 / lb35 / SL6 / TP14

trades: ~143
PF: ~1.262
win rate: ~38.5%
pnl: ~+1991
maxDD: ~-0.110
long PF: ~1.232
short PF: ~1.307
```

Runner-like candidate:

```text
w12 / r1 / lb35 / SL5 / TP20

PF: ~1.307
pnl: ~+2398
but:
  lower win rate
  more runner dependence
  less clean diagnostic profile
```

Вывод:

```text
SL6 / TP14 стал clean entry-quality baseline.
SL5 / TP20 был сохранён как runner branch, но не основной baseline.
```

Важно:

```text
Уже здесь стало видно,
что setup может быть не маленьким bounce,
а continuation после pullback.
```

---

## 7. Phase 3A/3B — recent width and lookback

Цель:

```text
Проверить, улучшает ли recent expansion уже найденный current width edge.
```

Фиксировали:

```text
current width = 12
SL6 / TP14
```

### 7.1 recent <= current is redundant

Результат:

```text
w12 / r1 or r12 / any tested lookback / SL6 / TP14:
  trades: ~143
  PF: ~1.262
  pnl: ~+1991
```

Причина:

```text
Если current width >= 12,
то recent window уже содержит текущий бар с width >= 12.
Поэтому recent <= 12 не добавляет нового фильтра.
```

Вывод:

```text
Не тратить время на r1/r8/r10/r12,
если current width уже 12.
```

### 7.2 strict continuation baseline

Лучший balanced result:

```text
w12 / r14 / width_lb20 / SL6 / TP14

trades: ~138
PF: ~1.410
win rate: ~40.6%
pnl: ~+2993
maxDD: ~-0.110
long PF: ~1.270
short PF: ~1.647
high_mfe_low_capture: 2
stop_loss_after_bad_context: 82
```

### 7.3 fresh expansion matters

Для `r14` короткий lookback оказался лучше:

```text
w12/r14/lb20:
  PF ~1.410
  pnl ~+2993

w12/r14/lb35:
  PF ~1.402
  pnl ~+2942

w12/r14/lb50:
  PF ~1.356
  pnl ~+2566

w12/r14/lb75+:
  PF ~1.335
  pnl ~+2435
```

Вывод:

```text
Для strict continuation важна свежая expansion.
Старая expansion допускает поздние/слабые входы.
```

---

## 8. Phase 4A — small exits on strict setup

Цель:

```text
Проверить, является ли strict setup локальным EMA200 bounce.
```

Фиксированный entry:

```text
w12 / r14 / width_lb20
untouched75 / active8
```

Тестировали smaller ATR rails:

```text
SL 2.5–5
TP 4–12
```

Reference оставался лучшим:

```text
w12/r14/wlb20/SL6/TP14

trades: ~138
PF: ~1.409
win rate: ~40.6%
pnl: ~+2993
maxDD: ~-0.110
long PF: ~1.270
short PF: ~1.647
```

Лучший smaller/medium candidate:

```text
w12/r14/wlb20/SL5/TP12

trades: ~140
PF: ~1.196
pnl: ~+1214
long PF: ~1.168
short PF: ~1.238
```

Вывод:

```text
Small exits не побеждают на strict setup.
Strict branch — это не локальный bounce от EMA200.
Это trend continuation после сильного расширения EMA stack.
```

Отвергнуто как main strict branch:

```text
SL 2.5–4
TP 4–10
```

---

## 9. Phase 4B — relaxed width with smaller exits

Цель:

```text
Проверить, существует ли более частая medium/bounce ветка,
если ослабить width и использовать меньшие rails.
```

Лучший useful relaxed candidate:

```text
w9 / r10 / width_lb20 / SL4 / TP10

trades: ~357
PF: ~1.168
win rate: ~34.7%
pnl: ~+3195
maxDD: ~-0.182
long PF: ~1.300
short PF: ~1.024
```

Почему важно:

```text
+ сильно больше сделок, чем strict
+ обе стороны формально положительные
+ useful branch for statistics
```

Почему опасно:

```text
- PF ниже
- drawdown хуже
- short side barely profitable
- bad-context stops much higher
- fees larger
```

Слабая зона:

```text
w8/r10:
  too dirty
  short side mostly breaks
```

Balanced but weak area:

```text
w10/r12:
  more balanced
  but edge too small
```

Вывод:

```text
Появились две отдельные ветки:

A. Strict continuation:
   w12/r14/wlb20/SL6/TP14

B. Relaxed medium/bounce:
   w9/r10/wlb20/SL4/TP10
```

---

## 10. Phase 5A — refine exits around relaxed branch

Фиксировали:

```text
w9 / r10 / width_lb20
untouched75 / active8
```

Тестировали exits вокруг:

```text
SL4 / TP10
```

Лучший кандидат остался:

```text
w9/r10/wlb20/SL4/TP10

trades: ~357
PF: ~1.168
win rate: ~34.7%
pnl: ~3195
maxDD: ~-0.182
long PF: ~1.300
short PF: ~1.024
```

Близкий, но хуже:

```text
w9/r10/wlb20/SL4/TP12

trades: ~354
PF: ~1.163
pnl: ~3177
long PF: ~1.280
short PF: ~1.033
```

Вывод:

```text
SL4 / TP10 — local optimum for relaxed/medium mode.
TP12 не даёт явного улучшения.
```

---

## 11. Phase 5B — entry neighborhood with medium exits

Цель:

```text
Проверить соседние width-зоны вокруг relaxed candidate.
```

Тестировали:

```text
w8/r10
w9/r10
w9/r12
w10/r10
w10/r12
w12/r14 reference
```

Главный вывод:

```text
w9/r10/SL4/TP10 остаётся лучшим relaxed both-side setup.
```

### w9/r12

```text
w9/r12/wlb20/SL4/TP10:
  trades ~305
  PF ~1.154
  pnl ~2295
  DD ~-0.153
  long PF ~1.302
  short PF ~0.959
```

Вывод:

```text
r12 немного чистит плохие входы,
но short side падает ниже 1.
```

### w8/r10

```text
w8/r10/wlb20/SL4/TP10:
  trades ~425
  PF ~1.064
  win rate ~33.2%
  pnl ~1403
  DD ~-0.256
  long PF ~1.130
  short PF ~0.988
```

Вывод:

```text
w8 too loose for both-side trading.
```

### w10/r12

```text
w10/r12/wlb20/SL4/TP10:
  trades ~256
  PF ~1.059
  long PF ~1.090
  short PF ~1.014
```

Вывод:

```text
more balanced, but edge too weak.
```

---

## 12. Phase 6 — HTF context regime sweep

Цель:

```text
Проверить, улучшает ли HTF context входы strict/relaxed branch.
```

Технический нюанс:

```text
context_consumption нельзя было повесить на anchor_stack_width_setup,
поэтому HTF gate временно вешался на untouched_anchor_setup.

Так как setups compose by AND,
это всё равно gating whole entry permission.
```

HTF contexts:

```text
1h 20/50/100
1h 50/100/200
```

Regimes:

```text
aligned
countertrend
aligned_neutral
```

Base candidates:

```text
strict_continuation:
  w12/r14/wlb20/SL6/TP14

relaxed_medium:
  w9/r10/wlb20/SL4/TP10

relaxed_cleaner_recent:
  w9/r12/wlb20/SL4/TP10
```

Главный смысл Phase 6:

```text
Понять, является ли HTF trend missing filter,
особенно для relaxed short side и bad-context stops.
```

Интерпретация:

```text
aligned better:
  HTF trend useful as entry filter

aligned_neutral better:
  pure aligned too strict

relaxed short improves:
  HTF context may be missing piece for relaxed both-side trading
```

---

## 13. Phase 7 — MFE depth diagnostics

Цель:

```text
Не оптимизировать TP,
а измерить, насколько большие favorable excursions вообще появляются.
```

Важно:

```text
No post-exit lookahead.
No shadow trades.
No hypothetical continuation.
Only entry -> actual exit window.
```

Для диагностики использовались большие TP, чтобы сделки жили дольше и MFE было видно.

### Relaxed diagnostic branch

```text
w9/r10/wlb20/SL4/TP20-30
```

### Strict diagnostic branch

```text
w12/r14/wlb20/SL6/TP24-30
```

Core MFE:

```text
Relaxed TP30:
  trades: 330
  median MFE: 0.71%
  p75 MFE: 2.52%
  p90 MFE: 4.62%

Strict TP30:
  trades: 136
  median MFE: 0.82%
  p75 MFE: 2.78%
  p90 MFE: 3.94%
```

Выводы:

```text
1. High-MFE tail exists.
2. Normal good bounce is around 2.0–2.8% MFE.
3. Strong tail is around 3.5–4.6% MFE.
4. Simply increasing fixed TP globally is not the final answer.
```

Failed-capture insight:

```text
Некоторые stop-loss trades всё равно имели meaningful MFE
и потом отдали движение обратно в SL.
```

Это стало основанием для dynamic exit research:

```text
EMA trailing
loss-of-momentum
break-even / lock
runner management
```

---

## 14. Phase 8 — dynamic exits / 1h RSI overheat

Цель:

```text
Начать тестировать dynamic exits вместо fixed ATR TP.
```

Phase 8A / 8A.1 tested 1h RSI overheat exits.

Branches:

```text
relaxed:
  w9/r10/wlb20
  SL4
  safety TP40

strict:
  w12/r14/wlb20
  SL6
  safety TP40
```

1h RSI thresholds:

```text
80/20
85/15
90/10
```

Important result:

```text
1h RSI signal exits themselves were high quality,
but 1h RSI alone was not enough as the only dynamic exit layer.
```

Signal quality examples:

```text
relaxed 1h RSI80:
  signal exits: 38
  signal PnL: +11750
  signal winrate: 94.7%

relaxed 1h RSI85:
  signal exits: 20
  signal PnL: +9081
  signal winrate: 95.0%

relaxed 1h RSI90:
  signal exits: 8
  signal PnL: +5698
  signal winrate: 100.0%
```

Core diagnostic:

```text
~28–31% of trades created meaningful high MFE.
Only ~12–18% both reached high MFE and captured it well.
```

Interpretation:

```text
Entry layer can create real movement.
Exit layer does not capture enough of it.
1h RSI is useful as overheat cap,
but not complete trade management.
```

---

## 15. Final baselines from width research

### Strict continuation baseline

```text
w12 / r14 / width_lb20 / untouched75 / active8 / SL6 / TP14
```

Use as:

```text
clean quality benchmark
continuation branch
future runner / context / management baseline
```

Pros:

```text
highest PF
lowest drawdown
best short quality
lowest bad-context leakage
strongest proof of width edge
```

Cons:

```text
only ~138 trades
may miss smaller bounce opportunities
wide rails
not local EMA200 bounce
```

---

### Relaxed medium/bounce baseline

```text
w9 / r10 / width_lb20 / untouched75 / active8 / SL4 / TP10
```

Use as:

```text
exploratory high-sample branch
filter/context testing branch
volume candidate
```

Pros:

```text
~357 trades
positive both-side raw result
good long side
more suitable for statistics
```

Cons:

```text
PF lower
drawdown higher
short barely profitable
bad-context stops much higher
more fee-sensitive
```

---

## 16. What was confirmed

```text
1. Naked EMA200 touch is not enough.
2. Anchor stack width is the first real edge filter.
3. Current width matters more than generic recent width.
4. recent <= current is redundant.
5. Fresh expansion matters for strict continuation.
6. Strict setup wants continuation exits, not small bounce exits.
7. Relaxed setup is a separate medium/bounce regime.
8. Shorts are fragile in relaxed mode.
9. High-MFE tail exists.
10. Global larger TP is not the solution.
11. 1h RSI overheat exits are high quality but incomplete.
```

---

## 17. What was rejected or deprioritized

```text
generic no-width EMA200 touch
w8 both-side relaxed mode
small exits on strict setup
global TP increase for all trades
recent thresholds <= current width
blind SL/TP sweeping without context
treating strict and relaxed as one same regime
using 1h RSI as the only dynamic exit engine
```

---

## 18. Historical conclusion

The “width experiment” found the first real edge in the EMA200 pullback idea.

The key historical result:

```text
EMA200 pullback has no stable naked edge by itself.
The edge appears when EMA200 pullback happens after EMA stack expansion.
```

This produced two useful branches:

```text
strict continuation:
  w12/r14/lb20/SL6/TP14
  fewer trades, higher quality

relaxed medium/bounce:
  w9/r10/lb20/SL4/TP10
  more trades, lower quality
```

The next stages should build on these baselines rather than restart blind parameter search.

---

## 19. How this connects to the current runner research

The current phase-gated runner work did not replace the width experiment. It sits on top of it.

Current strict runner candidate:

```text
strict width baseline
+ ADX/DI 40 runner phase
+ disable initial TP at runner
+ runtime RSI / EMA exits
```

Current relaxed runner candidate:

```text
relaxed width baseline
+ ADX/DI 40 runner phase
+ disable initial TP at runner
+ runtime RSI / EMA exits
```

Thus the width experiment remains the foundation:

```text
width setup = entry edge
runner management = exit/capture layer
```

Do not confuse these layers.

---

## 20. Recommended archival note

If this README is placed inside the old width sweep experiment folder, keep this as the final summary:

```text
This experiment did not produce a final production strategy.
It produced the first validated EMA200 entry edge:
anchor-stack width expansion before EMA200 pullback.

All later HTF context, RSI, ADX/DI runner, EMA loss-of-momentum,
partial TP, break-even, and trailing experiments are downstream
trade-management/context layers built on this width edge.
```
