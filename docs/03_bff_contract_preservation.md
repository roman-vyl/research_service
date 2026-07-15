# BFF contract preservation

## Browser ownership rule

Research Workbench communicates only with Research Service. Direct browser calls to Strategy Engine or Market Data Service are forbidden.

## Existing routes to preserve initially

### Research runs

- `GET /api/research/runs`
- `GET /api/research/runs/latest`
- `GET /api/research/runs/{run_id}`
- `GET /api/research/runs/{run_id}/summary`
- `GET /api/research/runs/{run_id}/signal-trace`
- `GET /api/research/runs/{run_id}/chart-events`

### Backtests/configuration

- `POST /api/research/backtests`
- `GET /api/research/component-catalog`
- `POST /api/research/config/validate`
- `POST /api/research/config/serialize`
- `POST /api/research/config/save`
- `GET /api/research/configs/state`
- `PUT /api/research/configs/selected`

### Market/chart

- `GET /api/market/candles-window`
- `GET /api/market/ema-window`
- `GET /api/market/chart-bundle` during compatibility period
- `GET /api/market/candles`
- `GET /api/market/indicators/ema`

## Adapter principle

External DTOs may remain identical while internal sources change:

```text
Workbench DTO
<- Research Service mapper
<- Strategy Engine / MDS / artifact store
```

No Strategy Engine response model is exposed directly to TypeScript. This prevents backend decomposition from forcing a frontend rewrite.

## Frontend API base

The existing `VITE_API_BASE_URL` remains the single browser backend setting.
