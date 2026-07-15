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
