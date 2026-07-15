# EMA200 runner exit sweeps

Research package for EMA200 pullback exit-management experiments.

This folder is the human-facing research home for runner / protected / dynamic-exit sweeps. It should contain the roadmap, findings, commands, and small batch specs. Large generated run reports remain under `research/results/runs/` and are referenced by path; do not copy large report JSON files here.

## Why this folder exists

The repository currently has two different kinds of experiment artifacts:

```text
research/experiments/specs/batches/      # machine-oriented batch specs
research/experiments/specs/candidates/   # machine-oriented single-run configs
research/experiments/configs/ema_pullback/width_sweeps/  # human research package with README/findings
```

For ongoing EMA200 research, prefer the `configs/ema_pullback/<study>/` style. It keeps the research narrative next to the configs and avoids losing conclusions in chat history.

## Proposed convention

Use this package as the canonical home for runner-exit research:

```text
research/experiments/configs/ema_pullback/runner_exit_sweeps/
  README.md
  findings/
    00_current_state.md
    01_fee_model.md
    02_adx_protected_be_findings.md
    03_adx_runner_rsi5m_phase1_findings.md
    04_next_rerun_plan.md
  batches/
    <batch specs for this study>.json
  candidates/
    <single-run configs for this study>.json
  templates/
    phase_findings_template.md
```

Allowed transitional state:

```text
research/experiments/specs/batches/<batch>.json
research/experiments/specs/candidates/<study>/<candidate>.json
```

If a batch already exists in `specs/`, do not move it blindly. Instead, add a finding file here that references the exact batch path and result path. For new runner-exit sweeps, prefer self-contained `batches/` and `candidates/` inside this package unless the loader or existing tooling requires `specs/`.

## Current research line

We started with EMA200 real fixed-TP candidates:

```text
strict continuation:
  EMA stack: 100 / 200 / 496
  width: w12 / r14 / width_lb20
  untouched: lookback75 / active_bars8
  trigger: touch_anchor
  SL/TP: 6 ATR / 14 ATR

relaxed medium:
  EMA stack: 100 / 200 / 496
  width: w9 / r10 / width_lb20
  untouched: lookback75 / active_bars8
  trigger: touch_anchor
  SL/TP: 4 ATR / 10 ATR
```

Main discovery so far:

```text
ADX/DI is better interpreted as a runner selector than as a break-even trigger.
```

Naive hard BE at entry is not accepted as a universal protective formula. ADX/DI correctly identifies high-MFE trades, but hard BE often gives back strong moves to entry. The promising branch is:

```text
ADX/DI -> runner
runner -> disable initial TP
runner/late stage -> dynamic exit, currently RSI 5m 90/10 as first candidate
```

## Current best candidates before fee rerun

Using current run reports with `fees_rate = 0.0006` one-way:

| Candidate | Net PnL | PF | Win rate | Max DD | Long PF | Short PF | Notes |
|---|---:|---:|---:|---:|---:|---:|---|
| relaxed ADX40 runner + RSI5m 90/10 | 13,484 | 1.159 | 33.9% | -0.486 | 1.179 | 1.134 | Max money, but noisy and fee-heavy |
| strict ADX40 runner + RSI5m 90/10 | 11,225 | 1.353 | 36.5% | -0.359 | 1.155 | 1.660 | Best quality/PF candidate |
| strict ADX45 runner + RSI5m 90/10 | 9,370 | 1.301 | 39.3% | -0.392 | 1.098 | 1.611 | Cleaner/rarer runner, less money |
| strict ADX40 runner + RSI5m 85/15 | 6,397 | 1.225 | 43.2% | -0.424 | 1.192 | 1.279 | Higher capture, less tail capture |
| relaxed ADX45 runner + RSI5m 90/10 | 6,140 | 1.072 | 34.9% | -0.565 | 1.013 | 1.147 | Positive but weaker |

Important: current fee is conservative/stress-like. See `findings/01_fee_model.md` before choosing winners.

## Next intended rerun

Do not expand the strategy grid yet. First rerun the same Phase 1 candidates with lower fee assumptions:

```text
fees_rate = 0.0004  # realistic mixed mode
fees_rate = 0.0003  # optimistic maker-biased mode
```

Keep `0.0006` as stress comparison, not the only default.

## Files

Read in this order:

```text
findings/00_current_state.md
findings/01_fee_model.md
findings/02_adx_protected_be_findings.md
findings/03_adx_runner_rsi5m_phase1_findings.md
findings/04_next_rerun_plan.md
```
