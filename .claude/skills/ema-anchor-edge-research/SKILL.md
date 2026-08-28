---
name: ema-anchor-edge-research
description: "Use when asked to autonomously research whether price interaction with a given EMA-stack's anchor EMA (touch/pullback) has a statistically stable entry edge for the ema_pullback strategy, and to progressively evolve any confirmed edge into a candidate strategy — via Research Service batch experiments, not one-off backtests. Triggered by requests like 'find an edge around anchor EMA', 'research the ema_pullback anchor touch', or 'run a coarse-to-fine parameter search for ema_pullback'. Not for running a single known-good backtest, not for editing strategy/component code, not for anything outside ema_pullback anchor-touch discovery."
---

# EMA anchor-touch edge research

## What this is

A methodology, not a script. It walks a future agent session through disciplined,
staged research into one question:

> Does price interaction with a given anchor EMA — inside a given fast/anchor/slow
> EMA stack — contain a statistically stable entry edge, once good pullback/touch
> regimes are separated from noise?

It does not know the answer. It does not assume the answer is yes. It is reusable
across different EMA-stack configurations (fast/anchor/slow periods, ticker, base
timeframe) supplied at the start of each research run — none of that is hardcoded
here.

This document is deliberately implementation-detail-light. It names Research
Service *concepts and capabilities*, not file paths or line numbers, because the
code will keep evolving. Before relying on any specific field name, class name, or
HTTP shape mentioned below, re-derive it from the live source (`grep`/`Read`) or
the live component catalog — never trust this document over the code.

## Non-negotiable ground rules

1. **No look-ahead into prior research.** Do not read old `var/runs/*`,
   `var/runs/batches/*`, historical CSV/heatmap exports, or any prior research
   report to learn what parameter values, ranges, or "winners" a past search
   found. It is fine to open an *old run's raw request/response JSON shape*
   purely to confirm today's request/response format still matches — but never
   to extract a numeric value, threshold, or ranking from it. If you are unsure
   whether you are about to use a file for format vs. for values, stop and ask.
2. **No hardcoded search values.** No EMA periods, ATR multipliers/periods, width
   thresholds, lookback bars, SL/TP distances, or reward/risk ratios belong in
   this document or in any config this skill writes before a search starts. All
   of that is either supplied by the user at First Run Procedure time, or derived
   live from component catalog schemas plus reasoned coarse ranges the agent
   states and justifies before running them.
3. **No new trading logic.** Use only strategy components that already exist in
   the live component catalog. If the research question cannot be expressed with
   existing components, stop the branch, write down exactly what's missing and
   why, and hand that back as a proposed component/strategy change — do not
   improvise new component logic inside a research loop.
4. **Batch, not loops of single backtests.** Every sweep of N candidate
   configurations over the same ticker/timeframe/window is one Research batch
   experiment (shared window resolution, one Strategy Engine range-batch call,
   one shared market frame, N materializations) — never N standalone backtest
   calls. See "Batch execution" below.
5. **Ridge, not point.** A single high-scoring candidate is never sufficient
   evidence. Every promising result must be checked against its parameter
   neighborhood before being trusted.

## Research capabilities this skill relies on

Confirm each of these still exists and still means what's described here before
starting — don't assume; read the current code.

- **Canonical strategy-instance identity** (`research_service.domain.strategy_instance`):
  a strategy instance is the tuple `{strategy_id, ticker, base_timeframe, raw_spec}`.
  `instance_id` is *derived*, never chosen — build every candidate as this
  identity subset (plus `enabled` where a full deployable document is needed),
  never invent an `instance_id`.
