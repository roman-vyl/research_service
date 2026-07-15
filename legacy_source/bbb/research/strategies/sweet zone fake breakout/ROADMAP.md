# Sweet Zone Fake Breakout Roadmap

## Назначение

Этот документ описывает дорожную карту стратегии Sweet Zone Sweep Reaction.

Базовая версия строится только на OHLCV:

```text
SweetZone -> SweepEvent -> VolumeConfirmation -> ReactionSignal -> Entry
```

Open interest, funding, liquidation events, CVD и полноценная Estimated Liquidation Pressure Zone модель не входят в первый MVP. Они вынесены в отдельные расширения после проверки базового edge.

## 0. Предусловия и допущения

Текущий `data_engine/` дает чистые свечи и остается слоем данных. В базовом MVP не добавляем в него стратегии, сигналы, vectorbt, отчеты и торговую логику.

На первом этапе используем только:

- `open`;
- `high`;
- `low`;
- `close`;
- `volume`;
- timestamp/index свечи.

Новая исполняемая strategy family должна жить в Python-пакете с корректным именем, например:

```text
research/strategies/sweet_zone_sweep_reaction/
```

Текущая папка `research/strategies/sweet zone fake breakout/` остается research-bay для PDF, `idea.md` и этого roadmap-документа. Папка с пробелами не должна становиться импортируемым Python-пакетом.

Все детекторы должны быть look-ahead-safe:

- решение принимается только после закрытия свечи;
- rolling baseline не включает текущую свечу;
- `previous_day_high/low` доступны только после завершения предыдущего дня;
- resample и session boundaries не должны подмешивать будущие данные.

## Архитектурная форма MVP

Стратегия должна лечь в существующую research-архитектуру:

```text
clean candles
-> StrategySpec
-> FeaturePlan
-> feature calculations
-> Component Registry
-> direction / blockers / setup / trigger / exits / risk
-> signals
-> vectorbt
-> JSON report
```

Предполагаемое соответствие компонентов:

- Direction: базово `no_direction_filter`; позже HTF bias.
- Blockers: session filter, ATR floor, cooldown, consumed-zone blocker.
- Setup: price is near active sweet zone.
- Trigger: sweep + volume anomaly + reaction.
- Exits: stop behind sweep extreme, fixed R take profit.
- Risk: базово `no_risk_filter`.

## Stage 1 - Volume Anomaly Detector

Цель: научиться надежно находить свечи и кластеры с необычно высоким объемом без сделок и без зон.

Минимальные признаки:

- rolling median volume;
- rolling MAD;
- Hampel score;
- simple volume ratio;
- 1m single-spike flag;
- 5m cluster flag.

Базовые параметры:

```yaml
volume_anomaly:
  intraday:
    timeframe: 1m
    baseline_window: 120
    baseline_method: rolling_median
    spike_ratio: 10.0
    hampel_score: 4.0
  swing:
    timeframe: 5m
    baseline_window: 144
    cluster_window: 6
    cluster_ratio: 4.5
    min_spike_count: 2
```

Важно: baseline volume должен считаться по прошлым свечам. Текущая свеча не входит в baseline.

Выходной диагностический объект:

```text
VolumeAnomalyEvent:
    symbol
    timeframe
    timestamp
    volume
    baseline_volume
    volume_ratio
    hampel_score
    anomaly_type
```

Что сделать:

- посчитать volume baseline;
- вывести top-N событий по `volume_ratio` и `hampel_score`;
- сохранить диагностический JSON/CSV;
- вручную проверить события на графике.

Acceptance criteria:

- на BTCUSDT 1m за 30 дней есть диагностический список top events;
- видно не менее 50 событий для ручной проверки;
- прошлый экстремальный объем не ломает baseline следующих свечей;
- detector работает без торговых входов.

## Stage 2 - Sweet Zone Context

Цель: определить зоны, рядом с которыми sweep и volume anomaly имеют смысл.

