# Next phase plan — phase-gated runner exits

## Why this phase is needed

The current experiments produced a strong insight, but the current implementation is not clean enough to prove the combined exit idea.

Current state:

```text
RSI and EMA signal exits are always-on exit_policy exits.
They can trigger before runner.
```

Target state:

```text
RSI and EMA runner exits should be active only after runner phase is reached.
```

This is required to test the actual idea:

```text
Once ADX/DI proves the trade is a runner,
switch from fixed TP/initial SL to a runner-specific exit stack.
```

## Target trading semantics

Before runner:

```text
active:
  initial SL
  initial TP

inactive:
  runner RSI exit
  runner EMA cross exit
```

After runner:

```text
active:
  runner RSI90/10 take exit
  runner EMA100/200 protective exit

disabled:
  initial TP

question to decide:
  keep initial SL as catastrophic fallback
  or replace/suppress it behind EMA100/200 protective exit
```

## Key design choice

There are two possible models.

### Model A — additive runner exits

After runner:

```text
initial SL remains active
initial TP disabled
RSI90/10 active
EMA100/200 active
```

Exit priority:

```text
initial SL
EMA100/200 protective exit
RSI90/10 take exit
```

Pros:

```text
safe, minimal semantic change
```

Cons:

```text
initial SL can still be hit before EMA exit in some paths
```

### Model B — replace initial SL with EMA protective exit

After runner:

```text
initial TP disabled
initial SL disabled or demoted to catastrophic fallback
EMA100/200 cross becomes the main protective exit
RSI90/10 remains take/exhaustion exit
```

Pros:

```text
tests the user's key hypothesis directly:
EMA cross protects runner trades instead of letting them fall to initial SL
```

Cons:

```text
riskier and requires precise priority/fallback rules
```

Recommended implementation order:

```text
Step 1: Model A first.
Step 2: Model B second, only after Model A validates the combined signal.
```

## Required runtime contract

Add runner-only managed signal/runtime exits under `exit_management`, not under generic `exit_policy`.

Example target config shape:

```json
{
  "trade_management": {
    "exit_policy": {
      "always_on": {
        "exits": [
          { "component_id": "atr_stop_loss", "instance_id": "sl_6p0atr" },
          { "component_id": "atr_take_profit", "instance_id": "initial_tp_14p0atr" }
        ]
      }
    },
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
}
```

Exact field names can be adjusted to match existing runtime conventions, but the ownership must stay:

```text
exit_management owns phase-gated runner exits.
exit_policy remains initial risk/ordinary fixed exits.
```

## Acceptance criteria

### Architecture

- No new trade path.
- No vectorbt callback domain logic.
- No changes in `data_engine`.
- No generic always-on RSI/EMA signal in the tested runner-only configs.
- Phase-gated exits live in managed runtime / exit_management.
- `trade_records[].trade_management.managed_events` records:
  - phase_changed
  - active_take_updated
  - runtime_exit_triggered
  - runtime_exit_executed
  - component_id
  - rule_id
  - phase
  - side
  - MFE/MAE at trigger
  - bars_in_trade

### Diagnostics

Reports must show:

```text
RSI exits before runner = 0
EMA exits before runner = 0
runner-only RSI exits count
runner-only EMA exits count
runner -> initial SL count
runner -> catastrophic SL count if fallback remains
runner capture summary
runner giveback summary
```

### Trading comparison

Minimum test matrix:

```text
strict initial fee04
strict ADX40 runner no-signal fee04
strict ADX40 runner-only RSI90 fee04
strict ADX40 runner-only EMA100/200 fee04
strict ADX40 runner-only RSI90 OR EMA100/200 fee04
strict ADX40 runner-only RSI90 + EMA100/200 protective fee04
```

Optional after strict:

```text
strict ADX45 variants
relaxed ADX40/45 variants only after missing relaxed reports are complete
```

## Expected result

A successful combined runner exit should:

```text
keep most of RSI90's large PnL,
reduce runner -> initial SL from ~11 toward EMA100/200's ~3,
improve runner median capture versus RSI90,
avoid overcutting tails like RSI85,
keep both long and short PF > 1.
```
