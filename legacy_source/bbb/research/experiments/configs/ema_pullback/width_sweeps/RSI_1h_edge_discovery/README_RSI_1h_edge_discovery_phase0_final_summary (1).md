# RSI 1h Edge Discovery — Phase 0 Final Summary

## Статус

Phase 0 закрыта как исследовательская калибровка 1h ATR symmetric SL/TP ruler для EMA200 pullback ветки.

Важно: итог Phase 0 не сводится к одному “лучший PnL”. Мы разделили несколько разных режимов, потому что широкие 1h ATR rails начинают менять смысл теста.

Главный вывод:

```text
EMA200 edge нельзя искать на одной универсальной SL/TP линейке.
Нужно дальше сравнивать несколько режимов:
  lower semantic EMA200 ruler
  upper/profit comparator
  wide continuation comparator
```

## Почему Phase 0 пришлось расширить

Изначально мы хотели подобрать симметричную 1h ATR линейку как измерительный ruler.

Но при росте множителя выяснилось:

```text
3–4 × 1h ATR для 5m EMA200 pullback — это уже огромный stop/take.
Такой SL/TP может быть шире локального EMA stack.
Иногда stop уходит далеко за EMA200-структуру, вплоть до зоны намного медленнее anchor.
В таком режиме тест начинает измерять не чистый EMA200 pullback, а широкое continuation holding.
```

Поэтому Phase 0 разделена на два смысловых слоя:

```text
1. Lower semantic ruler:
   линейка ещё близка к EMA200 pullback структуре.

2. Wide continuation rail:
   линейка уже проверяет удержание движения после входа.
```

Оба слоя полезны, но их нельзя смешивать в одном выводе.

---

# Phase 0A / coarse 1h ATR ruler

## Цель

Проверить грубую сетку 1h ATR symmetric SL/TP.

## Главный результат

Лучший coarse candidate:

```text
relaxed_known + 1hATR SL2 / TP2

trades: 352
PnL: +2 889
PF: 1.087
win rate: 56.5%
maxDD: -19.4%
long PF: 1.139
short PF: 1.037
long PnL: +2 270
short PnL: +619
```

Вывод:

```text
1hATR 2/2 уже лучше base-ATR ruler.
relaxed_known выглядит чище, чем strict_known.
no_width остаётся мусором.
known_width_sanity недостаточен.
```

---

# Phase 0B / fine sweep 1.50–2.50

## Цель

Уточнить область вокруг 2.0.

## Главный результат

Лучший observed relaxed candidate:

```text
relaxed_known + 1hATR SL2.45 / TP2.45

trades: 350
PnL: +4 946
PF: 1.123
win rate: 56.3%
maxDD: -22.6%
long PF: 1.161
short PF: 1.086
long PnL: +3 205
short PnL: +1 741
```

Вывод:

```text
2.45 выглядит сильнее 2.0.
Но 2.50 рядом, значит верхняя граница ещё не закрыта.
```

---

# Phase 0C / upper guard 2.50–3.00

## Цель

Проверить, не находится ли максимум выше 2.50.

## Главный результат

Лучший relaxed:

```text
relaxed_known + 1hATR SL3 / TP3

trades: 339
PnL: +10 727
PF: 1.178
win rate: 56.3%
maxDD: -22.8%
long PF: 1.134
short PF: 1.223
long PnL: +4 127
short PnL: +6 600
```

Strict тоже резко улучшился:

```text
strict_known + 1hATR SL3 / TP3

trades: 138
PnL: +5 595
PF: 1.310
maxDD: -14.1%
long PF: 1.198
short PF: 1.473
```

Вывод:

```text
3.0 снова оказался верхней границей.
Началась wide continuation картина.
```

---

# Phase 0D / wide guard 3.00–4.00

## Цель

Проверить, является ли 3.0 локальным пиком или wide rails продолжают улучшаться.

## Лучший relaxed

```text
relaxed_known + 1hATR SL3.75 / TP3.75

trades: 307
PnL: +15 639
PF: 1.236
win rate: 57.0%
maxDD: -32.5%
long PF: 1.064
short PF: 1.435
long PnL: +2 273
short PnL: +13 366
```

