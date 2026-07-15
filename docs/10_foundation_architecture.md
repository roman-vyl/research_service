# Research Service foundation architecture

The first production package is intentionally small. It owns the FastAPI/BFF process boundary, external service ports, artifact storage and runtime wiring. Existing browser route paths are registered immediately, but incomplete capabilities return explicit HTTP 501 responses.

```text
Research Workbench
  -> Research Service FastAPI
       -> Strategy Engine HTTP client
       -> Market Data Service HTTP client
       -> filesystem artifact volume
```

No production import reaches `legacy_source`. Later OpenSpec changes port one BFF/research capability at a time behind these boundaries.
