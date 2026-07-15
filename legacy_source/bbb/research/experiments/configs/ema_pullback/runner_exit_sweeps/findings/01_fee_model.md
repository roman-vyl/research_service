# Fee model notes

## Current problem

Current runner/RSI reports were run with:

```text
fees_rate = 0.0006
= 0.06% one-way
```

This is visible in each full report's `fee_diagnostics`.

This is a conservative/stress fee assumption. It is not a neutral default if the intended execution model can use maker/limit entries or mixed execution.

## Bybit reference assumption

Current Bybit futures/perpetual public fee structure for basic users is roughly:

```text
maker: 0.020% one-way
VIP0 taker: around 0.055% one-way
```

Research implication:

```text
0.0006 = conservative / stress
0.0004 = realistic mixed execution default
0.0003 = optimistic maker-biased target
```

Do not use only one fee number for runner strategies. Runner/dynamic-exit variants are fee-sensitive because they can increase hold time, turnover behavior, and path dependency.

## Sensitivity estimate from existing reports

The following recalculation is approximate but useful. It keeps gross trade outcomes unchanged and scales fees linearly from current `0.0006` to lower rates.

| Candidate | Net @0.06% | Net @0.04% | Net @0.03% | PF @0.06% | PF @0.04% | PF @0.03% |
|---|---:|---:|---:|---:|---:|---:|
| strict ADX40 RSI90 | 11,225 | 13,685 | 14,915 | 1.353 | 1.452 | 1.505 |
| strict ADX45 RSI90 | 9,370 | 11,866 | 13,115 | 1.301 | 1.400 | 1.454 |
| relaxed ADX40 RSI90 | 13,484 | 20,222 | 23,590 | 1.159 | 1.252 | 1.302 |
| relaxed ADX45 RSI90 | 6,140 | 12,946 | 16,349 | 1.072 | 1.161 | 1.209 |
| strict ADX40 RSI85 | 6,397 | 8,887 | 10,132 | 1.225 | 1.328 | 1.383 |

## Interpretation

Lower fees do not change the key qualitative result:

```text
strict ADX40 RSI90 remains the best quality/PF candidate.
relaxed ADX40 RSI90 remains the richest money candidate but is more fee/turnover sensitive.
ADX40 remains more promising than ADX45 for runner activation.
```

But lower fees materially change how viable relaxed becomes.

With `0.0003`, relaxed ADX40 RSI90 becomes very attractive by total PnL and both-side PF, but it still depends heavily on a small runner cohort. Do not accept it without year/outlier diagnostics.

## Recommended next rerun fee modes

Run the same Phase 1 batch with:

```text
fees_rate = 0.0004
fees_rate = 0.0003
```

Keep old `0.0006` results as stress mode.

## Reporting convention

Every future findings file should include these columns where possible:

```text
net_pnl_fee_06
pf_fee_06
net_pnl_fee_04
pf_fee_04
net_pnl_fee_03
pf_fee_03
```

If only one run is available, clearly state the actual `fees_rate` from report metadata.
