## 1. Summary

- [x] 1.1 `profit_factor_r` and `entry_signal_count` on a completed candidate; failed candidates must not populate
      them. Verify: unit tests (winners and losers, no loser, ineligible trades ignored).

## 2. Calculate

- [x] 2.1 Base spec per row (D2), validated, deduplicated; base candidates in the same batch call; chunks fit
      `BATCH_SIZE` (D3). Verify: tests with a fake runner: one base for many rows, a manifest without options.
- [x] 2.2 `blocked_share` value (D5), base failure (D4), journal lists the base runs. Verify: tests.
- [x] 2.3 Parity tolerance 1e-4 for `blocked_share`. Verify: test.

## 3. Acceptance (owner's Mac)

- [ ] 3.1 Calculate a few rows of a filter surface on the local stack: `blocked_share`, `profit_factor` (bound to
      `profit_factor_r`) and the period metrics pass parity against the replay row; rows published.

## 4. Gate

- [x] 4.1 ruff, mypy, the affected tests.
- [x] 4.2 `openspec validate research-calculate-blocked-share-v1 --strict`.
