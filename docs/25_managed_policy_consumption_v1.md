# Managed Policy Consumption v1

## Purpose

Consume the authoritative managed-policy replay produced by Strategy Engine and convert it into Research-owned executable candidates without recalculating phases, stop rules, take switches, or runtime exits.

## Seam

Legacy BBB combined policy evaluation and execution inside `ManagedExitProvider` and `run_managed_execution_loop`.

The new seam is:

```text
Strategy Engine managed replay
  - phase
  - active managed stop
  - active take profile
  - active runtime exits
  - end-of-bar effective timing

Research Service
  - inherit state on the next bar
  - detect OHLC hits
  - create managed exit candidates
  - preserve rule/component attribution
```

## Timing

A decision produced at the end of bar N is only executable from bar N+1. `ManagedPolicyTimeline` indexes states by `effective_from_time_ms`; no state exists for the source bar itself.

## Implemented contracts

- `ManagedEffectiveState`
- `ManagedPolicyTimeline`
- `build_managed_policy_timeline()`
- `collect_managed_exit_candidates()`

## Candidate semantics

- managed stop: gap-through fills at bar open, intrabar touch fills at stop level;
- runtime protective exit: `runtime_protective`;
- runtime take exit: `runtime_take`;
- market-close and other runtime exits: `runtime_close`, filled at bar close.

`active_take_profile` is carried as authoritative policy state. It is not interpreted into a take candidate in this slice; that happens when static and managed candidates are unified.

## Non-goals

This slice does not:

- evaluate managed phases or rules;
- arbitrate static and managed candidates together;
- close positions;
- calculate fees or PnL;
- persist trade artifacts.
