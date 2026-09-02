# AutoResearch Strategy Specification Reference

This is a **navigation/explanation layer**, not a second contract. It answers exactly one
question: *how is a `ema_pullback` strategy specification structured, and where do I find the
components currently available to configure it?* It does not define, extend, or restate strategy
semantics — that ownership stays exactly where it already is:

```
Strategy Engine            = authoritative raw_spec semantics (component legality, required
                              fields, static-semantic validity)
Engine Composer Catalog    = authoritative component availability / parameter schemas
This document              = worker-facing navigation only
Research -> Engine
  config validation        = authoritative fail-closed acceptance gate
```

If anything here ever appears to disagree with a live catalog response or a validation error,
the catalog and the validator are correct and this document is stale — report the discrepancy
rather than trusting this file over them.

## 1. Where to get the current component list and parameter schemas

Do not guess `component_id`s or parameter names, and do not read Strategy Engine or Market Data
Service source code to find them. Use the sanctioned Research Service endpoint, which proxies
Strategy Engine's own Composer catalog (Engine-owned, live, authoritative for this purpose):

```
GET /api/research/component-catalog?strategy_id=ema_pullback
```

The response lists every currently supported `component_id` per role (`direction`, `setup`,
`trigger`, `blockers`, `exits`, `risk`, `exit_management`) together with its `params_schema`
(field names, types, bounds, defaults). If a component you want to use is not in this catalog, it
does not exist yet in production — do not invent one.

## 2. The canonical strategy-specification shape

A submitted strategy instance has exactly this top-level envelope:

```
{ enabled, strategy_id, ticker, base_timeframe, raw_spec }
```

`raw_spec` is where every strategy-semantic component lives. Its top-level sections, and where
each catalog role is configured inside it:

| `raw_spec` section | Holds |
| --- | --- |
| `anchor_stack.{fast,anchor,slow}` | The three EMA definitions the strategy is built on |
| `trade_sides.enabled` | Which of `long`/`short` are active |
| `components.direction` | The `direction`-role component |
| `components.blockers[]` | A list of `blockers`-role component instances |
| `components.trigger` | The `trigger`-role component |
| `components.risk` | The `risk`-role component |
| `setups[]` | A list of `setup`-role component instances |
| `contexts` | Named higher-timeframe context providers, if used |
| `trade_management.exit_policy.always_on.exits[]` | Exit rules active regardless of profile |
| `trade_management.exit_policy.profiles.{aligned,countertrend,neutral}.exits[]` | Profile-scoped exit rules |
| `trade_management.exit_management` | Managed-exit configuration, if used |

Each entry in `components.blockers[]`, `setups[]`, and every `...exits[]` list is one **rule
instance**: an object with (at minimum) a `component_id` and, per the identity rule below, an
`instance_id`.

## 3. `component_id` vs `instance_id` — do not confuse them

- **`component_id`** selects *behavior* — which entry from the live catalog this rule instance
  runs. It comes from the catalog response in §1.
- **`instance_id`** is that specific rule's *identity* — a caller-assigned string that has no
  catalog entry and is not a behavior choice.

For every setup, blocker, and exit rule, `instance_id` is **mandatory, must be non-empty, and
must be unique** within its own kind (setups unique among all setups; blockers unique among all
blockers; exit rules unique across `always_on` and all three profiles combined — not just within
one group). This is enforced fail-closed by Strategy Engine's authoritative static-semantic
validator (see §5) — a request that omits it, empties it, or duplicates it is rejected before
any evaluation runs, never silently accepted.

**When modifying an existing rule instance across iterations, keep its `instance_id` exactly as
it was.** Do not invent a new one, drop it, or let it default to the `component_id` — an
`instance_id` change on what is meant to be the same rule breaks continuity (context-consumption
gating, prior evidence references, and duplicate-detection all key off it) even when the
`component_id` and parameters stay the same.

## 4. The authoritative acceptance gate

Before treating any constructed or modified strategy specification as usable, submit it through
the existing canonical Research validation path:

```
POST /api/research/config/validate
```

This delegates strategy-semantic checking to Strategy Engine's authoring-config validation —
the single authoritative, fail-closed source of truth for whether a `raw_spec` is valid. A
`valid=true`/`ok=true` result means the specification is free of static, market-data-independent
semantic errors (unsupported `component_id`, missing/duplicate `instance_id`, malformed
structure). It does not evaluate market-data availability, runtime state, or the strategy's
eventual numeric result.

Do not treat this document, the catalog, or memory of a prior iteration's success as a substitute
for this check. Use the validator to confirm correctness, not to discover syntax by trial and
error — read this document and the live catalog first, so validation failures are the exception,
not the primary way of learning the format.

## 5. Normative source, for traceability

The exact invariants enforced above are formally defined in Strategy Engine's OpenSpec capability
`ema-pullback-authoring-config-validation-v1` (in the Strategy Engine repository). This document
summarizes that contract for navigation; it does not replace it, and Strategy Engine's own
validator response is always the deciding authority, not this text.

## What this document does not cover

This reference does not tell you what to research, which research stage you are in, which
`raw_spec` fields are currently mutable versus locked for this session, which parameter ranges are
reasonable to explore, or which metrics matter for promotion. Those come from the current research
program, skill, and session state — not from this file.