## Лучший strict

```text
strict_known + 1hATR SL4 / TP4

trades: 131
PnL: +9 540
PF: 1.404
win rate: 61.8%
maxDD: -22.1%
long PF: 1.302
short PF: 1.556
long PnL: +4 276
short PnL: +5 264
```

Вывод:

```text
3–4 × 1hATR даёт сильные результаты,
но это уже не чистая EMA200 pullback ruler calibration.
Это отдельный wide continuation режим.
```

---

# Phase 0E / lower semantic sweep 0.75–2.50

## Цель

Вернуться ниже и найти линейку, которая ещё имеет смысл относительно EMA200 pullback структуры.

## Три зоны

```text
0.75–1.80:
  слишком узко / шум / комиссии
  relaxed mostly negative
  short side особенно слабый

1.85–2.35:
  рабочая lower semantic EMA200-compatible зона
  обе стороны могут быть положительными
  drawdown ниже, чем у 3–4× 1hATR

2.45–2.50:
  лучший raw PnL lower sweep,
  но уже верхняя transition зона к continuation behavior
```

## Лучший raw lower result

```text
relaxed_known + 1hATR SL2.45 / TP2.45

trades: 350
PnL: +4 946
PF: 1.123
win rate: 56.3%
maxDD: -22.6%
long PF: 1.161
short PF: 1.086
long PnL: +3 205
short PnL: +1 741
```

## Лучший semantic compromise

```text
relaxed_known + 1hATR SL2.15 / TP2.15

trades: 352
PnL: +3 697
PF: 1.108
win rate: 56.3%
maxDD: -20.0%
long PF: 1.146
short PF: 1.071
long PnL: +2 479
short PnL: +1 218
```

## Conservative lower semantic ruler

```text
relaxed_known + 1hATR SL1.90 / TP1.90

trades: 356
PnL: +2 817
PF: 1.089
win rate: 56.7%
maxDD: -15.3%
long PF: 1.109
short PF: 1.068
long PnL: +1 745
short PnL: +1 072
```

Вывод:

```text
Для дальнейшего поиска EMA200 edge основной lower ruler — не 3–4 ATR.
Главные semantic candidates: 1.90, 2.15, 2.35.
2.45/2.50 оставить как upper/profit comparator.
```

---

# Итоговые варианты, которые оставляем для дальнейшего сравнения

## Group A — Lower semantic EMA200 rulers

Эти варианты оставляем как основные для поиска именно EMA200 pullback edge.

### A1 — Conservative semantic ruler

```text
relaxed_known + 1hATR SL1.90 / TP1.90

Роль:
  самый аккуратный lower semantic ruler

Почему оставляем:
  обе стороны положительные
  maxDD ниже
  меньше риска, что SL/TP уже вышли из EMA200-семантики

Использование дальше:
  Phase 1A current-width sweep
```

### A2 — Primary semantic compromise

```text
relaxed_known + 1hATR SL2.15 / TP2.15

Роль:
  основной semantic ruler

Почему оставляем:
  лучший баланс PF / PnL / maxDD / side balance
  ещё не выглядит как wide continuation

Использование дальше:
  Phase 1A current-width sweep
```

### A3 — Upper semantic comparator

```text
relaxed_known + 1hATR SL2.35 / TP2.35

Роль:
  верхняя граница semantic ruler

Почему оставляем:
  сильнее по PnL
  обе стороны положительные
  ещё не настолько широкий как 3–4 ATR

Использование дальше:
  Phase 1A current-width sweep
```

---

## Group B — Upper/profit transition comparators

Эти варианты не считаем основными semantic rulers, но оставляем как контроль перехода к более широкому режиму.

### B1 — Best lower raw result

```text
relaxed_known + 1hATR SL2.45 / TP2.45

Роль:
  upper/profit comparator

Почему оставляем:
  лучший raw result в lower sweep
  показывает, насколько мы теряем, если выбираем более семантически чистый 2.15

Риск:
  уже близко к transition zone
```

### B2 — Boundary comparator