- **Component catalog** — Research Service's `GetComponentCatalog` application
  service (proxying Strategy Engine's composer catalog for a `strategy_id`). This
  is the *only* authoritative source for: which setup/blocker/trigger/exit/context
  components exist, their `component_id`s, their parameter names, types, and
  allowed ranges. Read it fresh at the start of every research session (and again
  whenever you're about to touch a component family you haven't used yet this
  session) — do not remember catalog shapes across sessions or code versions.
- **Config validation** (`ValidateStrategyConfig` / the Strategy Engine authoring
  validation it delegates to) — use it to catch a malformed candidate `raw_spec`
  before wasting a batch slot on it, not as a substitute for reading the catalog.
- **Batch experiments** (`RunBatchExperiment` + `PersistBatchExperiment`, backed
  by `application/experiments/*`): one experiment = one `strategy_id` + one
  `ticker` + one `base_timeframe` + one comparison window (`range_policy` +
  optional explicit `range`), shared by every candidate; each candidate
  contributes only what legitimately varies (`raw_spec`, execution/accounting
  policy, `managed_policy_enabled`, free-form `metadata`). Internally this
  resolves the window once, makes exactly one Strategy Engine `/range-batch`
  (evaluate-many-variants) call, reads exactly one shared Market Data Service
  historical frame, then materializes and persists each candidate independently
  with per-candidate failure isolation. This is "shared-L0": the expensive,
  identity-defining work (window resolution, Engine evaluation, market read)
  happens once per experiment, not once per candidate.
- **No HTTP route currently exposes batch experiments.** As of this writing the
  only way to actually invoke `RunBatchExperiment`/`PersistBatchExperiment` is to
  drive them directly from a short Python driver against the installed
  `research_service` package — build a `Container` the same way
  `runtime/wiring.py`/`api/app.py` already do (real `HttpStrategyEngineClient`,
  real `HttpMarketDataClient`, real `FilesystemArtifactStore` pointed at the
  running stack's actual `/data` or `var/` root), construct a
  `BatchExperimentRequest`, call `.execute()`. This is orchestration of an
  existing capability, not new trading logic — it belongs in a throwaway script
  under your experiment workspace (see First Run Procedure), not inside
  `src/research_service`. If a proper HTTP/CLI entrypoint for batch experiments
  has since been added, prefer that instead and update your notes accordingly.
- **Range/window policy**: `range_policy="full_available"` resolves against
  Market Data Service's real committed stream bounds and continuity audit for
  the ticker/timeframe, producing one `market_data_hash` every candidate in the
  experiment shares. `range_policy="explicit_range"` takes a caller-supplied
  `from_ms`/`to_ms`. Use `full_available` for the main discovery search (see
  "Full history by default" below); explicit narrower ranges are for the later
  validation stage only.
- **Persisted artifacts**: every completed single-instance backtest (including
  each batch candidate) is written as an immutable, atomically-published run
  bundle (request/result/manifest/trades/metrics, content-hashed) under the
  artifact store's runs root; every batch experiment additionally gets its own
  persisted batch summary under the artifact store's batches root. Read these
  back through the same application services that already parse them
  (`ReadResearchRuns` / the batch artifact reader) rather than hand-parsing JSON
  where you don't have to.
- **Trade-level accounting, not pre-computed ratios.** Research's accounting
  result gives you `net_pnl`, `gross_pnl`, `fees_paid`, `realised_trade_count`,
  and a full list of individual `TradeRecord`s (side, entry/exit price and time,
  gross/net pnl per trade, fees, equity before/after, hold time, exit
  attribution, MFE/MAE path metrics). It does **not** hand you a pre-computed
  profit factor, win rate, drawdown, or long/short split — you derive those
  yourself from the trade list (see "Decision metrics" below). Confirm this is
  still true before assuming otherwise.

## Phase sequence (do not skip or reorder without a documented reason)

```
Phase A  naked anchor symmetric baseline            (one FIXED symmetric SL/TP, not swept)
Phase B  structural entry discovery                 (SL/TP stays FIXED from Phase A)
Phase C  entry candidate selection                   (gate: must pass before D)
Phase D  SL/TP optimization                          (symmetric first, then asymmetric)
Phase E  secondary filters (RSI / ADX-DMI / HTF context / other blockers)
Phase F  managed-exit research                      (only after a frozen static candidate exists)
Phase G  validation
Phase H  final research report
```

Every phase transition is a decision, not a formality. State the decision and its
justification in the journal (see below) before moving on. It is entirely valid
for a phase to end in a stop condition instead of an advance.

**Causality this sequence enforces, and why it must not be reordered:**

```
naked anchor
  ↓
ONE fixed neutral symmetric exit          (Phase A)
  ↓
find WHICH anchor-touch is a quality entry
  freshness / repeat-touch lookback, stack width, optional bounce count
  (Phase B — SL/TP still fixed)
  ↓
select stable, profitable, lower-DD entry candidates   (Phase C)
  ↓
ONLY THEN optimize execution geometry: SL/TP            (Phase D)
  ↓
secondary filters / managed exits, later                (Phase E/F)
```

**DO NOT optimize SL/TP before structural entry discovery is complete. During
structural discovery (Phase B), SL/TP MUST remain fixed at the Phase A value.**
Sweeping SL/TP before the entry itself is understood optimizes the exit of a mix
of good and bad entries indiscriminately — it can make a weak entry *look* good
by pure payout skew, which is exactly the failure mode this ordering exists to
prevent.

### Phase A — naked anchor symmetric baseline

Build the simplest possible `ema_pullback` instance around the supplied
fast/anchor/slow EMA stack and the existing canonical anchor-touch trigger
component (find its exact `component_id` in the live catalog — likely something
like an anchor-touch/reclaim trigger family; do not guess the name, read it).
No setups, no blockers, no context filters, no managed exits.

Use **one fixed symmetric static exit** — the existing ATR-based stop-loss and
take-profit components, with **equal** SL and TP distance (same ATR period,
same multiplier, same everything except which side of price they sit on). Pick
this single distance from the ATR component's schema (min/max/allowed
granularity), the base timeframe, and reasoned judgment about typical
bar-to-bar/swing-scale volatility for this instrument — state and justify the
choice in the journal. This is a fixed reference exit for the rest of Phase A
and all of Phase B, not something to sweep here; sweeping SL/TP is Phase D's
job, done later, on selected structural entry candidates only.

Purpose of this phase: confirm the setup is not dead, and establish the
baseline everything in Phase B is measured against. Measure, from the trade
list:
- trade count (and whether it's non-trivial at all — a handful of trades over a
  multi-year window is not evidence of anything);
- gross result vs. net (after-fee) result — these are different conclusions;
- fees as a fraction of gross;
- win rate, profit factor;
- long vs. short trade count and PnL, separately;
- a simple drawdown measure from the reconstructed equity curve;
- turnover (trades per unit time, or notional traded relative to equity).

Explicitly distinguish and record which of these you found:
- **no interaction edge** — close to zero net signal regardless of fees;
- **edge before fees, destroyed by turnover/fees** — gross positive, net
  negative or negligible;
- **full after-fee edge** — net positive with a trade count you consider
  meaningful.

Do not add anything beyond the naked trigger plus its one fixed symmetric exit
in this phase, even if it's tempting. Freeze this exact configuration (raw
trigger + fixed symmetric SL/TP) as the Phase B parent baseline before moving
on.

