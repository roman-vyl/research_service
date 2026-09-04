# BBB AutoResearch — trading and research memory

This file is not technical documentation. It intentionally says nothing about current classes,
functions, schemas, CLI commands, endpoints, state fields, or implementation details — any agent
working on the codebase must inspect current code and live contracts for that. What this file
preserves is longer-lived: the trading question BBB AutoResearch exists to answer, and why.

## What AutoResearch is

BBB AutoResearch is inspired by Andrej Karpathy's autoresearch idea: a deterministic Python harness
runs research and backtests, while an LLM plays the role of the researcher. The loop is roughly:

```
LLM researcher
  -> formulates the next experiment
  -> deterministic harness executes the backtest
  -> LLM analyzes the result
  -> formulates the next experiment
  -> ...
```

The harness is responsible for mechanical, reproducible execution. The LLM is supposed to think
like a trader-researcher: understand the trading meaning of parameters, build hypotheses, choose
interesting ranges to explore, read the response surface, and decide where the research goes next.

## Trading thesis

We are researching a trend-following / pullback idea built around EMAs.

The core intuition is simple. When a real directional trend starts, price moves away from its
average value. As it does, EMAs of different speeds start to separate:

```
fast EMA
anchor EMA
slow EMA
```

One example configuration under research: EMA100 as fast, EMA200 as anchor, EMA500 as slow. In an
uptrend, fast sits above anchor, anchor above slow; in a downtrend, the reverse.

But EMA ordering itself is not the idea. The trading idea is: if the market truly made a strong
directional move, price should first travel meaningfully away from the anchor EMA, and then at some
point pull back to it. We want to take a trade around that return to anchor, in the direction of the
original trend — a continuation trade after a correction to the mean, not a breakout or an impulse
entry.

Long, schematically:

```
strong upward impulse
        ^
        ^
        ^
        |
        |
      price
        \
         \
          \   pullback
           \
------------- anchor EMA
              ^
       candidate long entry
```

Short is the mirror image.

## Why a bare EMA touch is not a strategy

Price touches an EMA constantly. In a flat or weak market it can cross the same average back and
forth many times in a short window — pure noise. If we buy every touch of the anchor in a nominal
long stack and sell every touch in a nominal short stack, we are largely just trading that noise.

So a naked anchor touch is a control, not a finished edge. The real research question is:

> How do we tell a return to EMA inside a genuinely strong trend apart from a random touch in
> noise, a weak move, or an already-decaying trend?

We are looking for measurable market-structure properties that let us make that distinction.

## Idea one — EMA stack width

One important signal is the distance between fast, anchor, and slow EMA. EMAs sitting close
together mean the market either hasn't traveled far directionally, or the trend structure is weak.
EMAs clearly separated mean price history has already produced meaningful directional separation
between the averages.

So EMA stack width is a direct, measurable proxy for how strong / mature the trend structure is. It
usually needs to be normalized against volatility (e.g. ATR), since the same absolute EMA distance
means something different on BTC across very different volatility regimes.

Main hypothesis: the more developed the trend was before the pullback, the more likely a return to
the anchor EMA is a correction within the trend rather than a random touch or the start of a
reversal. This is a hypothesis to test, not an assumed truth — the real dependency could be
monotonic, threshold-like, plateaued, have an optimal interior range, degrade at extreme width, be
regime-dependent, or simply be absent. A very large width can look great in backtest purely because
it leaves a few hundred extreme trend situations instead of several thousand trades — so the
researcher must distinguish genuine setup-quality improvement from plain thinning of the sample.
This distinction is one of the central research tasks.

## Idea two — untouched-anchor lookback

The second key parameter answers roughly: how long ago did price last touch this anchor EMA? It
carries two related trading meanings.

**1. Noise filter.** If price touched EMA200 ten times in the last hour, we are almost certainly not
looking at a clean correction inside a strong trend — we're looking at a market sawing through the
average. A minimum untouched lookback filters out situations where price is constantly near the
anchor. If price hasn't touched the EMA for, say, 50 or 100 bars, the market genuinely lived on one
side of it for a while and is now returning for the first time — a different market event.

**2. Freshness of the touch.** In a strong uptrend, price stays above EMA200 for a while, then
returns to it for the first time. If the trend is genuinely strong, buyers should show up near the
anchor and push price back up. If instead price returns to the EMA again a few bars later, that's
different information: the first bounce wasn't strong enough to keep the market away from the
average for long. If a third, fourth, fifth quick touch follows, the intuitive probability that the
anchor eventually breaks increases.

