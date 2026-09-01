## Why

BBB AutoResearch v1 correctly preserves negative evidence and prohibits PF/PnL leaderboards, but
its quality policy remains mostly qualitative. It does not yet provide a versioned, stage-aware
answer to four different questions: whether an experiment increased knowledge, whether a response
region is structurally promising, whether it is economically viable after costs, and whether it is
robust enough to carry forward.

Those questions cannot share one scalar gate. A losing structural sweep may map a useful response
function, while a profitable isolated spike may be unfit for promotion. Likewise, the same metric
has different scientific meaning during baseline measurement, neutral-exit entry discovery, exit
geometry research, and robustness validation.

## What Changes

- Define a versioned `ResearchQualityPolicy` resolved into each session, with explicit mappings from
  flexible research phase names to stable scientific stage kinds.
- Define a durable `ResearchQualityAssessment` separating information value, structural promise,
  economic viability, robustness, side classification, multi-metric trade-offs, and promotion
  disposition.
- Define phase-specific metric roles: descriptive facts, primary evidence, secondary/sanity
  evidence, and promotion gates.
- Make structural evidence, neighborhood support, configured threshold enforcement, and required
  validation explicit promotion semantics without inventing arbitrary numeric defaults; positive
  after-cost economics gates promotion out of exit-geometry research, not entry into it.
- Preserve worker interpretation and supervisor mechanical enforcement: the supervisor never ranks
  candidates or chooses a numeric winner.
- Require new enclosing AutoResearch contract versions when implemented rather than silently adding
  fields to the exact `bbb_autoresearch_state.v1` and `bbb_autoresearch_iteration.v1` schemas.

## Capability

### New Capability

- `autoresearch-research-quality-policy-v1`: stage-aware, multi-objective research-quality and
  promotion semantics above BBB AutoResearch's immutable canonical evaluator.

## Dependencies

- Depends on `bbb-autoresearch-v1` durable sessions, canonical batch references, explicit side/risk
  semantics, and no-scalar-leaderboard boundary.
- Consumes only the existing `research-batch-experiments-v1` candidate summary and canonical run
  artifacts. It adds no trading metric and changes no evaluator behavior.

## Impact

This change is specification-only. A later implementation may update AutoResearch program,
templates, schemas, supervisor validation, state advancement, journal projection, and tests.
Production packages under `src/research_service/`, Strategy Engine, Market Data Service, accounting,
execution, backtesting semantics, and the EMA research skill remain unchanged.
