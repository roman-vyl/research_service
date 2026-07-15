# Research Workbench extraction plan

## Decision

Frontend is a separate repository and Docker image named `research_workbench`.

## Raw source

The complete BBB `frontend/` directory is copied into `/mnt/data/research_workbench/legacy_source/bbb/frontend/` with SHA-256 provenance.

## Target package

```text
research_workbench/
├── src/
├── e2e/
├── scripts/
├── package.json
├── package-lock.json
├── vite.config.ts
├── vitest.config.ts
├── playwright.config.ts
├── Dockerfile
└── nginx.conf
```

## Contract

- browser uses `VITE_API_BASE_URL`;
- browser calls only Research Service BFF routes;
- TypeScript API DTOs remain stable during backend cutover;
- no MDS/Strategy Engine credentials or service URLs in browser configuration.

## Migration order

1. copy frontend unchanged;
2. make build/test run in independent repository;
3. point development environment to Research Service;
4. run existing unit and Playwright tests;
5. only later clean legacy/deprecated frontend paths.
