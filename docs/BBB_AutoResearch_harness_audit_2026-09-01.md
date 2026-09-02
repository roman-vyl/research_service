# BBB AutoResearch — накопленный аудит harness, исследовательской логики и направлений развития

**Дата фиксации:** 2026-09-01  
**Контекст:** текущий цикл разработки и HOST smoke BBB AutoResearch v1 в `research_service`  
**Назначение документа:** сохранить в одном месте все свежие наблюдения, блокеры, подозрительные места, идеи улучшения и методологические выводы, чтобы они не потерялись после обнуления контекста беседы.

---

## 0. Короткий итог

На текущем этапе важно разделять два разных результата.

### Control-plane harness: в основном работает

Свежий HOST smoke подтвердил жизнеспособность основного механизма AutoResearch:

- внешний оператор может быть практически «тупым» запускателем;
- supervisor запускает fresh LLM worker как отдельный CLI subprocess;
- worker может быть заменяемым: Codex CLI, OpenCode/GLM и потенциально другой CLI/provider;
- planning проходит через отдельного worker;
- canonical batch execution вызывается через существующий Research execution path;
- canonical artifacts/receipt сохраняются;
- interpretation запускается отдельным fresh worker;
- invalid interpretation fail-closed отклоняется;
- retry работает;
- корректный `hard_stop` проходит валидацию;
- state/journal коммитятся;
- supervisor завершается в terminal state;
- repository mutation guard не был нарушен;
- git остался clean.

То есть **механический оркестратор уже не является основной неизвестной**.

### Research end-to-end: пока не пройден

Полноценный исследовательский smoke не дошёл даже до валидного Phase A baseline:

- worker создал не тот стартовый EMA stack;
- worker сформировал exit-rule shape, который прошёл Research config validation, но был отвергнут Strategy Engine;
- interpretation с первого раза снова ошибся в evidence/candidate reference;
- значительная часть времени ушла на навигацию по репозиторию и восстановление operational/contracts вместо торгового reasoning.

Главный текущий вывод:

> Harness уже способен надежно остановиться на проблеме. Теперь нужно сделать так, чтобы worker тратил интеллект прежде всего на исследовательскую/торговую задачу, а не на археологию интерфейсов и угадывание начальных условий.

---

# 1. Текущая архитектурная модель AutoResearch

## 1.1. Что является harness

AutoResearch следует рассматривать как два разных слоя.

### Mechanical control plane

Python supervisor отвечает за:

- загрузку durable session state;
- создание iteration;
- подготовку worker prompt;
- запуск fresh worker subprocess;
- schema validation;
- permission/mutation guard;
- исполнение canonical Research batch;
- artifact provenance;
- retries;
- state transition;
- journal append;
- resume/crash recovery;
- hard-stop/complete.

Он **не должен самостоятельно заниматься исследовательской интерпретацией**.

### LLM research worker

LLM worker отвечает за интеллектуальные задачи:

- понять текущий исследовательский вопрос;
- сформулировать гипотезу;
- выбрать следующий эксперимент;
- интерпретировать canonical metrics;
- оценить topology;
- определить, что стало известно;
- определить следующий highest-information question;
- сформировать structured result.

Принцип:

> **LLM context disposable; research state durable.**

Каждый worker может быть fresh process без памяти предыдущего разговора. Континуитет должен приходить через session state, journal и в будущем Research Knowledge Map.

---

# 2. Что показал реальный запуск через OpenCode/GLM

## 2.1. Worker brain действительно заменяем

Вместо Codex был успешно использован:

```bash
BBB_AUTORESEARCH_AGENT_COMMAND='opencode run --auto -m speshu/z-ai/glm-5.2'
```

Проба:

```bash
echo "Reply with exactly the word PONG and nothing else." \
  | opencode run --auto -m speshu/z-ai/glm-5.2
```

успешно дала `PONG`.

Это практически подтвердило ожидаемую схему:

```text
Human / external operator
        ↓
Python supervisor
        ↓
BBB_AUTORESEARCH_AGENT_COMMAND
        ↓
fresh CLI worker process
        ↓
structured output
```

То есть worker provider — инфраструктурная конфигурация harness, а не часть research semantics.

### Следствие

В зрелой версии provider должен выбираться детерминированно:

```text
worker_profile = codex
worker_profile = claude
worker_profile = opencode_glm52
worker_profile = openrouter_x
```

а не импровизироваться внешним оператором.

---

# 3. HOST smoke: фактический проход

Свежая session:

```text
ema-anchor-host-smoke-20260901181128
```

Репозиторий:

```text
branch: main
HEAD: d8c6d49f8ceb68a2813064ca7b65616caaa961b7
working tree: clean
```

Запуск:

```bash
scripts/autoresearch_run_host.sh \
  --session ema-anchor-host-smoke-20260901181128 \
  --max-iterations 3
```

С окружением:

```text
RESEARCH_ARTIFACTS_ROOT=/Users/mcroma/bbb_data/autoresearch
RESEARCH_CONFIGS_ROOT=/Users/mcroma/bbb_data/autoresearch/configs
BBB_AUTORESEARCH_RESEARCH_SERVICE_URL=http://127.0.0.1:8000
BBB_AUTORESEARCH_AGENT_COMMAND='opencode run --auto -m speshu/z-ai/glm-5.2'
```

Сервисы:

```text
Research Service    127.0.0.1:8000
Market Data Service 127.0.0.1:8080
Strategy Engine     127.0.0.1:8090
```

