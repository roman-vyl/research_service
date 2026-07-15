# Legacy reference policy

`legacy_source/bbb/` is a read-only mirror used to inspect the original research implementation while building the new service.

It is allowed only for audits, extraction work, provenance checks and frozen parity fixtures. It must never be imported by `src/research_service`, wired into FastAPI, executed as a fallback, or included in the service dependency graph.

Research Service is an independent authoritative backend that calls Strategy Engine and Market Data Service through explicit ports and HTTP adapters.
