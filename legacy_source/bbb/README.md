# Data Engine

Минимальный фундамент проекта с историческим backfill из Phase 2.

Что умеет сейчас:
- создать SQLite базу с базовой схемой;
- проверить контракт схемы;
- показать состояние базы командой `status`;
- загрузить исторические свечи Bybit linear командой `backfill`.
- починить свечные дыры в historical window командой `fix`.

## Быстрый старт

```bash
pip install -e .[dev]
python -m data_engine status
```

Research Workbench BFF tests (`tests/test_research_api_*.py`):

```bash
pip install -e ".[dev,workbench-api]"
python -m pytest tests/test_research_api_runs.py tests/test_research_api_market.py -q
```

## Research Workbench (UI + BFF, Windows)

From repo root (after `pip install -e ".[dev,workbench-api]"` and `cd frontend && npm install`):

- **Start:** `scripts\dev-workbench.bat` — frees ports **8000** / **5173**, opens BFF + Vite in two windows. UI: http://127.0.0.1:5173/ · API docs: http://127.0.0.1:8000/docs
- **Stop:** `scripts\stop-workbench.bat`
- BFF runs **without** `--reload`; after backend changes run stop → dev again.
- Chart `Field required` on market load usually means a stale BFF on 8000 — run stop, then dev (script checks for `ema_fast` in OpenAPI).

Пример вывода:

```text
db_path: ./market.sqlite
schema_version: 1
schema_meta: 1
candles: 0
meta: 0
quarantine: 0
contract: ok
```

## Historical Backfill

Manual smoke для Phase 2:

```bash
python -m data_engine backfill --symbol BTCUSDT --tf 1h
```

Команда грузит закрытые свечи Bybit `linear` от `launchTime` инструмента до последней полностью закрытой свечи выбранного таймфрейма.

## DIM Repair (Phase 3)

```bash
python -m data_engine fix --symbol BTCUSDT --tf 1h
```

CLI-обертка строит historical window и делегирует ремонт в `fix_candles(...)`, включая preflight/postflight проверку gaps, read-only OHLC validation и freshness check последней закрытой свечи.
