## Why

Two surface metrics still block Calculate on the replay-built filter surfaces (owner 2026-10-16):

- `blocked_share`, the share of the cell's entry signals that the filter blocks. One run cannot give it: the share
  needs the signal count of the same cell without the filter. The owner wants the metric kept and computed by
  Research ("Надо добавить blocked share в ресерч сервис подсчет").
- `profit_factor`: the replay surfaces store the profit factor in R (sum of the winners' net R / sum of the losers'
  net R); the Research summary has the profit factor in money, so with compounding equity they differ on almost
  every row and the parity gate fails (first real Calculate: 1.301886 in the table, 1.279385 in the run). The owner
  chose a profit factor in R in the summary ("Делаем pf r").

## What Changes

- The batch summary of a completed candidate gains `profit_factor_r` (net R of winners / |net R of losers| over the
  R-eligible trades; null without a losing trade) and `entry_signal_count` (the number of Engine entry
  opportunities of the run's evaluation).
- Calculate computes `blocked_share` for every calculated row of a manifest with options: the row's "base" spec is
  its spec with no option inserted (the template with the row's bindings, as a row with every option off); every
  distinct base spec runs once in the same Engine batch call as the rows; `blocked_share = 1 - entry_signal_count of
  the row / entry_signal_count of its base` (0 when the base has no signal). A manifest binds it with the result
  binding `"blocked_share": "blocked_share"`. A manifest without options gets 0.
- Base runs are ordinary Research runs (persisted, not linked to any row) and are listed in the job journal.
- Parity tolerance of `blocked_share`: absolute 1e-4 (the tables round it to 4 decimals).

## Out of scope

- No change to Strategy Engine; Research still does not interpret components: "base" is defined only by the
  manifest's options.
- No Engine evaluation without accounting (a lighter base call) in this change.