Health:

- Research `/health` → `{"status":"ok"}`
- Engine `/health` → `{"status":"ok","service":"strategy_engine"}`
- MDS `/health` → healthy

Фактический lifecycle:

```text
planning
  ✓

canonical batch execution
  ✓ transport/executor
  ✗ candidate execution

interpretation
  attempt 0 → rejected by supervisor
  retry 1  → accepted

iteration commit
  ✓

session
  hard_stopped

git
  clean
```

---

# 4. Блокер №1 — exit rule contract mismatch

## 4.1. Симптом

Planning worker сформировал `always_on` exits:

- `atr_stop_loss`
- `atr_take_profit`

с полями наподобие:

```text
component_id
distance.multiplier
distance.period
distance.timeframe
```

но без `instance_id`.

Research config validation сказал:

```json
{"ok": true, "errors": []}
```

Strategy Engine затем вернул:

```text
StrategyEngineVariantError:
'exit rule requires instance_id'
```

Canonical execution summary:

```text
status: completed_with_failures
completed_count: 0
failed_count: 1
candidate: naked_anchor_baseline
error: invalid_request / exit rule requires instance_id
```

## 4.2. Почему это настоящий blocker

Это не проблема quota, не ошибка внешнего агента и не transient infrastructure.

Есть воспроизводимое расхождение между двумя contract boundaries:

```text
Research validation
        считает shape допустимым
                ↓
Strategy Engine
        считает shape недопустимым
```

## 4.3. Не принимать поспешное решение

Worker предложил по смыслу:

> либо добавить `instance_id` и enforce в validator,
> либо расслабить Engine.

Но это пока **не решение**, а только варианты.

Нужно отдельно доказать:

1. Как выглядит canonical exit-rule contract сегодня.
2. Какие реальные production strategy configs уже работают.
3. Где должен появляться `instance_id`:
   - в raw strategy config;
   - в normalization layer;
   - в batch adapter;
   - внутри Engine builder;
   - или он вообще не должен требоваться на этом уровне.
4. Не является ли worker-generated config неверной формой, которую Research validator ошибочно пропускает.

### Требуемый следующий шаг

Сделать отдельный узкий contract audit:

```text
Research config schema
→ validation path
→ normalized strategy config
→ Engine request
→ Engine variant builder
→ exit rule parser
```

и только после этого менять код.

---

# 5. Блокер/шероховатость №2 — неправильный стартовый EMA stack

Во время planning worker построил:

```text
fast   EMA100
anchor EMA200
slow   EMA1000
```

Текущий ожидаемый исходный baseline для нашего EMA-anchor research:

```text
fast   EMA100
anchor EMA200
slow   EMA500
```

если пользователь явно не выбрал иной starting point.

Это важная проблема исследовательской воспроизводимости.

## 5.1. Почему worker не должен самостоятельно менять starting point

Baseline должен отвечать на вопрос:

> что происходит с **заданной исходной стратегией** до применения исследуемых структурных фильтров?

Если worker уже в Phase A сам меняет slow EMA 500 → 1000, он фактически меняет объект исследования.

Это создаёт следующие риски:

- baseline разных sessions становится несопоставим;
- дальнейшие findings могут относиться к другой стратегии;
- worker незаметно начинает parameter optimization раньше времени;
- accumulated research memory становится неоднозначной;
- пользователь не понимает, что исследуется уже другой EMA stack.

## 5.2. Нужен explicit Starting Strategy Contract

Session bootstrap должен содержать полный исходный strategy specification.

Пример концептуально:

```yaml
starting_strategy:
  strategy_id: ema_pullback
  ticker: BTCUSDT.P
  timeframe: 5m

  anchor_stack:
    fast:
      period: 100
    anchor:
      period: 200
    slow:
      period: 500

  direction: ema_anchor_stack_trend
  trigger: touch_anchor

  exits:
    measurement_horizon: ...
```

Главное правило:

> **Worker MUST preserve all starting strategy parameters unless the active research question explicitly authorizes changing them.**

Если пользователь хочет:

```text
100 / 200 / 1000
```

это допустимо, но должно быть задано оператором/сессией, а не придумано worker.

---

# 6. Очень важная торговая проблема: worker пока слишком мало думает о торговле

Это один из главных выводов свежего smoke.

В первой iteration worker значительную часть интеллектуального бюджета потратил на:

- поиск `BatchExperimentRequest`;
- поиск примеров request;
- чтение contract files;
- catalog API;
- validation API;
- восстановление формы exit spec;
- repo exploration.

В логах было видно, например:

> “Now let me find the BatchExperimentRequest contract and example batch requests.”

Это полезно для инженерного агента, но нежелательно для research worker.

## 6.1. Worker должен думать не «как вызвать систему», а «что проверить на рынке»

Нормальный research reasoning должен выглядеть ближе к:

```text
Current stage:
descriptive baseline

Starting strategy:
100/200/500 naked EMA anchor

Question:
How many opportunities does the raw setup generate?
How are opportunities distributed by long/short?
What is the basic hit-rate under neutral measurement horizons?

Experiment:
run exact baseline unchanged
```

а не:

```text
Where is BatchExperimentRequest?
What shape should exit_policy have?
What API endpoint validates config?
```

## 6.2. Инфраструктурные details должны быть заранее hidden

Research worker должен получать готовый research-facing contract:

- starting spec;
- mutable dimensions;
- exact stage;
- exact objective;
- canonical baseline;
- allowed experiment DSL;
- candidate naming rules;
- execution tool;
- evidence schema.