### Phase B — structural entry discovery

Purpose: find out *which* anchor touches are quality entries — not yet how to
exit them. **Keep the Phase A symmetric SL/TP completely fixed** through this
entire phase; every candidate here varies only the entry-side structural
filter(s), never the exit.

Investigate one axis at a time — do not combine these into one giant grid
before understanding each independently:

1. **`untouched_anchor_setup`** (or the catalog's current equivalent — verify):
   does the time since the anchor was last touched (freshness of the anchor
   level, repeat-touch lookback) predict touch quality? Sweep its lookback/
   freshness parameter(s) as their own axis, coarse → refine → ridge.
2. **`anchor_stack_width_setup`** (or the catalog's current equivalent name —
   verify): investigate, in this order:
   - current stack width (fast-to-slow or anchor-to-slow separation, per the
     component's actual parameters) alone;
   - recent/historical stack width alone;
   - freshness/lookback of a recent width expansion alone;
   - only once each shows something, local combinations around the promising
     regions found for each.
   Research question: does a wider/more-expanded EMA stack at touch time predict
   a better subsequent touch?
3. **`ema_bounce_counter_setup`** (if its current schema/semantics fit this
   question — confirm from the catalog before using it) — an optional
   additional axis, investigated only after the two primary axes above are
   each independently understood: does the count/frequency of recent prior
   anchor interactions predict the next touch's quality?

For each component/axis: run its own coarse→refine→ridge batch experiment(s)
against the exact Phase A frozen baseline (fixed symmetric exit unchanged), and
explicitly answer "does this structural condition improve on the naked
baseline — profitability, and especially drawdown — on its own?" before moving
to the next axis or to combinations. Objective throughout: a profitable,
materially lower-drawdown, sufficiently populated, *stable* entry region — not
the single highest-PF point. Analyze total/long/short for every axis and every
promising region.

### Phase C — entry candidate selection (gate)

Before Phase D is permitted, select several robust structural entry candidates
from Phase B's findings (a single component/axis result, or a considered
combination of the axes that each showed real independent value). Do not
optimize SL/TP here — this phase is about which entries to carry forward, still
under the Phase A fixed symmetric exit.

Each selected candidate must show, under the still-fixed Phase A symmetric
exit:

- positive after-fee net PnL;
- PF > 1 driven by the distribution of trades, not by one outsized trade;
- a materially lower drawdown than the Phase A naked baseline (state what
  "materially lower" means for this run, and why);
- a trade count you consider statistically non-trivial for the window used;
- a contiguous region of good neighboring parameters, not an isolated point —
  reject isolated parameter spikes even if their raw score looked best;
- a clear understanding of whether the candidate's edge is `BOTH_SIDES_EDGE`,
  `LONG_ONLY_EDGE`, `SHORT_ONLY_EDGE`, or effectively `NO_STABLE_EDGE` (see
  "Long/short independence" below).

If nothing in Phase B clears this bar: either go back into Phase B with a
different structural axis or combination, or conclude the branch with
`NO_EDGE_FOUND` (or `STOP_OVERFIT_RISK` if the only positive results were
isolated spikes — see Stop conditions).

### Phase D — SL/TP optimization

Only on the structural entry candidates selected in Phase C — never on the
naked baseline, and never before Phase C's selection. Two sub-steps, in order:

1. **Symmetric distance exploration first.** For each selected structural
   candidate, sweep symmetric SL==TP distance (coarse → refine → ridge, same
   discipline as every other phase) around the Phase A fixed value, to see
   whether a different symmetric distance materially changes the picture for
   this specific entry. This re-confirms (or revises) the symmetric edge now
   that the entry itself is understood, before touching payout skew.
2. **Asymmetric SL/TP payoff optimization.** Only after step 1. Vary SL
   distance and TP distance independently (reward/risk ratio becomes a derived
   quantity, not an input you pick first). Coarse sweep first, batch
   experiment, then refine around promising regions. Always keep the step-1
   symmetric finalist as a labeled control candidate in these comparisons, so
   you can tell whether asymmetric payout added real value or just increased
   variance around the same underlying edge.

Evaluate trade count, PF, net PnL, drawdown, fees, and long/short split for
every candidate under consideration in both steps, not just PnL. Seek a broad
stable region, not a single optimum.

### Phase E — secondary filters

Only after a frozen static (symmetric-or-asymmetric, whichever Phase D's
evidence supports) candidate exists. Existing components only — RSI-based
blockers, ADX/DMI-based conditions, HTF contexts, other entry blockers or
signal-exit components already in the catalog. Add **one at a time** as an
incremental change against the exact frozen parent baseline; do not run a
combinatorial sweep of several new filters simultaneously before understanding
each one's own marginal contribution.

### Phase F — managed-exit research (late, separate)

Break-even shifts, protected phase, runner behavior, active stop/take
switching, and other managed-exit machinery must never be used to *establish*
entry edge — they belong strictly after a frozen static entry/exit candidate
exists. Maintain this boundary explicitly:

```
ENTRY EDGE FOUND  →  STATIC EXIT CANDIDATE FROZEN  →  MANAGED EXIT RESEARCH
```

Do not let a managed exit's complexity mask a weak entry earlier in the chain.

### Phase G — validation

Before calling anything final: check the finalist against parameter
perturbations one step away in every varied dimension; check performance on
distinct time subperiods within the same discovery-universe history (not a
different universe — see "Full history by default"); reconfirm long/short
attribution; if there's a second liquid, catalog-supported ticker available and
it's reasonable to check, do so; sanity-check sensitivity to the fee/slippage
assumptions used throughout. A single full-history winner is not, by itself,
sufficient evidence of robustness.

### Phase H — final research report

Summarize the whole chain: hypothesis, what was tested at each phase, what was
rejected and why, the final candidate (or the `NO_EDGE_FOUND` conclusion),
long/short attribution, stability evidence, validation results, and explicit
next steps if any. This is the terminal artifact of a research session — see
"Experiment journal" for the running version kept throughout, and produce a
clean final version here.

## Long/short independence

At every phase that matters (Phase A baseline, Phase B/C structural findings,
Phase D verdict, Phase E), report aggregate, long-only, and short-only results as three separate rows,
not one blended number. A positive aggregate result driven entirely by one
long-only bull-regime stretch of history is not evidence of a general edge.
Label each meaningful result with one of: `BOTH_SIDES_EDGE`, `LONG_ONLY_EDGE`,
`SHORT_ONLY_EDGE`, `NO_STABLE_EDGE`. You are not required to force long and short
into equal profitability — you are required to know, and state, which side is
actually generating the result.

## Coarse → refine → ridge loop (applies to every swept axis, every phase)

```
1. Read the current component/parameter schema live.
2. State a coarse range + step, and justify it from schema/timeframe/observed
   behavior — never from memory of a prior search's winner.
3. Run ONE batch experiment covering the coarse range (batch, not a loop of
   single backtests — see below).
4. Score every candidate on the full metric set (see "Decision metrics"), not
   PnL alone.
5. Identify contiguous promising region(s), not the single best point.
6. If a region exists: run a second, narrower batch experiment refining inside
   it, plus its immediate neighbors, to check stability.
7. If the "best" result is an isolated spike with much worse neighbors on every
   side: flag STOP_OVERFIT_RISK for that region and do not adopt it, even though
   its raw score looked best.
8. Freeze the winning region's representative candidate as the new baseline for
   the next axis, and record the decision in the journal before moving on.
```

Batches can be large — hundreds or low thousands of candidates for one
experimental axis is fine if the axis's dimensionality justifies it — but stay
disciplined about **one axis's Cartesian space at a time**, not the full
cross-product of every axis discussed in this document at once. That combinatorial
explosion is exactly what this staged sequence exists to avoid.

## Batch execution — mandatory shape

For any sweep of N ≥ 2 candidate configurations over the same comparison window:
build **one** `BatchExperimentRequest` (one `strategy_id`, one `ticker`, one
`base_timeframe`, one `range_policy`/`range`, one candidate list) and call
`RunBatchExperiment.execute()` once. This gets you the shared-L0 property for
free: one window resolution, one Strategy Engine `/range-batch` call, one shared
Market Data Service historical read, one shared `market_data_hash` every
candidate in the batch is validated against, N independent
materialize+persist steps with per-candidate failure isolation.

Never write `for candidate in candidates: run_single_instance_backtest(...)` for
a sweep — that silently reintroduces N separate window resolutions, N separate
Engine calls, and N separate market reads, defeats the whole point of the batch
path, and risks candidates in the "same" sweep actually being compared against
subtly different market data if anything changes between calls.

## Full history by default

Use `range_policy="full_available"` for the main discovery search in every
phase through Phase F. Every candidate inside one experiment is already forced
to share one window by `BatchExperimentRequest`'s own invariants — this rule is
about *experiment-to-experiment* consistency: don't compare a Phase B result
computed over one window against a Phase D result computed over a different
one. Subperiod / walk-forward / out-of-sample slicing is Phase G validation
work, done deliberately and labeled as such, after discovery is complete —
never mixed into the discovery loop itself.

## Search-space generation

Ranges come from, in this order: (1) the live component schema's declared
min/max/units, (2) the base timeframe and what it implies about bar-to-bar and
swing-scale behavior, (3) what you actually observed in the previous phase's
trade data, (4) plain reasoning about what a "coarse but sane" starting grid
looks like for that parameter's semantics. State this reasoning before running
anything. It is never acceptable to choose a range because "the old research
winner was around X" — you do not have access to that information for this
purpose, and even if you did, using it would defeat the point of this exercise.

## Fees are mandatory, always

Never conclude anything from gross PnL alone. Every phase's evaluation must
separately report gross behavior (where meaningful), total fees, and net PnL.
This matters most in high-turnover symmetric-exit experiments, where fees can
plausibly consume an entire gross edge. `SIGNAL_EXISTS_BUT_FEES_DESTROY_EDGE` is
a real, useful, reportable conclusion — not a failure to find something better.

## Decision metrics

Minimum set for every candidate you seriously evaluate, computed from the raw
trade list (see "Research capabilities" above — Research does not hand you
pre-computed ratios):

- net PnL, gross PnL, total fees;
- profit factor (gross profit / gross loss, or the net equivalent — pick one
  convention and use it consistently within a research session, document
  which);
- realised trade count;
- win rate;
- a drawdown measure from the reconstructed equity curve;
- long-only and short-only versions of the above;
- local parameter-neighborhood stability (does a one-step perturbation in any
  varied dimension preserve the qualitative result?).

Use a broader **discovery score** (weighting toward "does this region look
promising at all") to decide what to refine into next — but the final
**acceptance decision** for a candidate must weigh robustness, trade count, and
neighboring-candidate agreement, not the discovery score or raw PnL alone.
Additional trade-quality diagnostics already available on each `TradeRecord`
(MFE/MAE path metrics, hold time, exit attribution) are useful supporting
evidence when they help explain *why* a result looks the way it does.

## Experiment journal

Maintain both a machine-readable and a human-readable trail. Do not rely on
individual persisted run/batch artifacts alone to reconstruct what happened —
they record *what ran*, not *why*, *what was learned*, or *what's next*.

For every research iteration, record at minimum:
- hypothesis being tested;
- frozen parent configuration (the exact `raw_spec` this iteration varies from);
- exactly which parameter(s) were varied and their ranges;
- candidate count and the experiment/batch id used;
- the shared window/`market_data_hash` for that experiment;
- key metrics per candidate or per region;
- the promising region(s) identified;
- the region(s) explicitly rejected, and why;
- the next planned step and its reason.

After each phase, refresh a concise current-state summary (own document or
top-of-journal block — your choice, but keep exactly one canonical copy):

```
CURRENT_HYPOTHESIS
CURRENT_FROZEN_BASELINE
WHAT_WAS_TESTED
WHAT_WAS_LEARNED
WHAT_WAS_REJECTED
NEXT_EXPERIMENT
```

This must be enough for a brand-new agent session, with no memory of this one,
to pick up the research exactly where it left off — not restart from Phase A.

**Never delete a negative or failed experiment's record.** A rejected region is
part of the evidence base; losing it risks re-running (and re-rejecting) the
same dead end in a future session. Keep the record of what was tried and why it
didn't hold up, even when — especially when — the result was negative.

## Stop conditions

Use these labels (or, if repository/journal conventions have since introduced
different names, use those instead — but preserve the underlying meaning):

- **`NO_EDGE_FOUND`** — several consecutive Phase B structural searches fail to
  produce a candidate that clears Phase C's gate, or Phase E filters fail to
  rescue a marginal candidate.
- **`STOP_OVERFIT_RISK`** — a positive result exists only at one narrow point
  and collapses at its immediate parameter neighbors.
- **`SYMMETRIC_EDGE_CONFIRMED`** — Phase C's gate criteria are met: at least
  one structural entry candidate, under the fixed Phase A symmetric exit, is
  profitable, materially lower-drawdown, and stable.
- **`STATIC_STRATEGY_CANDIDATE_FOUND`** — after Phase D (and, if used, Phase
  E), a robust, validated static candidate exists.
- **`READY_FOR_MANAGED_EXIT_RESEARCH`** — the static candidate is stable enough
  that Phase F is a reasonable next investment.

Any of these is a legitimate, complete terminal (or phase-terminal) outcome.
`NO_EDGE_FOUND` is not a failure of the research process — it's the process
working correctly on a hypothesis that didn't hold up.

## Do not touch the trading core

Use only strategy components that already exist in the live catalog. If a
research question genuinely cannot be expressed with what exists:

1. stop the current search branch;
2. write the precise missing capability/hypothesis down;
3. explain concretely why existing components can't express it;
4. hand this back as a proposed strategy/component-catalog change request — do
   not write new component/trading logic inside this research loop.

## First Run Procedure

Before Phase A of any new research run:

1. Record the current repository branch and commit SHA.
2. Confirm Research Service, Strategy Engine, and Market Data Service are all
   reachable and healthy (whatever the current health/readiness mechanism is —
   check it live, don't assume the shape from memory).
3. Read the live component catalog for the target `strategy_id` (`ema_pullback`
   unless told otherwise).
4. Take from the user (do not invent): `ticker`, `base_timeframe`, `fast EMA
   period`, `anchor EMA period`, `slow EMA period`. If any is missing, ask —
   don't guess or default to a value you happen to recall.
5. Confirm the target ticker/timeframe is actually enabled/covered by the
   running Market Data Service configuration before relying on
   `full_available` — a stream that isn't configured will simply fail, and
   that failure means "check the config," not "no edge."
6. Create an isolated, clearly-named experiment workspace/namespace for this
   research run (distinct experiment-id prefix, distinct journal file/dir) so
   it never collides with or silently reuses another run's candidates,
   artifacts, or journal.
7. Write down the initial hypothesis and the frozen Phase-A baseline
   configuration in the journal.
8. Only then begin Phase A.

## What this skill deliberately does not run

This document is methodology only. Following it does not itself execute any
backtest, create any batch, or read any historical result. A session invoking
this skill should treat "run the First Run Procedure and begin Phase A" as an
explicit next action to confirm with the user before spending compute, not an
implicit instruction to start immediately.
