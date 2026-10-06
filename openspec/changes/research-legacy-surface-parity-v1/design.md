## Context

`research-run-calculation-v1` fixed one hard gate (integers exact, floats rel 1e-6).
The smoke on `btcusdt_p.ema500.calc_smoke_width_band` (5 rows copied from the legacy
replay Surface `width_band_incl_5d`) proved where the failures come from: trade
counts equal, and each failing float equals the stored value once the Engine value is
rounded to the stored precision; `net_pnl` is `round(return, 4) × 10 000`, so it is
not independently rounded. Report: /mnt/project-files/run-calculation/smoke-parity-5x7.md.

## Decisions

### D1. Legacy precision is fixed, not described

The rules restore the known resolution of the legacy artifact; they are not a
tolerance framework. They are fixed in code per Engine summary field (the right-hand
side of `result_bindings`), not per table column name, so a legacy column bound to
`return_pct` gets the `return_pct` rule whatever it is called.

### D2. Explicit opt-in per Experiment

`materialize.parity` selects the gate: `strict` (default, the existing rule) or
`legacy_surface`. Strict remains the contract for Engine results and for new Surfaces
written at full precision. A legacy Experiment is opted in by whoever writes its
`materialize` block.

### D3. `net_pnl` by a $0.5 bound, not by formula

`round(return, 4) × 10 000` is how the legacy builders produced it, not a guaranteed
contract, so the gate checks `|engine − stored| ≤ 0.5` instead of recomputing it.

### D4. No strict fallback inside the legacy gate

The legacy rules replace `rel 1e-6` for those fields; the legacy Surface does not
hold enough precision for it. A result binding whose Engine field has no legacy rule
is compared with the strict rule.

### D5. Equality after rounding

`round(engine, d) == round(stored, d)`, both as floats with Python `round`; the stored
value is rounded too so that `0.2960` and `0.296` compare equal. Empty values keep the
existing rule (both empty pass, one empty fails).

## Risks

- A legacy builder that rounded half differently could miss by one unit on an exact
  half; such a row fails visibly as `parity_failed` and nothing is published.
