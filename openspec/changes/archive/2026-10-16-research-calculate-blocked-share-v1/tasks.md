## 1. Summary

- [x] 1.1 `profit_factor_r` and `entry_signal_count` on a completed candidate; failed candidates must not populate
      them. Verify: unit tests (winners and losers, no loser, ineligible trades ignored).

## 2. Calculate

- [x] 2.1 Base spec per row (D2), validated, deduplicated; base candidates in the same batch call; chunks fit
      `BATCH_SIZE` (D3). Verify: tests with a fake runner: one base for many rows, a manifest without options.
- [x] 2.2 `blocked_share` value (D5), base failure (D4), journal lists the base runs. Verify: tests.
- [x] 2.3 Parity tolerance 1e-4 for `blocked_share`. Verify: test.

## 3. Acceptance (owner's Mac)

- [x] 3.1 Calculate a few rows of a filter surface on the local stack: `blocked_share`, `profit_factor` (bound to
      `profit_factor_r`) and the period metrics pass parity against the replay row; rows published.
      Mac 2026-10-16, research e19a764 + Engine 7263ab2: 5 rows published with full parity (BTC iso C1.1 W7/LB20/SL7/TP5.5
      C1.1 <= 0.45; BTC A2.1 >= 2.5; BTC weighted vote set 2 T 8; BTC iso B1 5m W8/LB120/SL6/TP7 >= 1.05; ETH A2.2
      W11/LB20/SL8/TP5.5 <= 0.5). The first try of the vote row failed on `worst_year` at the default floor: D7, PR #38.

## 4. Gate

- [x] 4.1 ruff, mypy, the affected tests.
- [x] 4.2 `openspec validate research-calculate-blocked-share-v1 --strict`.
