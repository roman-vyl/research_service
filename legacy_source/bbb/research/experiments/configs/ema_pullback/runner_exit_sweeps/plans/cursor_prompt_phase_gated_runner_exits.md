# Prompt for Cursor / coding agent

You are working in `_bbb_new_gen`, research layer only.

## Context

We tested EMA200 strict runner exits with `fees=0.0004`.

Important findings:

```text
ADX40 runner + RSI90:
  total PnL ~13.7k
  PF ~1.45
  runner trades 23
  runner exit mix: 12 RSI / 11 initial SL

ADX40 runner + EMA100/200 cross:
  total PnL ~11.4k
  PF ~1.42
  runner trades 23
  runner exit mix: 20 EMA / 3 initial SL
```

Interpretation:

```text
RSI90 captures momentum peaks.
EMA100/200 cross protects runner trades from falling back to initial SL.
```

Current problem:

```text
RSI and EMA exits are still generic always-on exit_policy signal exits.
They are not true runner-only exits.
```

## Task

Design and implement phase-gated runner-only signal/runtime exits in `exit_management`, without creating a new trade path.

Goal:

```text
After ADX/DI moves trade to runner:
  disable initial TP
  enable runner-only RSI90/10 take exit
  enable runner-only EMA100/200 protective exit
```

## Strict boundaries

- Do not touch `data_engine`.
- Do not create a second trade execution path.
- Do not move domain logic into vectorbt callbacks.
- Do not make RSI/EMA runner exits as generic always-on `exit_policy` exits in the new tests.
- Keep initial `exit_policy` as initial SL/TP owner.
- Put phase-gated runner exits into `exit_management` runtime layer.

## Proposed config shape

Use exact existing conventions where possible, but conceptually support:

```json
{
  "exit_management": {
    "mode": "managed",
    "phase_rules": [
      {
        "rule_id": "runner_5m_adx_di_40",
        "to_phase": "runner",
        "condition": {
          "component_id": "adx_di_threshold",
          "params": {
            "timeframe": "base",
            "period": 14,
            "adx_threshold": 40.0,
            "require_di_alignment": true
          }
        }
      }
    ],
    "take_management": [
      {
        "rule_id": "disable_initial_tp_at_runner_adx_40",
        "component_id": "take_profile_switch",
        "activate_when": { "phase_at_least": "runner" },
        "params": { "action": "disable_initial_tp" }
      }
    ],
    "runtime_exits": [
      {
        "rule_id": "runner_rsi90_take",
        "component_id": "phase_gated_rsi_signal_exit",
        "activate_when": { "phase_at_least": "runner" },
        "exit_kind": "take_profit",
        "params": {
          "rsi": { "timeframe": "base", "period": 14 },
          "long_exit_above": 90.0,
          "short_exit_below": 10.0,
          "confirm_bars": 1
        }
      },
      {
        "rule_id": "runner_ema100_200_protect",
        "component_id": "phase_gated_ema_cross_exit",
        "activate_when": { "phase_at_least": "runner" },
        "exit_kind": "protective_exit",
        "params": {
          "fast_ema": { "timeframe": "base", "period": 100, "source": "close" },
          "slow_ema": { "timeframe": "base", "period": 200, "source": "close" },
          "confirm_bars": 1
        }
      }
    ]
  }
}
```

## Acceptance

Add tests proving:

```text
1. RSI/EMA runner exits cannot trigger before runner.
2. RSI runner exit triggers after runner for long RSI > 90 and short RSI < 10.
3. EMA100/200 protective exit triggers after runner:
   long: EMA100 crosses below EMA200
   short: EMA100 crosses above EMA200
4. Initial TP is disabled after runner by take_profile_switch.
5. Reports expose:
   - runtime_exit_breakdown
   - runner exit mix
   - RSI exits before runner = 0
   - EMA exits before runner = 0
   - runner -> initial SL count
6. No new trade path.
```

## Minimum smoke configs after implementation

Create batch under:

```text
research/experiments/configs/ema_pullback/runner_exit_sweeps/batches/
```

with strict fee04 configs:

```text
strict initial fee04
strict ADX40 runner no-signal fee04
strict ADX40 runner-only RSI90 fee04
strict ADX40 runner-only EMA100/200 fee04
strict ADX40 runner-only RSI90 OR EMA100/200 fee04
strict ADX40 runner-only RSI90 + EMA100/200 protective fee04
```

Do not expand to relaxed until strict phase-gated behavior is verified.
