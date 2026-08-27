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
Phase A  naked anchor-touch baseline
Phase B  symmetric SL/TP calibration              (gate: must pass before C proceeds far)
Phase C  signal/noise structural filtering          (anchor_stack_width_setup, untouched_anchor_setup, ema_bounce_counter_setup)
Phase D  symmetric-edge verdict                     (gate: must pass before E)
Phase E  asymmetric SL/TP payoff optimization
Phase F  secondary filters (RSI / ADX-DMI / HTF context / other blockers)
Phase G  managed-exit research                      (only after a frozen static candidate exists)
Phase H  validation
Phase I  final research report
```

Every phase transition is a decision, not a formality. State the decision and its
justification in the journal (see below) before moving on. It is entirely valid
for a phase to end in a stop condition instead of an advance.

### Phase A — naked anchor-touch baseline

Build the simplest possible `ema_pullback` instance around the supplied
fast/anchor/slow EMA stack and the existing canonical anchor-touch trigger
component (find its exact `component_id` in the live catalog — likely something
like an anchor-touch/reclaim trigger family; do not guess the name, read it).
No setups, no blockers, no context filters, no managed exits. Use whatever
minimal static exit the catalog effectively requires just to close a position
(document the choice; it is a placeholder, not a result).

Measure, from the trade list:
- trade count (and whether it's non-trivial at all — a handful of trades over a
  multi-year window is not evidence of anything);
- gross result vs. net (after-fee) result — these are different conclusions;
- fees as a fraction of gross;
- win rate;
- long vs. short trade count and PnL, separately;
- a simple drawdown measure from the reconstructed equity curve;
- turnover (trades per unit time, or notional traded relative to equity).

Explicitly distinguish and record which of these you found:
- **no interaction edge** — close to zero net signal regardless of fees;
- **edge before fees, destroyed by turnover/fees** — gross positive, net
  negative or negligible;
- **full after-fee edge** — net positive with a trade count you consider
  meaningful.

Do not add anything beyond the naked trigger in this phase, even if it's
tempting.

### Phase B — symmetric SL/TP calibration

Purpose: separate "is the entry any good" from "did we get lucky with reward/risk."
Use symmetric static exits — the existing ATR-based stop-loss and take-profit
components, with **equal** SL and TP distance (same ATR period, same multiplier,
same everything except which side of price they sit on).

Derive a coarse initial multiplier range yourself from: the ATR component's
schema (min/max/allowed granularity), the base timeframe, and what you observe
about typical bar-to-bar and swing-scale volatility for this instrument in Phase
A's trade data. State the chosen coarse range and *why* before running it — this
justification is part of the journal entry, not optional. Do not narrow toward
any value you already "know" is favorable.

Run the coarse sweep as one batch experiment (all symmetric-multiplier
candidates, same window, same everything else). Analyze PF, net PnL, trade
count, fees, win rate, long PF, short PF, and drawdown across the sweep surface
— not just the single best point. Identify any candidate parameter is a *region*
where results, not a fluke.

If a promising region exists, refine with a second, narrower batch experiment
centered on it, and check neighborhood stability (do the immediate neighbors of
the apparent best point also look good, or does performance collapse one step
away?).

The goal here is not maximum PnL. The goal is answering: is there a symmetric-RR
region where entry has positive after-fee expectancy? One positive point is not
an answer.

### Phase C — signal/noise structural filtering

Only after Phase B, and one axis at a time — do not combine these into one giant
grid before understanding each independently.

1. **`anchor_stack_width_setup`** (or the catalog's current equivalent name —
   verify): investigate, in this order:
   - current stack width (fast-to-slow or anchor-to-slow separation, per the
     component's actual parameters) alone;
   - recent/historical stack width alone;
   - freshness/lookback of a recent width expansion alone;
   - only once each shows something, local combinations around the promising
     regions found for each.
   Research question: does a wider/more-expanded EMA stack at touch time predict
   a better subsequent touch?
2. **`untouched_anchor_setup`**: does the time since the anchor was last touched
   (freshness of the anchor level) predict touch quality? Sweep its lookback/
   freshness parameter(s) as their own axis.
3. **`ema_bounce_counter_setup`** (if its current schema/semantics fit this
   question — confirm from the catalog before using it): does the count/
   frequency of recent prior anchor interactions predict the next touch's
   quality? Investigate independently before mixing with width or freshness.

For each component/axis: run its own coarse→refine batch experiment(s) against
the Phase B symmetric-exit frozen baseline, and explicitly answer "does this
component add incremental value over the frozen parent, on its own?" before
moving to the next axis or to combinations.

### Phase D — symmetric-edge verdict (gate)

Before Phase E is permitted, the accumulated symmetric-exit evidence (Phase B,
refined by whichever Phase C filters showed real incremental value) must show,
together:

- positive after-fee net PnL;
- PF > 1 driven by the distribution of trades, not by one outsized trade;
- a trade count you consider statistically non-trivial for the window used;
- an acceptable drawdown (state what "acceptable" means for this run, and why);
- a contiguous region of good neighboring parameters, not an isolated point;
- a clear understanding of whether the edge is `BOTH_SIDES_EDGE`,
  `LONG_ONLY_EDGE`, `SHORT_ONLY_EDGE`, or effectively `NO_STABLE_EDGE` (see
  "Long/short independence" below) — you do not need long and short to be
  equally profitable, but you must know which side(s) actually produce the
  result.

If this bar isn't cleared: either go back into Phase C with a different
structural axis or combination, or conclude the branch with `NO_EDGE_FOUND` (or
`STOP_OVERFIT_RISK` if the only positive results were isolated spikes — see Stop
conditions). Do not proceed to asymmetric optimization on a weak or unconfirmed
symmetric result; asymmetric SL/TP can make a weak entry *look* good by pure
payout skew, which is exactly the failure mode Phase B/D exist to prevent.

### Phase E — asymmetric SL/TP payoff optimization

Only after Phase D passes. Vary SL distance and TP distance independently
(reward/risk ratio becomes a derived quantity, not an input you pick first).
Coarse sweep first, batch experiment, then refine around promising regions —
same ridge-not-point discipline as every other phase. Always keep the Phase D
symmetric finalist as a labeled control candidate in these comparisons, so you
can tell whether asymmetric payout added real value or just increased variance
around the same underlying edge. Evaluate trade count, PF, net PnL, drawdown,
fees, and long/short split for every candidate under consideration, not just
PnL.

### Phase F — secondary filters

Only after a frozen static (symmetric-or-asymmetric, whichever the evidence
supports) candidate exists. Existing components only — RSI-based blockers,
ADX/DMI-based conditions, HTF contexts, other entry blockers or signal-exit
components already in the catalog. Add **one at a time** as an incremental
change against the exact frozen parent baseline; do not run a combinatorial
sweep of several new filters simultaneously before understanding each one's own
marginal contribution.

### Phase G — managed-exit research (late, separate)

Break-even shifts, protected phase, runner behavior, active stop/take
switching, and other managed-exit machinery must never be used to *establish*
entry edge — they belong strictly after a frozen static entry/exit candidate
exists. Maintain this boundary explicitly:

```
ENTRY EDGE FOUND  →  STATIC EXIT CANDIDATE FROZEN  →  MANAGED EXIT RESEARCH
```

Do not let a managed exit's complexity mask a weak entry earlier in the chain.

### Phase H — validation

Before calling anything final: check the finalist against parameter
perturbations one step away in every varied dimension; check performance on
distinct time subperiods within the same discovery-universe history (not a
different universe — see "Full history by default"); reconfirm long/short
attribution; if there's a second liquid, catalog-supported ticker available and
it's reasonable to check, do so; sanity-check sensitivity to the fee/slippage
assumptions used throughout. A single full-history winner is not, by itself,
sufficient evidence of robustness.

### Phase I — final research report

Summarize the whole chain: hypothesis, what was tested at each phase, what was
rejected and why, the final candidate (or the `NO_EDGE_FOUND` conclusion),
long/short attribution, stability evidence, validation results, and explicit
next steps if any. This is the terminal artifact of a research session — see
"Experiment journal" for the running version kept throughout, and produce a
clean final version here.

## Long/short independence

At every phase that matters (Phase A baseline, Phase B/D verdict, Phase E, Phase
F), report aggregate, long-only, and short-only results as three separate rows,
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
phase through Phase G. Every candidate inside one experiment is already forced
to share one window by `BatchExperimentRequest`'s own invariants — this rule is
about *experiment-to-experiment* consistency: don't compare a Phase C result
computed over one window against a Phase E result computed over a different
one. Subperiod / walk-forward / out-of-sample slicing is Phase H validation
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

- **`NO_EDGE_FOUND`** — several consecutive structural/filter searches (Phase
  C, or Phase F once reached) fail to produce a stable after-fee symmetric edge.
- **`STOP_OVERFIT_RISK`** — a positive result exists only at one narrow point
  and collapses at its immediate parameter neighbors.
- **`SYMMETRIC_EDGE_CONFIRMED`** — Phase D's gate criteria are met.
- **`STATIC_STRATEGY_CANDIDATE_FOUND`** — after Phase E (and, if used, Phase
  F), a robust, validated static candidate exists.
- **`READY_FOR_MANAGED_EXIT_RESEARCH`** — the static candidate is stable enough
  that Phase G is a reasonable next investment.

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