Он **не должен заново изучать внутренности Research Service**.

### Архитектурный принцип

> **Research worker should operate against a narrow research protocol, not against the service repository.**

---

# 7. Точка оптимизации — слишком дорогой operator bootstrap

Внешний пускающий агент потратил заметное время на выяснение:

- какой script canonical;
- нужен ли Python или `python3`;
- существует ли `.venv`;
- какие порты используются;
- какие сервисы уже подняты;
- health endpoints;
- artifacts root;
- configs root;
- worker command;
- как OpenCode принимает stdin;
- создаёт ли OpenCode untracked files;
- где лежат старые sessions.

Это нормальная работа при первой отладке, но плохая эксплуатационная поверхность.

## 7.1. Желаемый UX

В зрелой версии запуск должен быть ближе к:

```bash
./scripts/autoresearch_run_host.sh \
  --template ema_anchor \
  --worker-profile opencode-glm52
```

или вообще:

```bash
autoresearch start ema-anchor
```

А wrapper самостоятельно:

- находит project Python;
- проверяет required services;
- проверяет health;
- выбирает roots;
- выбирает worker profile;
- создаёт session;
- запускает supervisor;
- печатает session_id.

## 7.2. Запускающий агент не должен изучать BBB

Оператору достаточно задачи:

> Запусти новую EMA AutoResearch session с worker profile X. Сообщи PASS или первый genuine failure.

Контекст Strategy Engine/Research architecture ему не нужен, если запуск уже детерминирован.

---

# 8. Точка оптимизации — wrapper зависит от shell state

Первая попытка:

```text
scripts/autoresearch_run_host.sh: line 21:
exec: python: not found
```

На машине:

```text
/usr/bin/python3
Python 3.9.6

repo:
.venv/bin/python
Python 3.12.13
```

После:

```bash
source .venv/bin/activate
```

wrapper заработал.

## 8.1. Почему это плохо

Canonical host launcher не должен молча рассчитывать на то, что оператор заранее активировал virtualenv.

Это приводит к:

- лишней диагностике;
- разным Python versions;
- случайному запуску системным Python;
- более сложным prompts для внешнего оператора.

## 8.2. Возможные варианты

Предпочтительно:

```bash
PROJECT_ROOT/.venv/bin/python ...
```

если repo-local `.venv` является canonical.

Либо fail-fast:

```text
AutoResearch host launcher requires project venv.
Run:
source .venv/bin/activate
```

Но первый вариант намного лучше для unattended/autonomous запуска.

---

# 9. `/tmp` — не defect harness, но показатель лишней импровизации

Внешний оператор записал:

```bash
echo "$SID" > /tmp/bbb_smoke_sid.txt
```

OpenCode затем запросил access к внешней директории `/tmp`.

Пользователь правильно остановил это:

> «Не используй /tmp. Это не требуется для HOST smoke. Получай session_id из созданной session под var/autoresearch или держи его в shell variable.»

## Вывод

Это не ошибка AutoResearch.

Это:

```text
operator improvisation
```

Но она показывает, что operator surface можно сделать удобнее:

- init должен ясно печатать session id;
- launcher может сам создавать session;
- session id можно возвращать machine-readable;
- не должно требоваться внешнее scratch storage.

---

# 10. Повторяющийся defect/ambiguity — unknown current candidate

Первый interpretation попытался записать research quality assessment, но supervisor отверг результат:

```text
invalid interpretation result:
invalid research quality assessment:
canonical evidence references an unknown current candidate
```

Retry 1 затем прошёл.

## 10.1. Хорошая новость

Fail-closed validator работает.

Worker не смог записать некорректную ссылку в durable state.

Retry mechanism тоже работает.

## 10.2. Плохая новость

Ошибка повторилась уже как минимум в нескольких smoke sessions.

Это значит, что contract может быть формально правильным, но **недостаточно эргономичным для LLM**.

Worker должен буквально знать:

```text
These are the only valid current candidate IDs:
- naked_anchor_baseline
```

и при evidence ref не генерировать идентификатор самостоятельно.

## 10.3. Возможное улучшение

В interpretation prompt давать machine-generated section:

```text
CURRENT_CANONICAL_CANDIDATES

candidate_id: naked_anchor_baseline
status: failed
run_id: null
```

И отдельное правило:

> candidate_id in canonical evidence references MUST be copied byte-for-byte from CURRENT_CANONICAL_CANDIDATES. Never derive or rename it.

Можно также подумать, нужен ли вообще `candidate_id` для certain infrastructure hard-stop evidence, если evidence относится к batch-level failure.

Но это уже contract decision и требует просмотра текущего OpenSpec.

---

# 11. Ранее найденная evidence ambiguity: `analysis_artifact`

До текущего smoke была отдельная проблема:

worker ссылался на supervisor-owned files вроде:

```text
execution_output.json
canonical_request.json
receipt
```

как на:

```text
analysis_artifact
```

Validator требовал:

```text
analysis_artifact.analysis_path
==
execution_result.analysis_path
```

и корректно отклонял result.

Правильная семантика:

- `analysis_artifact` — только worker-authored retained analysis file;
- canonical executor/supervisor files — не analysis artifacts;
- данные из canonical files должны ссылаться через `canonical_metric` / canonical evidence ref.

Полезная формулировка для worker cheat-sheet:

> For `analysis_artifact`, `analysis_path` MUST exactly equal `execution_result.analysis_path`. Never cite supervisor-owned canonical executor files (`execution_output.json`, `canonical_request.json`, `receipt`) as `analysis_artifact`; reference their data through canonical evidence references.

Это уже показало, насколько важен отдельный компактный EvidenceRef guide.

---

# 12. Старое возможное противоречие в failure classification

В предыдущей session оператор сначала увидел:

```text
planning + batch execution succeeded
```

и interpretation failure:

```text
canonical evidence references an unknown current candidate
```

Позже он сформулировал:

> “The prior batch genuinely failed at the Strategy Engine boundary...”

Эти утверждения не обязательно противоречат друг другу.

Batch execution может завершиться транспортно/canonically и при этом содержать:

```text
candidate status = failed
```

То есть важно различать:

```text
executor transport success
batch artifact success
candidate execution success
research experiment success
```

## Улучшение терминологии

В логах и final status желательно явно разделять:

```text
executor_status
batch_status
candidate_status
iteration_status
session_status
```

чтобы фраза:

> “batch execution ✓”

не воспринималась как:

> “research candidate successfully backtested”.

---

# 13. Время iteration и интеллектуальная эффективность

Свежий smoke занял примерно 10+ минут до terminal hard-stop.

При этом полноценный backtest не состоялся.

Большая доля времени ушла на:

- repo inspection;
- planning navigation;
- contract discovery;
- interpretation retry.

Поскольку compute backtests в нашем случае не является главным bottleneck, оптимизировать надо прежде всего **LLM cognitive overhead**.

## Цель

Не:

```text
сделать на 30 секунд быстрее
```

а:

```text
увеличить долю worker reasoning,
которая посвящена исследовательскому вопросу.
```

---

# 14. Методологическая основа EMA research

Главный принцип:

> **EMA anchor research = search for robust market states around touch, not search for an optimal set of numbers.**

Параметр — proxy рыночного состояния, а не самоцель оптимизации.

Следствия:

- hypothesis-first;
- topology > max;
- ridge/plateau > isolated optimum;
- side decomposition обязательна;
- границы диапазона должны считаться resolved/unresolved;
- thinning/sample concentration контролируются;
- `NO_STABLE_EDGE` — валидный научный результат;
- не вводить magic weighted score;
- не превращать AutoResearch в PF leaderboard;
- не гонять multi-param optimization без исследовательской причины.

---

# 15. Фазовые semantics должны быть явными

Одна из двух сильных идей, извлечённых из вебинара и последующего обсуждения:

> **успех эксперимента и смысл метрик должны зависеть от исследовательской фазы.**

Не должно существовать одного глобального критерия вроде:

```text
PF выше → эксперимент лучше
```

## Phase A — descriptive baseline

Цель:

- понять количество opportunities;
- long/short distribution;
- basic behavior naked setup;
- получить reference point.

Основная формулировка:

> **Phase A metrics are descriptive baseline facts, not optimization targets.**

PF/PnL/DD можно записывать, но worker не должен оптимизировать baseline.

## Phase B — structural entry discovery

Цель:

- найти рыночные состояния, в которых вход структурно лучше;
- сравнивать с naked/parent baseline;
- смотреть response topology;
- измерять uplift при neutral/symmetric measurement geometry.

Основные evidence:

- win rate / profitable trades;
- uplift относительно baseline;
- trade count;
- thinning;
- long/short WR;
- neighborhood stability;
- ridge/plateau/boundaries.

PF/PnL/DD здесь secondary sanity/context, а не final promotion gate.

Пример:

```text
55% WR на 600 trades в широком plateau
```

может быть сильнее:

```text
72% WR на 18 trades в isolated point.
```

## Phase C — execution geometry

После выбора структурной области появляются реалистичные asymmetric TP:SL.

Здесь уже становятся primary:

- after-cost PnL/return;
- PF;
- DD;
- payoff;
- trade count;
- long/short profitability;
- neighboring exit stability.

Только здесь торговая economics начинает быть главным критерием.

## Robustness / promotion

Дальше:

- perturbation;
- side robustness;
- regime concentration;
- independent time cuts;
- ticker/window variation where justified.

---

# 16. Phase B нельзя жёстко сводить к одному symmetric exit

В нашем исследовании использовались:

```text
2/2
3/3
4/4
```

как diagnostic measurement horizons.

Это не обязательно три «торговые exit strategies».

Они могут использоваться, чтобы понять:

> какой horizon достаточно длинный, чтобы structural effect проявился.

Правильная формулировка:

- допустимо сравнить несколько symmetric horizons;
- после выбора neutral horizon держать geometry fixed для structural comparison;
- не оптимизировать TP/SL внутри Phase B.

---

# 17. Уже известные EMA research факты, которые future worker должен получать как knowledge, а не открывать заново

Phase A historical window:

```text
2021-11-01T00:00Z
→
2022-11-01T00:00Z

105,120 bars @ 5m
```

Важно:

> Этот interval заканчивается до FTX collapse 6–11 ноября 2022. Нельзя говорить, что baseline включает FTX collapse.

Исходный baseline:

```text
EMA fast   100
EMA anchor 200
EMA slow   500

direction: stack trend
trigger: touch_anchor
ATR14
symmetric 2/2
fees: 4 bp each side
initial equity: 1,000,000
quantity: 1
```

Результат:

```text
trades: 1242

gross: -1291.5
fees: 34681.5
net: -35973

PF: 0.706
WR: 50.7%
DD: 3.71%

long:
  n 564
  gross -2304
  PF .657
  WR 49.8%

short:
  n 678
  gross +1012.7
  PF .743
  WR 51.5%
```

