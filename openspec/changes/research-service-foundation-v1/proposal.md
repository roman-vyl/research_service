# Proposal: Research Service foundation v1

## Why

The BBB research backend and Workbench BFF currently share a repository with strategy semantics, legacy market storage, frontend assets and generated research artifacts. A clean process boundary is required before replacing those internal calls with Strategy Engine and Market Data Service APIs.

## What changes

- create an installable `research_service` package;
- create a FastAPI application that owns the preserved Workbench BFF namespace;
- introduce Strategy Engine, Market Data Service and artifact-store ports;
- provide concrete HTTP/filesystem adapters and runtime wiring;
- preserve important legacy route paths while returning explicit `501 capability_not_ported` until each route is semantically ported;
- add health/readiness and architecture guards;
- do not port execution simulation or result semantics in this change.
