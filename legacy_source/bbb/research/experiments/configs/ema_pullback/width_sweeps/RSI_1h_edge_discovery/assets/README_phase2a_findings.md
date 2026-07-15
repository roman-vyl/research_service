# RSI 1h Edge Discovery - Phase 2A Findings

Batch: `ema200_rsi_1h_edge_phase2a_width_params_tuning_fee04`

Status: candidates 72, ok 72, failed 0, duration_sec 2181.5.

## Executive summary

Phase 2A confirms that the best width-parameter region is not arbitrary. The strongest quality ridge is `w11 + r12 + lb10/lb20`, especially `lb10`. The broad profit lane is `w9 + r12 + lb20`.

Main carry-forward candidate: `2.15 + w11/r12/lb10`, because it has the best PF in the whole batch and both long and short PF are strong. For broader profit/coverage, keep `2.45 + w9/r12/lb20` as a separate broad transition candidate.

## Top candidates by PF

| Rail | w | r | lb | Trades | PnL | PF | MaxDD | Long PF | Short PF | Bad ctx SL |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2.15 | 11 | 12 | 10 | 197 | 4 088 | 1.218 | -20.3% | 1.214 | 1.222 | 83 |
| 2.35 | 11 | 12 | 10 | 196 | 4 312 | 1.205 | -23.6% | 1.222 | 1.187 | 84 |
| 2.15 | 11 | 12 | 20 | 200 | 3 812 | 1.202 | -20.3% | 1.184 | 1.224 | 85 |
| 2.45 | 11 | 12 | 10 | 196 | 4 174 | 1.192 | -24.4% | 1.238 | 1.145 | 84 |
| 2.35 | 11 | 12 | 20 | 199 | 4 009 | 1.190 | -25.0% | 1.191 | 1.189 | 86 |
| 2.15 | 11 | 8 | 10 | 204 | 3 568 | 1.190 | -20.9% | 1.151 | 1.234 | 88 |
| 2.15 | 11 | 8 | 20 | 204 | 3 568 | 1.190 | -20.9% | 1.151 | 1.234 | 88 |
| 2.15 | 11 | 8 | 35 | 204 | 3 568 | 1.190 | -20.9% | 1.151 | 1.234 | 88 |
| 2.15 | 11 | 10 | 10 | 204 | 3 568 | 1.190 | -20.9% | 1.151 | 1.234 | 88 |
| 2.15 | 11 | 10 | 20 | 204 | 3 568 | 1.190 | -20.9% | 1.151 | 1.234 | 88 |

## Best parameter regions across rails

| w | r | lb | Avg PF | Min PF | Sum PnL | Min Long PF | Min Short PF | Sum Trades |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 11 | 12 | 10 | 1.205 | 1.192 | 12 573 | 1.214 | 1.145 | 589 |
| 11 | 12 | 20 | 1.190 | 1.178 | 11 683 | 1.184 | 1.146 | 598 |
| 11 | 8 | 10 | 1.184 | 1.175 | 11 289 | 1.151 | 1.174 | 610 |
| 11 | 8 | 20 | 1.184 | 1.175 | 11 289 | 1.151 | 1.174 | 610 |
| 11 | 8 | 35 | 1.184 | 1.175 | 11 289 | 1.151 | 1.174 | 610 |
| 11 | 10 | 10 | 1.184 | 1.175 | 11 289 | 1.151 | 1.174 | 610 |
| 11 | 10 | 20 | 1.184 | 1.175 | 11 289 | 1.151 | 1.174 | 610 |
| 11 | 10 | 35 | 1.184 | 1.175 | 11 289 | 1.151 | 1.174 | 610 |
| 11 | 14 | 35 | 1.173 | 1.166 | 9 337 | 1.242 | 1.042 | 550 |
| 11 | 14 | 20 | 1.170 | 1.159 | 8 945 | 1.232 | 1.043 | 526 |

## Decisions

- `w11/r12/lb10` becomes the main quality ridge. Across rails it has avg PF about 1.205 and every rail remains positive.

- `w9/r12/lb20` becomes the broad profit lane. It has higher total PnL across rails but lower average PF and more trades.

- `r14` is too strict for the main branch: on w9 it can collapse short-side results and total PnL; on w11 it is acceptable but inferior to r12.

- `lb10` is best for the quality ridge at w11; `lb20` is better for broad w9 profit.

- Still no RSI/ADX/runtime exits should be added until we freeze which lane is being tested.
