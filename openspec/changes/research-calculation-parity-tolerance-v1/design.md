## Context

Smoke report: /mnt/project-files/run-calculation/smoke-parity-5x7.md. Stored
precision differs across Surfaces (width_band 4/2 decimals, adx 6/4, trailing 6/1,
ratio_4d full); some Surfaces labelled engine are rounded too.

## Decisions

### D1. Parity means the same result, not the same float

The gate answers "did the strategy result change", so a recalculation passes when
discrete values are equal and continuous values agree within 0.1 %. It does not try
to reconstruct how each table was rounded.

### D2. Integer metrics exact

Trade count and other `integer` metrics carry the discrete outcome; any difference
fails.

### D3. rel 1e-3 with an absolute floor of 1e-6

0.1 % covers the observed rounding (max 7.9e-4) with margin and still fails on any
change that alters the strategy result. The 1e-6 floor only keeps values at zero
comparable; a value rounded near zero (for example cumulative R `0.03` vs `0.0349`)
fails, which is safe: nothing is published.

### D4. No manifest field

The constants are part of the gate, the same for every Experiment.

## Risks

- `net_pnl` around 9 000 may differ by up to about 9 USD and pass. Accepted: the trade
  count must match exactly and every other metric must agree within 0.1 %.