So the hypothesis: a fresh first touch of the EMA after a long absence of contact is potentially
higher quality than a rapid repeat touch. A very strong trend can still survive several touches, so
we can't say up front that the second or third touch is always bad — but on average, freshness
likely carries information about how intact the trend still is. Untouched-anchor lookback is a
parameter with concrete market meaning, not an arbitrary tuning knob.

## Why width and lookback should be studied together

These two filters describe different sides of the same phenomenon. Width answers: how developed was
the trend structure? Lookback answers: how separated and fresh is the current return to anchor?

You can have a large lookback with a weak stack. You can have a wide stack with price that's already
tested the anchor several times in quick succession. The most interesting hypothesis is that a good
pullback may require both a sufficiently wide EMA stack *and* a sufficiently fresh anchor touch at
the same time. Study the parameters independently first to understand their own effect, then jointly
to see the interaction — a weak solo effect for one parameter doesn't mean their interaction is
necessarily weak too.

## What we are actually looking for

The goal is not to land on a pretty number like "width = 7.25 ATR, lookback = 83 bars" just because
that exact combination happened to produce the best historical PnL. We are looking for parameter
regions that correspond to a stable market meaning — a threshold, a plateau, a robust region, an
interaction region, a degradation boundary, regime dependence — which matters more than a single
best point estimate. If neighboring values (6, 7, 8, 9) all give a similar positive effect, that is
far more interesting than one lucky spike at 7.35. We want a region where the market behaves in a
systematically identifiable way.

## Parameter search and backtest

Many parameters have known trading meaning but unknown correct scale: is a stack "wide" at 2 ATR? 4?
8? Should the EMA stay untouched for 20 bars, 50, 100, 300? Logic alone can't answer that — it has to
come from historical data. AutoResearch uses backtest as the experimental apparatus: the LLM forms
hypotheses and candidate regions, the harness runs them against history, and the LLM updates its
understanding of where the interesting structure lives.

Search may later use coarse-to-fine refinement, Bayesian optimization, or other efficient methods
over a multi-dimensional parameter space — but the point of that search is not to maximize fit to
historical PnL. It's to efficiently explore a large parameter space and localize stable regions that
can then be checked more rigorously. Backtest is our observed quality function, but it always carries
overfitting risk: one narrow maximum is weak evidence, while a broad, economically/tradingly
interpretable, and reproducible-across-history region is much more convincing.

## How the researcher should think

The scientific LLM should keep asking not "which candidate made the most money?" but "what does this
result say about market behavior?" For example, if PF rises steadily from width 2 to width 10 while
trade count drops from 5000 to 500, the right questions are: does stronger trend structure really
improve anchor-touch quality, or is this thinning? Is the effect distributed across history, or did
it come from a few huge BTC trends? Do long and short behave the same way? Does the effect continue
past the current tested boundary, or plateau? Is there an interaction with untouched lookback? The
next experiment should aim to discriminate between competing explanations, not just chase a more
profitable parameter point.

## Long and short

Aggregate results alone are not enough. BTC has had long directional regimes historically, so a
strategy can look good only because one side happened to align with a long-run market move. The
researcher must track long, short, and aggregate behavior separately. It's especially notable when
the same structural condition improves both long and short — that's much stronger support for a real
trend/pullback property than a result that only exists on one side. But asymmetry is itself a
legitimate finding and shouldn't automatically be treated as an error.

## Costs and real edge

High trade frequency can erase a weak edge through fees. A strategy with near-zero gross expectancy
before costs almost certainly won't be useful after real execution. Structural filters can help not
only by raising average trade quality but also by removing a large volume of low-quality noise
entries — though a lower trade count alone is not proof of improvement. Always look together at trade
count, gross performance, costs, net performance, profit factor, win/loss structure, long/short
behavior, and stability across neighboring parameters.

## The central research question

Everything reduces to one question: can observable market structure distinguish a genuine-quality
pullback to the anchor EMA inside a live trend from a random EMA touch, or from a moment where the
trend is already breaking down?

Width, untouched lookback, and any future parameters are not ends in themselves — they are attempts
to measure a hidden market state: is this still a healthy trend temporarily pulling back to its
anchor, or is this just noise, exhaustion, or transition? If we can answer that well enough before
entry, anchor-touch can become a real trading edge.

---

Before any future architectural work, first read the current repository code. This file is not a
technical specification — its purpose is to preserve the trading hypothesis and the meaning of the
research. Do not let technical refactoring silently change the scientific question AutoResearch is
trying to answer.