MVP-источники зон:

- previous day high;
- previous day low;
- current session high;
- current session low;
- local swing high;
- local swing low;
- manual zones из конфига.

Следующий приоритетный источник после MVP: equal highs / equal lows.

Зона должна быть диапазоном, а не линией. Базовая ширина:

```yaml
zones:
  zone_width:
    mode: percent
    value: 0.0015
```

Альтернативный режим:

```text
zone_width = ATR(14) * 0.1
```

Выходной объект:

```text
SweetZone:
    zone_id
    symbol
    timeframe
    side: upper | lower
    price_low
    price_high
    source
    strength
    created_at
    expires_at
```

De-duplication:

- если `previous_day_high` почти совпал со `swing_high`, не создавать две независимые зоны;
- близкие зоны объединять или повышать `strength`;
- приоритет источников фиксировать в конфиге.

Acceptance criteria:

- previous day high/low корректно сдвинуты на один день;
- зоны визуально совпадают с очевидными уровнями;
- нет пачки дублирующих зон вокруг одного уровня;
- минимум previous day high/low работает до добавления сложных источников.

## Stage 3 - Sweep Detector

Цель: определить факт съема зоны.

Для нижней зоны:

```text
low < zone_low - min_sweep_depth
```

Для верхней зоны:

```text
high > zone_high + min_sweep_depth
```

Базовые параметры:

```yaml
sweep:
  min_depth:
    mode: percent
    value: 0.0007
  max_bars_after_touch: 3
```

ATR-вариант:

```text
min_sweep_depth = ATR(14) * 0.1
```

State machine для зоны:

```text
armed -> swept -> reacted -> consumed
```

Правила:

- `armed`: зона активна и может быть снята;
- `swept`: цена проколола зону на минимальную глубину;
- `reacted`: после прокола появилась реакция;
- `consumed`: зона использована, новых сделок от нее не открываем.

Выходной объект:

```text
SweepEvent:
    sweep_event_id
    zone_id
    timestamp
    side: sweep_lower | sweep_upper
    sweep_depth
    sweep_extreme_price
    candle_open
    candle_high
    candle_low
    candle_close
```

Acceptance criteria:

- один sweep не создает несколько независимых сделок;
- зона не переиспользуется после `consumed`;
- на BTCUSDT 1m/5m детектор находит очевидные проколы предыдущего high/low;
- каждый SweepEvent привязан к конкретной зоне.

## Stage 4 - Reaction Detector

Цель: определить, был ли после sweep отказ от продолжения пробоя.

MVP-паттерны для long после нижнего sweep:

- close reclaim: свеча закрылась выше `zone_low`;
- pinbar: длинный нижний фитиль, `lower_wick_ratio >= 0.5`;
- bullish engulfing;
- next candle break: следующая свеча закрылась выше high sweep-свечи.

MVP-паттерны для short после верхнего sweep:

- close reclaim вниз: свеча закрылась ниже `zone_high`;
- pinbar: длинный верхний фитиль, `upper_wick_ratio >= 0.5`;
- bearish engulfing;
- next candle break: следующая свеча закрылась ниже low sweep-свечи.

Volume confirmation:

- в MVP реакция считается торговой только если sweep-свеча или ближайший кластер подтвержден VolumeAnomalyDetector;
- без volume anomaly событие можно логировать, но не использовать как entry.

Выходной объект:

```text
ReactionSignal:
    reaction_signal_id
    sweep_event_id
    timestamp
    direction: long | short
    confirmation_type
    volume_ratio
    hampel_score
    confidence
```

Acceptance criteria:

- для каждого SweepEvent есть либо ReactionSignal, либо явная причина отсутствия реакции;
- тип реакции логируется;
- паттерны работают только на закрытых свечах;
- volume confirmation является отдельным компонентом, а не скрытой частью price-action.

