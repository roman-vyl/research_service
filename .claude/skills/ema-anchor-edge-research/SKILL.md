---
name: ema-anchor-edge-research
description: "Research whether price interaction with an anchor EMA has a stable trading edge by testing market-state hypotheses, response functions, parameter interactions, and robustness. Use for EMA-anchor touch/pullback discovery; not for one-off backtests, infrastructure documentation, or strategy/component implementation."
---

# EMA anchor edge research

## Purpose and boundaries

Use this methodology to answer:

> Under which market states does price interaction with an anchor EMA have predictive or execution value, and is that value stable enough to matter?

The goal is not a winning parameter tuple. It is an interpretable, reproducible region of market states where the interaction behaves differently from the naked-anchor baseline. `NO_STABLE_EDGE` is a valid conclusion.

This is a research method, not documentation for Research Service, Strategy Engine, HTTP, persistence, or deployment. Inspect current code and live contracts for operations when a research run begins.

## Non-negotiable constraints

- Conduct independent research. When the task requires a fresh investigation, do not inspect previous winners, rankings, heatmaps, or reports. Prior artifacts may clarify a current data shape, never seed values or hypotheses.
- Do not hardcode EMA periods, thresholds, lookbacks, ATR distances, grid sizes, or historical winners. Derive search spaces from the supplied strategy specification, live component catalog, parameter meaning, and the current experiment.
- Use only components present in the current live catalog. If a hypothesis cannot be expressed, report the missing capability; do not invent trading logic or modify production code.
- State a market hypothesis before creating candidates. No random exploration or retrospective stories about winners.
- Compare regions, not isolated maxima. Preserve negative results and rejected regions.
- Keep entry discovery causally separate from exit optimization.

## Parameters are proxies for market state

Do not ask, “What is the magic value?” Ask:

> What market property does this parameter express, and does changing that property alter the conditional outcome of an anchor interaction?

Interpret only parameters confirmed in the live catalog. Examples, when such dimensions exist:

- **Untouched/freshness lookback** proxies how long price stayed away from the anchor, whether the return is first or rare, and whether fresh interaction differs from a repeatedly tested level.
- **Anchor-stack width** proxies trend organisation, EMA separation, compression versus expansion, structural maturity, and possible overextension at extreme separation.
- **Bounce count and bounce lookback** proxy the number, frequency, and temporal concentration of prior interactions. Repetition may confirm significance or exhaust the level.

These interpretations generate hypotheses; they are not canonical rules. Verify actual component semantics before using them.

## Hypothesis-first protocol

Before every sweep, record:

1. **Market phenomenon** — what behavior is expected?
2. **Proxy** — which live component and parameter express it?
3. **Confirmation** — what response shape or conditional result supports it?
4. **Refutation** — what observation weakens or rejects it?
5. **Confounder** — what alternative explanation could produce the result?

Reasoning examples, not strategy rules: “A fresh touch may be more valuable than a repeated touch when the EMA structure is organised”; “Bounce history may matter only at particular degrees of EMA separation.” Only then define an experiment that can discriminate between explanations.

## Causal sequence

1. Naked anchor baseline.
2. Independent structural entry discovery.
3. Structural interaction discovery.
4. Selection of a stable entry region.
5. Static exit geometry research.
6. Additional independently motivated filters.
7. Managed exits, if justified.
8. Robustness validation and report.

Do not optimize SL/TP to rescue an entry condition without structural value. During entry discovery, one fixed neutral static exit is a measurement instrument for comparable entries, not an optimization target.

## Phase A — naked-anchor baseline

Build the simplest valid anchor-interaction strategy from the supplied spec and live catalog. Add no structural filters. Use one fixed, reasoned symmetric static exit and keep it unchanged throughout structural discovery.

Establish aggregate, long, and short baseline behavior using at least:

- net result or return, plus gross result and fees when available;
- profit factor and win rate;
- maximum drawdown or a comparable risk measure;
- realised trade count.

Record whether the naked interaction is positive after costs, positive only before costs, indistinguishable from noise, or too thin to judge. It is the control every structural condition must explain.

## Phase B — discover the structural response

Phase B asks which market states make an anchor interaction useful. The Phase A exit stays fixed for every candidate.

### B1. Independent one-dimensional discovery

Test each meaningful structural dimension independently against the naked baseline. Write the response as `Q(x)`, where `Q` is a multi-metric assessment, not necessarily one scalar.

For each dimension:

1. justify a coarse, trading-plausible range from live schema and meaning;
2. run a comparable batch across the range;
3. inspect net result/return, PF, drawdown, trade count, win rate, and long/short;
4. choose the next points for their expected information value about response shape, refining a promising region only after enough exploration identifies what kind of shape would be exploited.