```text
relaxed_known + 1hATR SL2.50 / TP2.50

Роль:
  верхняя граница lower/transition зоны

Почему оставляем:
  помогает отделить semantic ruler от wide-continuation начала

Риск:
  может уже начинать тянуть в continuation behavior
```

---

## Group C — Wide continuation comparators

Эти варианты не используем как базовый ruler для EMA200 edge discovery, но оставляем как отдельную гипотезу.

### C1 — Relaxed wide continuation

```text
relaxed_known + 1hATR SL3.75 / TP3.75

Роль:
  high-PnL wide continuation comparator

Почему оставляем:
  максимальный relaxed PnL
  показывает потенциал широкого удержания

Риск:
  short-carried
  long side почти на грани
  maxDD сильно выше
```

### C2 — Strict wide quality

```text
strict_known + 1hATR SL4 / TP4

Роль:
  quality wide continuation comparator

Почему оставляем:
  лучший strict quality point
  обе стороны сильные
  PF высокий

Риск:
  это точно уже не локальный EMA200 bounce ruler
  меньше сделок
  другой торговый режим
```

---

# Итоговая таблица выбранных вариантов

| Group | Variant | Branch | 1hATR SL/TP | Роль |
|---|---|---|---:|---|
| A1 | conservative semantic | relaxed_known | 1.90 / 1.90 | нижняя аккуратная EMA200 линейка |
| A2 | primary semantic | relaxed_known | 2.15 / 2.15 | основной semantic ruler |
| A3 | upper semantic | relaxed_known | 2.35 / 2.35 | верх semantic зоны |
| B1 | upper/profit | relaxed_known | 2.45 / 2.45 | лучший lower raw result |
| B2 | transition boundary | relaxed_known | 2.50 / 2.50 | граница перед continuation |
| C1 | relaxed wide continuation | relaxed_known | 3.75 / 3.75 | высокий PnL, short-carried |
| C2 | strict wide continuation | strict_known | 4.00 / 4.00 | quality wide continuation |

---

# Что делаем дальше

## Phase 1A — current-width sweep для semantic rulers

Основной следующий шаг:

```text
branch:
  relaxed-style

recent:
  10

lookback:
  20

untouched:
  lookback 75
  active 8

rails:
  1hATR 1.90 / 1.90
  1hATR 2.15 / 2.15
  1hATR 2.35 / 2.35

current width:
  w6
  w7
  w8
  w9
  w10
  w11
  w12
  w13
  w14
  w16
```

Цель:

```text
найти current-width зону,
где edge существует именно на EMA200-compatible rails.
```

## Phase 1B — transition comparator

Опционально после 1A:

```text
rails:
  1hATR 2.45 / 2.45
  1hATR 2.50 / 2.50

branch:
  relaxed-style

purpose:
  проверить, насколько лучше raw profit при переходе к upper zone
```

## Phase 1C — wide continuation branch

Отдельная гипотеза, не смешивать с 1A:

```text
relaxed_known:
  1hATR 3.75 / 3.75

strict_known:
  1hATR 4.00 / 4.00
```

Цель:

```text
понять, это реальный continuation edge или просто широкое удержание,
которое маскирует слабость локального EMA200 входа.
```

---

# Что пока не добавлять

До завершения Phase 1A не добавлять:

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
```

Причина:

```text
Сначала нужно понять,
какая current-width зона создаёт entry edge
на адекватной EMA200-compatible SL/TP линейке.
```

---

# Финальный вывод Phase 0

```text
1. EMA200 naked touch не является edge.

2. Width setup остаётся ключевым кандидатом на entry edge.

3. 1hATR SL/TP лучше base-ATR для этой ветки,
   но множитель критически меняет смысл теста.

4. 1hATR 1.90–2.35 — рабочая lower semantic зона.

5. 1hATR 2.45–2.50 — верхняя transition зона.

6. 1hATR 3–4 — wide continuation режим,
   полезный как отдельная гипотеза,
   но не как базовая EMA200 pullback ruler calibration.

7. Следующий честный шаг:
   current-width sweep на 1.90 / 2.15 / 2.35.
