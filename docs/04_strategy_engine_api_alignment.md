# Strategy Engine API alignment

## Coarse evaluation call

Research Service should call `POST /v1/strategy-evaluations/range` with:

- strategy envelope/spec;
- canonical ticker;
- base timeframe;
- aligned half-open range;
- instance/variant identity and output requirements.

It receives the strategy-owned artifact:

- feature series and mappings;
- contexts and side-relative context consumption;
- direction, blocker, setup, trigger and risk evidence;
- final entry masks;
- standard exit masks and relative stop/take distances;
- hashes, warnings and validity metadata.

## Batch call

`POST /v1/strategy-evaluations/range-batch` is used when variants share one market range. Semantically it is multiple range evaluations, but it permits market and feature reuse inside Strategy Engine.

## Managed policy

`POST /v1/strategy-evaluations/managed-replay` returns policy decisions for an already-open logical trade. Research Service still owns OHLC fill arbitration and resulting trade lifecycle.

## Catalog/config

Research Service adapts Strategy Engine catalogs and validation errors to existing Composer contracts. It does not maintain a second authoritative strategy schema.

## Compatibility gate

For offline parity acceptance, frozen BBB reference fixtures and the remote Strategy Engine result must be compared for the same config/range:

- config hash;
- market identity/range;
- entries and exits;
- stop/take distances;
- component evidence needed by diagnostics;
- managed decisions where applicable.