Do not select a final value. Determine whether a dependency exists, its direction and shape, promising and rejected intervals, and whether the dimension deserves more research.

### B2. Classify each 1D response

Classify meaningful `Q(x)` as one or more of:

- flat/absent effect; monotonic improvement or deterioration;
- threshold; plateau/broad optimum; narrow optimum;
- U-shape or inverted U-shape; multiple regimes;
- unstable/noisy spikes; boundary optimum.

A boundary optimum means the function is not localized on the tested domain. It does not automatically mean “extend the boundary” or “densify near the winner.” Choose hypothesis-discriminating points that can separate monotonic continuation, a threshold or plateau, an internal or inverted-U optimum, multiple regimes, and noise. Also ask when further movement loses trading meaning. Boundary exploration and refinement should maximize understanding of topology, not automate boundary chasing; this is an information-gain principle, not a formal optimizer.

### B3. Use 1D optima as landmarks

An independently promising interval is a search landmark, not a final setting. If `x` is promising in `X*` and `y` in `Y*`, next investigate `Q(x, y)` around `X* × Y*`; do not freeze the best x and y. Preserve plateaus and distinct regimes as regions.

### B4. Select interaction dimensions by meaning

Do not form a Cartesian product of available parameters. Add a dimension only if it measures a new market property and the hypothesis explains why it may condition the response.

If two parameters appear to proxy the same state, test redundancy, correlation, or conditional value before optimizing both. Prioritize interpretable structural interactions; complexity must be earned by evidence or a hypothesis stated before seeing the interaction result.

### B5. Conditional local two-dimensional search

Proceed to `Q(x, y)` when either both dimensions have meaningful independent 1D signal, or one has signal and a trading-plausible hypothesis stated before the 2D result says the other may matter only conditionally. For example, bounce may be marginal alone while a prior hypothesis predicts that repeated touches matter only at particular stack widths.

Do not build an interaction merely because parameters exist, search for a second dimension when neither evidence nor prior conditional hypothesis supports one, or invent the hypothesis after a favorable surface appears. Phase B may end with a robust 1D structural finding. When 2D is justified, build around promising regions rather than single points; cover meaningful plateaus and separate regimes where appropriate.

Keep the data window, execution assumptions, fixed exit, and metric definitions comparable so surface changes reflect entry structure.

### B6. Draw the response “blanket”

For every meaningful `Q(x, y)`, produce:

1. a 3D response surface — “draw the quality-function blanket”;
2. preferably a 2D heatmap of the same surface.

Use X and Y for structural parameters and Z for a hypothesis-relevant metric. When conclusions depend on trade-offs, inspect a small set of parallel surfaces such as PF, net return, drawdown, or trade count. Every plot must inform a decision.

### B7. Interpret surface topology

Topology matters more than the highest cell. Look for:

- broad plateaus, ridges, valleys, and diagonal ridges;
- isolated spikes, cliffs, and noisy checkerboards;
- smooth transitions, multiple regimes, and boundary-running optima.

Give geometry a trading interpretation. A diagonal ridge such as greater stack organisation paired with a weaker freshness requirement may suggest a conditional relationship between those properties. Report it as a hypothesis supported by response geometry, not proven causality.

### B8. Ridge, not point

A promising 2D region must tolerate perturbation along X, Y, and preferably both simultaneously. A high cell surrounded by poor cells is suspect. Prefer an interior representative of a broad elevated region over an absolute maximum at its edge.

Economic outcome, risk, sample size, and side behavior must remain qualitatively acceptable in the neighborhood. Stability in one metric alone is insufficient.

### B9. Optional third dimension

Add a third parameter only if it has its own 1D signal, distinct trading meaning, and a plausible interaction with the discovered 2D structure.

Do not reduce it to gigantic grid ranking. Prefer slices such as `Q(x, y | z = z₁)`, `Q(x, y | z = z₂)`, and `Q(x, y | z = z₃)`. Ask whether the ridge appears, disappears, moves, widens, narrows, or changes by side. The third dimension should explain an existing structure, not create more chances for a winner.

## Phase C — select a stable entry region

Carry forward regions, not leaderboard rows. A credible region needs:

- economically relevant after-cost outcome and controlled risk versus baseline;
- meaningful trade count rather than statistical thinning;
- neighborhood stability across important dimensions;
- explicit aggregate/long/short interpretation;
- plausible market-state meaning and a competing explanation.

If only isolated peaks survive, stop for overfit risk. If no structural region credibly improves the baseline, report `NO_STABLE_EDGE` rather than tuning exits.

## Later phases

Only after Phase C research static exits: first symmetric distance locally, then asymmetric SL/TP only if justified. Keep a stable structural candidate and symmetric control; judge response regions rather than payout-skew winners.