Корректная интерпретация:

> near-flat/slightly negative BEFORE costs, strongly negative AFTER costs.

Не:

> стратегия «ужасно проигрывает» raw edge.

Значительная отрицательная net economics происходит из-за transaction costs.

---

# 18. Уже найденная width topology

Right-tail width исследован по нескольким symmetric horizons.

Данные:

| Width | 2/2 n/PF | 3/3 n/PF | 4/4 n/PF |
|---:|---:|---:|---:|
| 4 | 522 / .768 | 522 / .768 | 398 / .839 |
| 5 | 580 / .697 | 420 / .787 | 318 / .859 |
| 6 | 452 / .734 | 329 / .806 | 263 / 1.026 |
| 7 | 356 / .774 | 257 / .761 | 209 / 1.044 |
| 8 | 276 / .668 | 201 / .751 | 162 / .893 |
| 10 | 156 / .532 | 117 / .790 | 100 / 1.025 |
| 12 | 101 / .318 | 79 / .475 | 64 / .547 |
| 15 | 46 / .317 | 40 / .498 | 36 / .636 |

Controls:

```text
.706 / .806 / .803
```

Текущее знание:

- region 6–7 наиболее интересный при более длинном measurement horizon;
- после 8 начинается deterioration;
- 12–15 становится sparse/unreliable;
- right boundary достаточно исследован;
- нет смысла снова бесконечно расширять вправо без новой гипотезы;
- эффект преимущественно short-side;
- long PF остаётся примерно 0.67–0.84;
- width effect усиливается при более длинном horizon.

Это идеальный пример информации, которую future Research Knowledge Map должен подавать fresh worker в сжатом виде.

---

# 19. Lookback research

Для untouched lookback:

```text
10 .. 100
step 5
```

была обнаружена nested structure:

- larger lookback фильтрует subset trades меньшего lookback;
- retained-vs-filtered analysis показал, что отбрасываемые trades экономически слабее;
- strict nested sets;
- явной directional/coarse temporal concentration не обнаружено.

Но:

- sample uncertainty остаётся;
- нельзя утверждать, что «thinning disproved».

При symmetric exit 4/4 положительная-ish область:

```text
lookback ~65–100
landmark around ~70
```

Но это **landmark, а не optimum**.

---

# 20. Bounce parameter пока исключён

Несмотря на существование `ema_bounce_counter_setup`, пользователь ранее явно сказал bounce пока не брать.

Следовательно future worker не должен внезапно включать:

```text
max_bounces
bounce count
bounce interaction
```

без reopening research scope.

Это ещё один аргумент за explicit mutable-dimensions contract в session.

---

# 21. Width semantic audit остаётся важным

Есть потенциально важное различие старого BBB и текущего implementation:

старое значение width порядка `~2 ATR` могло быть нормализовано относительно **1h ATR**, тогда как текущая реализация, вероятно, использует **5m ATR**.

По приблизительной оценке старый масштаб может соответствовать:

```text
~15–25 ATR_5m
```

но фиксированного коэффициента пересчёта нет.

Нужен отдельный read-only semantic audit:

- точная formula;
- timeframe ATR;
- `min_current`;
- `min_recent`;
- `width_lookback`;
- defaults;
- pass-rate;
- distribution;
- old BBB parity.

Не смешивать этот audit с новым optimization run.

---

# 22. Идея из вебинара №1 — phase-specific success semantics

Это уже описано выше, но важно зафиксировать отдельно как направление будущей доработки.

Текущая chain:

```text
stage
→ metric roles
→ interpretation
```

может эволюционировать в:

```text
stage
→ research objective
→ primary evidence
→ secondary evidence
→ common failure modes
→ promotion condition
→ next-stage handoff
```

Пример для Phase B:

```text
Output:
stable structural region
or NO_STABLE_EDGE

NOT:
winning tuple
```

Handoff в Phase C:

```text
“structural region supported for execution-geometry research”
```

а не:

```text
“width=6 won”
```

---

# 23. Идея из вебинара №2 — Research Knowledge Map / долговременная научная память

Это второй крупный deferred direction.

Нужно разделить три слоя.

## Layer 1 — canonical evidence

Immutable truth:

- requests;
- results;
- metrics;
- configs;
- hashes;
- artifacts.

## Layer 2 — chronological research journal

Что происходило:

```text
iteration 1
iteration 2
...
```

## Layer 3 — Research Knowledge Map

Что **уже известно**.

Пример структуры:

```yaml
finding:
  id: width_right_tail_v1
  stage: structural_entry_discovery
  scope:
    ticker: BTCUSDT.P
    timeframe: 5m

  tested_space:
    width: [4, 5, 6, 7, 8, 10, 12, 15]
    horizons: ["2/2", "3/3", "4/4"]

  topology:
    favorable_region: [6, 7]
    deterioration_after: 8
    right_boundary_resolved_to: 15

  sample:
    sparse_from: 12

  side_structure:
    classification: short_dominant

  conclusion:
    status: supported
```

## 23.1. Coverage map

Worker должен знать:

```text
width right-tail:
  resolved

lookback:
  favorable zone known
  interaction unresolved

width × lookback:
  untested
```

Тогда следующий worker не повторяет исследованное пространство.

## 23.2. Negative results обязательны

Research memory должна хранить не только успешные findings.

Например:

```text
ADX blocker did not show stable improvement
```

