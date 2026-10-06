## Context

Smoke report: /mnt/project-files/run-calculation/smoke-parity-5x7.md. A full read of a
513 648-row legacy Surface showed that a relative tolerance alone fails on values near
zero (for example 25.6 % of rows on `return_pct`), because there any stored precision
exceeds 0.1 % of the value.

## Decisions

### D1. Parity means the same result, not the same float

The gate answers "did the strategy result change": discrete values equal, continuous
values within 0.1 %.

### D2. Integer metrics exact

Trade count and other `integer` metrics carry the discrete outcome; any difference
fails.

### D3. Relative part from the larger magnitude

`1e-3 × max(|actual|, |expected|)`, so a stored zero does not turn the check into an
absolute-only comparison.

### D4. Absolute floor per metric

The floor prevents the relative tolerance from degenerating near zero. Its values are
fixed by each metric's semantics (fractions 1e-4, R 0.01, money 1.0) and keyed by the
Engine summary field, not by table column or Surface. Fields without a semantic floor
keep 1e-9.

### D5. No manifest field

The constants are part of the gate, the same for every Experiment.

## Risks

- `net_pnl` around 9 000 may differ by about 9 and pass. Accepted: the trade count must
  match exactly and every other metric must agree within 0.1 %.