## Stage 5 - Backtest Baseline

Цель: собрать первую торговую версию.

Long:

```text
lower sweet zone
+ sweep down
+ volume anomaly
+ reaction up
=> long entry
```

Short:

```text
upper sweet zone
+ sweep up
+ volume anomaly
+ reaction down
=> short entry
```

Базовый stop:

```text
long_stop = sweep_low - buffer
short_stop = sweep_high + buffer
```

Базовый take profit:

```text
take_profit = 2R
```

Стартовый конфиг:

```yaml
strategy:
  family: sweet_zone_sweep_reaction
  symbol: BTCUSDT
  base_timeframe: 5m
  execution_timeframe: 1m

entry:
  require_zone_touch: true
  require_volume_anomaly: true
  require_reaction: true

risk:
  stop_mode: sweep_extreme
  stop_buffer:
    mode: atr
    value: 0.05
  take_profit_mode: fixed_r
  take_profit_r: 2.0
```

Trade records должны дополнительно хранить:

```text
sweep_event_id
zone_id
zone_source
zone_side
sweep_depth
volume_ratio
hampel_score
reaction_type
stop_price
take_profit_price
```

Acceptance criteria:

- стратегия запускается через vectorbt;
- JSON report использует существующую schema v2 или совместимое расширение;
- long и short считаются отдельно;
- disabled side не генерирует сигналы;
- все сделки можно связать с zone -> sweep -> reaction.

## Stage 6 - Инкрементальный анализ фильтров

Цель: понять, какие фильтры реально улучшают edge, а какие просто уменьшают количество сделок.

Сравнить варианты:

- sweep only;
- sweep + volume anomaly;
- sweep + volume anomaly + reaction;
- sweep + volume anomaly + reaction + price-action pattern;
- long отдельно;
- short отдельно;
- 1m intraday отдельно;
- 5m swing отдельно;
- previous day zones отдельно;
- session zones отдельно;
- swing zones отдельно.

Метрики:

- trades;
- win rate;
- profit factor;
- expectancy;
- average R;
- max drawdown;
- MFE/MAE после Stage 8;
- median hold time;
- results by zone source.

Acceptance criteria:

- видно, что добавляет каждый фильтр;
- есть таблица сравнения variants;
- фильтр не принимается только потому, что красиво выглядит на нескольких графиках;
- результаты можно повторить одним runner-командой.

## Stage 7 - Walk-Forward Calibration

Цель: проверить устойчивость параметров и не переподогнать стратегию.

Параметры для калибровки ограничить максимум пятью:

- `volume_window`;
- `spike_ratio` или `hampel_score`;
- `min_sweep_depth`;
- `zone_width`;
- `take_profit_r`.

Пример сплитов:

```text
train: 90 days
test: 30 days
step: 30 days
```

Или проще:

```text
70% in-sample
30% out-of-sample
```

Acceptance criteria:

- параметры не меняются радикально от окна к окну;
- out-of-sample не разваливается полностью;
- результаты показаны отдельно для train и test;
- если edge есть только при одном узком наборе параметров, стратегия считается неготовой.

## Stage 8 - Trade Management Improvements

Цель: улучшить управление сделкой после того, как базовый сигнал доказал полезность.

Добавить в диагностику:

- MFE;
- MAE;
- time to MFE;
- time to stop;
- R-multiple distribution;
- exit reason.

Проверить варианты управления:

- break-even shift после 1R;
- partial take profit: 50% на 1R, остаток на 2R;
- выход у противоположной sweet zone;
- выход у VWAP;
- time stop;
- session close exit;
- cooldown после убыточной сделки.

Acceptance criteria:

- trade management сравнивается поверх одного и того же entry-signal;
- улучшение не достигается за счет скрытого look-ahead;
- в `trade_records` достаточно данных, чтобы вручную разобрать плохие сделки.

## Конец базового MVP