должно остаться, чтобы fresh worker не «изобрёл» тот же experiment через 50 iterations.

## 23.3. Reopening требует rationale

Если исследованное направление открывается снова:

```text
reopen_reason:
new timeframe semantics discovered
```

а не просто потому, что новый worker забыл историю.

## 23.4. Supersession вместо destructive overwrite

Пример:

```text
finding_017
SUPPORTED

finding_041
SUPERSEDES finding_017
```

Так сохраняется история научного развития.

---

# 24. Что НЕ брать из webinar adaptation

Из trading AutoResearch adaptations полезна общая архитектура:

```text
program
worker
runner
evaluator
history
```

Но не стоит копировать следующие практики.

## Не делать scalar champion

Не превращать research в:

```text
Sharpe leaderboard
PF leaderboard
PnL leaderboard
```

## Не давать worker менять evaluator

Immutable judge:

```text
MDS
Strategy Engine
Research execution
accounting
```

Worker не должен иметь возможность «улучшить стратегию» изменив способ оценки.

## Не делать uncontrolled hyperparameter search

50 параметров × тысячи random combinations ≠ scientific research.

## Не вводить новые indicators ad hoc

Новый component/indicator должен появляться только как осознанная исследовательская гипотеза и через нормальный development contract.

---

# 25. Идея из webinar, которую пользователь НЕ принял

Progressive small-window screening:

```text
90d
120d
6m
...
```

не подходит нам как compute-saving mechanism.

Причина:

- compute не является серьёзной проблемой;
- большой market sample важен;
- нет смысла жертвовать статистической информацией ради экономии дешёвого расчёта.

Следовательно:

> Не предлагать короткие окна только ради ускорения AutoResearch.

Позже можно использовать независимые time/regime slices **для robustness**, но это другая цель.

---

# 26. Нужен explicit Research Context Pack

Fresh worker не должен получать огромный repo context.

Он должен получать сжатый пакет.

Пример:

```yaml
research_program:
  objective: discover robust EMA-anchor market states

stage:
  kind: structural_entry_discovery
  objective: improve entry selectivity, not final economics

starting_strategy:
  fast_ema: 100
  anchor_ema: 200
  slow_ema: 500

immutable_dimensions:
  ticker: BTCUSDT.P
  timeframe: 5m

allowed_mutations:
  - untouched_anchor_lookback
  - anchor_stack_width

forbidden_now:
  - bounce_counter
  - new indicators
  - managed exits
  - evaluator changes

known_findings:
  - width favorable ridge around 6–7 under longer neutral horizon
  - right boundary deterioration after 8
  - effect short-dominant

open_questions:
  - width × lookback interaction

current_baseline:
  ...

evidence_contract:
  ...

output_schema:
  ...
```

Так worker начинает с trading question, а не с чтения 30 файлов.

---

# 27. Разделение ролей агентов

## External launch/operator agent

Должен знать минимум:

```text
repo path
canonical launch command
worker profile
when to stop/report
```

Не должен знать:

- I0–I8;
- internal Engine implementation;
- весь Research architecture;
- методологию EMA в деталях.

## Research worker

Должен знать:

- research program;
- active phase;
- starting strategy;
- allowed dimensions;
- current knowledge;
- evidence contract.

Не должен изучать production repo.

## Engineering/debug agent

Только этот агент должен читать:

- supervisor code;
- contracts;
- OpenSpec;
- Engine/Research implementation;
- tests.

Сейчас большой bootstrap prompt нужен именно потому, что harness ещё отлаживается.

---

# 28. Worker provider configuration

Provider должен быть частью deterministic config.

Нежелательно:

```text
external LLM operator decides which agent to spawn
```

Желательно:

```yaml
worker_profile: opencode_glm52
```

или:

```bash
autoresearch start ... --worker-profile opencode-glm52
```

Profile может содержать:

```yaml
command:
  - opencode
  - run
  - --auto
  - -m
  - speshu/z-ai/glm-5.2

prompt_transport: stdin
```

Это позволит без изменения research semantics переключать:

- Codex;
- Claude;
- GLM;
- OpenRouter-backed CLI.

---

# 29. External provider quota/capacity

Предыдущий Codex smoke получил:

```text
You've hit your session limit
```

Это не defect AutoResearch.

Но зрелый supervisor потенциально может классифицировать:

```text
agent_capacity_unavailable
```

отдельно от:

```text
invalid_worker_output
```

и сохранять resumability.

Не является текущим приоритетом, но направление разумное.

---

# 30. Harness должен различать infrastructure failure и research finding

Свежий worker корректно написал hard stop:

> “This is an infrastructure/contract failure, not a research finding.”

Это очень правильная семантика.

Если:

```text
completed_count = 0
metrics = null
```

worker не должен делать выводы:

```text
strategy bad
baseline unprofitable
edge absent
```

Нужно жёстко сохранять distinction:

```text
NO_DATA
EXECUTION_FAILURE
CONTRACT_FAILURE
NO_STABLE_EDGE
NEGATIVE_ECONOMICS
```

Это совершенно разные научные состояния.

---

# 31. Current smoke status нужно формулировать двухуровнево

Фраза просто:

```text
FAIL
```

слишком грубая.

Лучше:

### Harness control-plane smoke

```text
PASS
```

Потому что:

- fresh worker launch работает;
- planning работает;
- execution adapter работает;
- artifacts работают;
- interpretation работает;
- validation/retry работают;
- terminal state работает;
- durable state/journal работают.