Add secondary filters one at a time, each with a prior hypothesis about a new market property. Do not add filters after viewing winners merely because they improve in-sample PnL. Managed exits come only after a robust static candidate and must not establish or disguise entry edge.

## Multi-metric and side-aware reasoning

Never reduce quality to PF, PnL, or win rate alone, and do not invent a weighted score without need. For every promising region reason across:

- economic outcome and costs;
- drawdown and other relevant risk;
- trade count and concentration;
- aggregate, long-only, and short-only behavior;
- stability under neighboring parameters.

PF rising while trade count collapses may be statistical thinning; return rising with sharply worse drawdown may be a worse trade-off. A good aggregate result entirely on one side may be directional regime, not a general anchor edge.

For every meaningful improvement ask whether it is specific to the market-state proxy or merely generic thinning, temporal concentration, or broad regime selection. If trade count falls materially versus baseline, inspect concentration through time, by long/short, and by regime when a reasonable diagnostic exists; also require neighboring-parameter stability and persistence on validation windows. Do not confirm structural edge when selecting a small favorable historical segment explains the result equally well.

Compare `Q(x)` shape and `Q(x, y)` topology separately for long and short. Asymmetry is not automatically bad, but label it honestly; do not call a one-sided finding universal.

## Controlled A→B causal ladder

For the controlled A→B programme, treat Phase A as an operator-configured naked-anchor reference
line of independent symmetric measurement geometries, not exit optimization. Study B1 width and B2
untouched lookback independently against the identical referenced geometry; B2 resets to the naked
strategy rather than carrying B1 forward. Only after both one-dimensional questions are
sufficiently characterized or terminally rejected may width×lookback B3 be considered. B3 is
scientifically optional: preserve `NO_STABLE_EDGE` when an interaction experiment is not justified.

## Mandatory reasoning checkpoint

After every meaningful experiment answer:

1. What changed?
2. What market property did the proxy attempt to measure?
3. Why is the observed shape economically plausible?
4. What alternative explanation remains?
5. Could thinning or temporal/directional/regime concentration explain the improvement?
6. Which next experiment has the greatest information value for discriminating between explanations or response shapes?

The next experiment must follow from these answers. Selection says what worked; causal explanation remains a hypothesis until discriminating evidence supports it.

## Overfitting defenses

Reject or discount isolated best points, excessive grids, repeated boundary chasing, parameter explosion, retrospective hypotheses, tiny or generically thinned samples, temporal/regime concentration, aggregate results masking side failure, and filters chosen after inspecting winners.

Prefer broad stable regions, smooth reproducible topology, meaningful samples, interpretable interactions, and negative results that remain negative under reasonable perturbation.

## Validate the discovered region

Depending on available data, test adjacent parameter perturbations, temporal holdout, regime splits, long/short, another suitable ticker, and other reasonable windows not reused for discovery.

Ask whether the *shape* persists. A ridge may move across periods while preserving its structural relationship; that is stronger evidence than exact repetition of one best tuple. Report topology changes and failures as well as successes.

## Research journal

Store knowledge, not request/response logs. After each experiment record:

```text
HYPOTHESIS
WHAT_MARKET_PROPERTY_IS_BEING_PROXIED
DIMENSIONS_TESTED
RANGES_TESTED
OBSERVED_RESPONSE_SHAPE
PROMISING_REGION
REJECTED_REGION
LONG_SHORT_DIFFERENCE
ALTERNATIVE_EXPLANATION
NEXT_DISCRIMINATING_EXPERIMENT
CURRENT_STRUCTURAL_HYPOTHESIS
```

Keep exact specs, data windows, code revision, technical identifiers, and result locations as reproducibility metadata, not the journal's substance. Never delete negative experiments.

## Final report

Answer:

1. Was a stable EMA-anchor edge found, and which market state is associated with it?
2. Which dimensions mattered, and what were their 1D response shapes?
3. Which interactions appeared in the 2D surface?
4. Was there a broad ridge/plateau or only an isolated peak?
5. How did aggregate, long, and short differ?
6. Did response topology survive validation?
7. Which regions and hypotheses were rejected?
8. What remains unknown, and which next experiment has highest information value?

A parameter tuple may appear as a representative configuration inside a stable region, never as the main scientific conclusion.

## Minimal operational discipline

- Before running, inspect the live component catalog, current strategy spec, production contracts, and available research capabilities. Current code is authoritative.
- Prefer current batch comparison for candidates sharing a window; do not launch many independent heavy backtests when batch capability exists.
- Keep candidates comparable and preserve enough metadata and results for reproducibility.
- Confirm component semantics and validate specs before spending a batch. Never use an old winner as an unspoken prior.
- Do not begin compute-intensive research without an explicit research request. Invoking this skill alone does not authorize a parameter sweep.