После Stage 8 базовая OHLCV-версия должна ответить на главный вопрос:

```text
Дает ли статистическое преимущество событие:
sweet zone -> sweep -> abnormal volume -> reaction?
```

Если ответ положительный, можно переходить к расширениям. Если ответ отрицательный, расширения не спасают идею автоматически: сначала нужно понять, какой блок не работает.

## Ext-A - HTF Directional Bias Filter

Добавить фильтр старшего таймфрейма.

Варианты:

- HTF EMA stack;
- HTF price above/below VWAP;
- market structure shift;
- simple trend/range classifier.

Идея:

- long после нижнего sweep разрешен только если HTF не медвежий;
- short после верхнего sweep разрешен только если HTF не бычий;
- counter-trend сделки можно оставить отдельным variant.

Acceptance:

- сравнить symmetric MVP vs HTF-filtered MVP;
- отдельно проверить, не убивает ли HTF filter хорошие reversal-сделки.

## Ext-B - Equal Highs / Equal Lows Premium Zones

Добавить detector равных максимумов и минимумов.

Гипотеза: equal highs/lows часто содержат более плотную ликвидность, чем одиночный swing.

Пример логики:

```text
2+ swing highs within tolerance -> equal_high_zone
2+ swing lows within tolerance -> equal_low_zone
```

Параметры:

- lookback window;
- tolerance in bps or ATR fraction;
- minimum touches;
- age decay.

Equal-zone повышает `strength` sweet zone и может быть отдельным source в отчетах.

## Ext-C - Session Filter

Добавить фильтры по времени.

Проверить окна:

- Asia range build;
- London open;
- NY open;
- first hour after major session open;
- weekends vs weekdays.

Цель: понять, концентрируется ли edge в конкретных сессиях.

## Ext-D - Open Interest Ingestion

Это первое расширение, которое требует новых данных.

Нужно добавить в `data_engine/` отдельный источник open interest, например Bybit `/v5/market/open-interest`.

Новые данные:

```text
timestamp
symbol
timeframe
open_interest
```

Research features:

- `delta_oi`;
- `oi_pct_change`;
- `oi_spike`;
- OI/price regime.

Использование в стратегии:

- подтверждать, что перед sweep был рост открытого интереса;
- фильтровать ситуации, где OI не подтверждает скопление позиций;
- отдельно логировать `price_up + oi_up`, `price_down + oi_up`, `price_up + oi_down`, `price_down + oi_down`.

## Ext-E - Funding Rate Ingestion

Добавить funding как контекст перегруженности рынка.

Идея:

- extreme positive funding означает перегруженность лонгами;
- extreme negative funding означает перегруженность шортами;
- funding не является entry-сигналом, но помогает оценить сторону риска.

Пример применения:

- осторожнее с long, если funding уже экстремально положительный;
- осторожнее с short, если funding экстремально отрицательный;
- повышать confidence sweep-reversal, если sweep выбивает переполненную сторону.

## Ext-F - Real Liquidation Events

Добавить реальные события ликвидаций как подтверждение и ground truth.

Источники:

- Bybit websocket `allLiquidation.{symbol}` для realtime;
- исторический агрегированный источник, если доступен;
- Coinglass-like data, если будет выбран внешний провайдер.

Использование:

- не для первого MVP;
- для калибровки Estimated Liquidation Pressure Zones;
- для подтверждения, что sweep действительно сопровождался ликвидационным событием;
- для оценки качества zones.

## Ext-G - Estimated Liquidation Pressure Zones

Это реализация первой части PDF.

Требует Ext-D, Ext-E и желательно Ext-F.

Идея:

```text
positive delta OI
-> position cohorts
-> side probability
-> leverage grid
-> estimated liquidation levels
-> price bins
-> smoothed pressure zones
```

Входные данные:

- OHLCV;
- open interest;
- funding;
- optional long/short ratio;
- optional taker buy/sell volume;
- optional liquidation events.