### Research E2E smoke

```text
FAIL / BLOCKED
```

Потому что:

- валидный baseline candidate не был рассчитан;
- contract mismatch остановил research.

---

# 32. Потенциальный roadmap после текущего blocker

Не делать всё сразу. Разделить.

## Шаг 1 — contract blocker

Разобрать:

```text
exit rule requires instance_id
```

минимально.

## Шаг 2 — повторный HOST smoke

Тот же baseline.

Цель:

```text
валидный Phase A baseline
→ metrics
→ interpretation
→ next iteration
```

## Шаг 3 — operational polish

- wrapper / `.venv`;
- worker profile config;
- automatic health checks;
- session creation;
- operator UX.

## Шаг 4 — research bootstrap contract

- explicit starting strategy;
- immutable/mutable dimensions;
- canonical baseline;
- no implicit EMA changes.

## Шаг 5 — worker cognitive surface

Сократить repo archaeology.

## Шаг 6 — quality semantics extension

Phase-specific objective/evidence/promotion/handoff.

## Шаг 7 — Research Knowledge Map

Durable scientific memory.

---

# 33. Что считать подозрительным при следующих smoke

Ниже checklist для наблюдения.

## Operator layer

Подозрительно, если внешний агент:

- читает десятки production files перед запуском;
- угадывает ports;
- угадывает roots;
- создаёт scratch files вне repo;
- сам выбирает provider без explicit request;
- редактирует code во время smoke.

## Planning worker

Подозрительно, если worker:

- сам меняет EMA periods;
- сам включает bounce;
- начинает оптимизировать exits в Phase B;
- ищет random hyperparameter combinations;
- читает большую часть repo;
- меняет evaluator;
- строит strategy с параметрами вне allowed space;
- не использует baseline exactly.

## Execution

Подозрительно:

- validator says valid but Engine says invalid;
- transport success маскируется под candidate success;
- metrics отсутствуют, но interpretation делает trading conclusions.

## Interpretation

Подозрительно:

- candidate IDs придумываются;
- supervisor-owned files помечаются `analysis_artifact`;
- PF/PnL оптимизируются в Phase A/B;
- high WR tiny-N объявляется победителем;
- one-side edge называется universal;
- isolated spike называется optimum;
- losing but informative experiment выбрасывается как useless.

---

# 34. Главный принцип будущей доработки

AutoResearch не должен превращаться в:

> «LLM, который крутит параметры стратегии».

Он должен стать:

> **автономным научным исследователем, которому harness предоставляет неизменный способ измерения рынка, durable память и строгие границы допустимого эксперимента.**

Механический supervisor должен делать систему безопасной и воспроизводимой.

LLM должен использовать большую часть своего интеллекта на:

- market hypothesis;
- structural interpretation;
- topology;
- side asymmetry;
- causal sequencing;
- uncertainty;
- highest-information next question.

И как можно меньше — на:

- поиск Python interpreter;
- API payload shape;
- порт 8090;
- schema archaeology;
- угадывание starting EMA.

---

# 35. Ключевые формулировки, которые стоит сохранить буквально

> **LLM context disposable; research state durable.**

> **EMA anchor research = search for robust market states around touch, not search for an optimal set of numbers.**

> **Phase A metrics are descriptive baseline facts, not optimization targets.**

> **Topology > maximum.**

> **A broad stable region with meaningful sample can be stronger evidence than an isolated high metric point.**

> **Research worker should operate against a narrow research protocol, not against the service repository.**

> **Experiment history records what happened. Research memory records what has been learned.**

> **Worker MUST preserve all starting strategy parameters unless the active research question explicitly authorizes changing them.**

---

# 36. Текущие приоритеты

На момент фиксации порядок выглядит так:

1. **Не менять methodology прямо сейчас.**
2. Разобрать `exit rule requires instance_id`.
3. Сделать minimal proven fix.
4. Повторить HOST smoke.
5. Добиться валидного Phase A baseline.
6. После зелёного smoke отдельно пройтись по накопленному списку operational/harness improvements.
7. Затем развить:
   - phase-specific research success semantics;
   - Research Knowledge Map.

---

# 37. Итоговая оценка состояния

AutoResearch уже прошёл важный рубеж:

раньше главный вопрос был:

> «Сможет ли вообще Python supervisor автономно запускать LLM, исполнять experiment и поддерживать состояние?»

Свежий smoke показывает:

> **да, сможет и уже делает это.**

Теперь центр проблемы сместился.

Следующий уровень качества:

> **можем ли мы сделать research contract настолько хорошим, чтобы свежий worker сразу думал о рынке, а не о программной инфраструктуре, и при этом не мог незаметно изменить сам объект исследования?**

Именно здесь сейчас находится наиболее ценная дальнейшая работа.

---

# 38. Future polishing — Research-intent compilation вместо ручной сериализации strategy spec

Это deferred orchestration/context-efficiency improvement, а не prerequisite текущей Stage
Contract работы.

Fresh-worker архитектура должна сохраниться:

```text
planning LLM
→ deterministic supervisor/executor
→ interpretation LLM
→ durable state/journal
→ next fresh planning LLM
```

Нельзя превращать эти вызовы в один долгоживущий LLM context. Disposable context и durable
research state остаются важной границей воспроизводимости.

Сейчас planning worker всё ещё расходует часть context window и reasoning budget на механическую
работу: формирует полный canonical `BatchExperimentRequest` и вручную сериализует полные candidate
strategy specifications. Это работа с низкой исследовательской ценностью, которую в будущем следует
скомпилировать детерминированно.

