## Context

The research replay that built the surfaces computes, from its trade list (book_metrics_v6 lab, `F.ST.stats`):

- per-trade return `r = net PnL / equity before the trade` (full-equity sizing, fees included), equity chain from
  $10,000 compounded by `r`;
- in sample / out of sample: trades with exit bar before / from the split (2023-07-01 UTC), each part compounded
  again from $10,000; `is_net` and `oos_net` are the final equity of each part minus $10,000;
- years: by the calendar year of the exit bar, `equity after the year's last trade / equity before its first trade
  - 1`; `years_up` counts years with a return above 0, `worst_year` is the smallest return;
- average trade (replay_core `chg_fee_table.summ`): `mean(r) * 10^4` basis points; payoff: `mean(r of winners) /
  -mean(r of losers)`.

Research accounting already records, per closed trade, `exit_time_ms`, `net_pnl`, `equity_before` and
`equity_after`, so all of these follow from the trade list without the Engine.

## Decisions

- D1 Per-trade return is `net_pnl / equity_before`. With full-equity sizing it reproduces re-accounting a part from
  the initial equity exactly; with other sizings it is the compounding of the same per-trade returns (documented,
  not re-sized).
- D2 A part's net is `initial_equity * (prod(1 + r) - 1)` over its trades in trade order, in Decimal; an empty part
  is 0 with 0 trades.
- D3 IS / OOS split by `exit_time_ms < period_split_ms` (IS) else OOS. Year by `exit_time_ms` in UTC.
- D4 A year appears in `years` only when it has a trade. Its return is `equity_after(last) / equity_before(first) -
  1` over the account's own equity chain (not re-based). `years_up` = count of years with `return_pct > 0`;
  `worst_year` = min `return_pct`, null without trades. `years_up` counts exact returns above 0 (owner
  2026-10-16); the replay counted on returns rounded to 4 decimals, so a year with a return in (0, 0.00005) is up
  here and not there.
- D5 `avg_trade_bp` = `mean(r) * 10000`, null without trades. `payoff_ratio` = `mean(r | r > 0) / -mean(r | r < 0)`,
  null when there is no winner or no loser (the replay wrote 0 there; null says "undefined" and a cell with 0
  still compares equal to null only if the parity gate allows it, see D7).
- D6 `period_split_ms` on `BatchExperimentRequest` (optional, default 1688169600000 = 2023-07-01T00:00:00Z) and on
  the materialize `research_policy`; the summary echoes the value it used.
- D7 Calculate parity is unchanged: a bound metric whose stored cell is empty and whose value is null passes; the
  replay's payoff 0 for "no winner or no loser" therefore fails parity on such rows. Those rows are rare (a cell
  without losers or winners); the mismatch is reported, not hidden.
- D8 The new fields are optional on `BatchCandidateResult` (summaries persisted before stay valid) and listed with
  the summary fields a failed candidate must not populate.

## Risks

- Exit time vs exit bar: the replay splits on the exit bar index; Research on `exit_time_ms`. The acceptance check
  against the stored A1 runs shows whether a trade on the split bar lands on the same side.