Выходной объект:

```text
LiquidationPressureZone:
    symbol
    timeframe
    side: long_liq | short_liq
    price_low
    price_high
    estimated_liq_notional
    score
    confidence
    components
```

Важно: модель должна явно называться estimated. Нельзя выдавать ее за настоящую карту ликвидаций биржи.

Использование в основной стратегии:

- как отдельный source sweet zone;
- как multiplier к `strength`;
- как context feature в отчете.

## Ext-H - CVD Divergence Quality Filter

Добавить CVD или упрощенный taker-flow proxy.

Идея:

- top sweep: price делает higher high, CVD не подтверждает higher high -> bearish divergence;
- bottom sweep: price делает lower low, CVD не подтверждает lower low -> bullish divergence.

Это не обязательный фильтр для входа, а quality filter:

- повышает confidence ReactionSignal;
- может увеличивать score сетапа;
- позволяет отдельно сравнить сделки с CVD divergence и без нее.

Требования к данным:

- taker buy volume;
- taker sell volume;
- либо источник trade-level/order-flow данных.

## Ext-I - Multi-Symbol Portfolio

После BTCUSDT проверить стратегию на корзине ликвидных перпов.

Кандидаты:

- BTCUSDT;
- ETHUSDT;
- SOLUSDT;
- BNBUSDT;
- другие инструменты с достаточной историей и объемом.

Нужны portfolio-level ограничения:

- max concurrent positions;
- max exposure per symbol;
- max daily loss;
- correlated-position cap.

Цель: понять, стратегия работает как общий паттерн или только как BTC-specific fit.

## Ext-J - Market Regime Split

Разделить рынок на режимы.

Базовые режимы:

- trend;
- range;
- squeeze;
- high-volatility expansion.

Проверить разные параметры по режимам:

- zone width;
- sweep depth;
- volume threshold;
- TP multiple;
- разрешенные стороны.

Важно: regime classifier должен быть простым и look-ahead-safe.

## Risks & Pitfalls

Основные риски:

- Look-ahead bias при расчете уровней, session high/low, resample и rolling baseline.
- Один и тот же уровень может породить много сделок без state machine.
- Rolling average объема искажается прошлыми выбросами; нужен rolling median/MAD.
- Симметричный long/short без HTF bias может ловить слишком много контртрендовых сделок.
- Большой объем на пробое иногда означает continuation, а не ловушку.
- Equal highs/lows и swing levels легко переоптимизировать.
- Слишком много параметров сделает стратегию красивой только на истории.
- OI/funding/liquidations не должны смешиваться с MVP до проверки OHLCV-версии.
- Реaltime и backtest должны использовать один и тот же detector на закрытых свечах.

Guardrails:

- не больше пяти ключевых параметров на walk-forward;
- всегда сравнивать in-sample и out-of-sample;
- логировать не только сделки, но и rejected events;
- хранить причины отказа от входа;
- проверять long/short, zone source и timeframe отдельно.

## Open Questions Before Stage 1

1. Какое финальное имя Python-пакета использовать: `sweet_zone_sweep_reaction` или другое?
2. Базовая калибровка: только BTCUSDT или сразу BTCUSDT + ETHUSDT?
3. Основной режим теста: 5m base + 1m execution или сначала только 5m?
4. Какие session windows принять по умолчанию: UTC, London/NY, или кастомные Bybit-окна?
5. Какие зоны обязательны в Stage 2: только previous day high/low или сразу добавить swing high/low?

## Минимальный порядок внедрения

```text
1. VolumeAnomalyDetector
2. SweetZoneContext
3. SweepDetector
4. ReactionDetector
5. Backtest baseline
6. Incremental filter analysis
7. Walk-forward calibration
8. Trade-management diagnostics
```

После этого можно решать, стоит ли добавлять Estimated Liquidation Pressure Zones и новые источники данных.