Целевая ownership boundary:

> **LLM chooses the research action; supervisor compiles it into the executable experiment.**

## 38.1. Что остаётся за planning LLM

Planning LLM формулирует:

- исследовательскую гипотезу;
- следующий discriminating question;
- разрешённую semantic dimension;
- значения или диапазон, которые следует проверить;
- rationale и ожидаемую information value.

Например, обычный B1 planning result должен уметь выразить research intent и выбранные width values,
не сериализуя полный `raw_spec` каждого кандидата.

## 38.2. Что детерминированно компилирует supervisor

Supervisor должен:

- взять immutable starting/reference strategy из session state;
- разрешить approved typed semantic binding;
- применить только разрешённые mutation values;
- сохранить ticker, timeframe, EMA stack, trigger, component IDs, instance IDs, fixed parameters,
  exits и все остальные immutable поля;
- обеспечить matched A↔B geometry;
- обеспечить naked reset для B2;
- построить deterministic candidate strategies;
- сформировать полный canonical `BatchExperimentRequest`;
- провести существующую validation → freeze → brokered execution цепочку.

Это не новый evaluator и не дополнительный LLM role. Если операция детерминирована, её должен
выполнять код, а не отдельный агент «для подготовки specification».

## 38.3. Узкая граница, не generic mutation framework

Будущий compiler должен опираться на существующие Stage Contract и typed semantic dimensions.

Не вводить:

- JSONPath;
- JSON Pointer;
- arbitrary patch language;
- универсальный strategy editor;
- generic mutation DSL.

Strategy Engine сохраняет ownership raw-spec semantics. Strategy Specification Reference остаётся
conceptual/navigation reference, но worker больше не использует его как руководство по ручной
сериализации полного candidate `raw_spec`.

## 38.4. Зачем это нужно

Главная цель — освободить LLM context window и reasoning budget для:

- исследования торговой стратегии;
- response topology;
- sample thinning;
- long/short behavior;
- competing explanations;
- выбора следующего наиболее информативного эксперимента.

LLM не должна повторно тратить этот бюджет на JSON structure и механическое копирование immutable
strategy fields.

## 38.5. Порядок выполнения

Эта полировка выполняется только после:

1. завершения текущей Stage Contract полировки;
2. успешного controlled HOST smoke A → B1 → B2 → optional B3;
3. доказательства работоспособности существующего harness;
4. отдельного согласования orchestration/context-efficiency refactor.

Refactor не должен менять:

- Research evaluator semantics;
- Strategy Engine ownership of raw-spec semantics;
- MDS;
- accounting;
- canonical batch artifacts;
- evidence provenance;
- brokered execution;
- fail-closed supervisor model;
- fresh-worker architecture.

Acceptance direction:

> Обычная B1 iteration принимает от planning LLM только research intent и выбранные width values,
> после чего supervisor детерминированно строит полный canonical multi-candidate
> `BatchExperimentRequest` без ручной сериализации strategy specs со стороны LLM.

---

# 39. Future polishing — human-authored research brief как вход в постановку задачи

В дополнение к typed session/template controls следует рассмотреть operator-authored research brief:
человек передаёт AutoResearch отдельный `.txt` или `.md` файл со свободным описанием того, что
нужно исследовать.

Пример содержания:

```text
Исследуй EMA-anchor setup с EMA100/EMA200/EMA500.
Сначала измерь заданные symmetric horizons.
Затем независимо проверь width и untouched lookback.
Особенно проверь thinning и long/short asymmetry.
Не добавляй новые indicators и не переходи к exit optimization.
```

Этот brief читается planning LLM в момент постановки исходной research task, до выбора первого
эксперимента. Он может содержать:

- человеческую формулировку исследовательской цели;
- выбранную EMA или starting strategy family;
- интересующие параметры и вопросы;
- дополнительные методологические акценты;
- явно запрещённые направления;
- ожидаемый scope исследования.

## 39.1. Brief не заменяет механические контракты

Свободный текст задаёт intent, но не становится authority для исполнения. Immutable starting
strategy, Stage Contract, typed semantic dimensions, measurement geometries и supervisor validation
остаются нормативными и fail-closed.

Если brief противоречит session contract, LLM не получает дополнительного mutation authority:
она должна сообщить о конфликте или сформулировать действие в разрешённом space.

## 39.2. Brief должен быть frozen session input

Для воспроизводимости выбранный brief следует рассматривать как immutable input конкретной session:

- сохранить исходное содержимое или resolved copy;
- связать его hash с bootstrap/state provenance;
- передавать его fresh planning worker вместе с compact Research Context Pack;
- не использовать изменяемый внешний файл как неявную память активной session.

Точная contract/schema форма требует отдельного будущего проектирования. Не реализовывать её в
рамках текущей Stage Contract работы.

## 39.3. Связь с research-intent compilation

Human brief отвечает на вопрос:

```text
Что человек хочет исследовать?
```

Planning LLM преобразует это вместе с durable state в следующий научно осмысленный research intent:

```text
Какой следующий разрешённый эксперимент даст максимум информации?
```

Supervisor затем компилирует этот structured intent в canonical executable request:

```text
Как детерминированно и без изменения immutable controls выполнить этот эксперимент?
```

Такой pipeline сохраняет исследовательскую свободу LLM, но убирает из её работы повторяющуюся
ручную сериализацию strategy specification.


