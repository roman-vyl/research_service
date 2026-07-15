# Tasks: Research Market Candles Window v1

- [x] Audit the legacy router, DTO, parameter resolver, reader and tests.
- [x] Add Workbench `ChartBar`, `CandlesWindowCoverage` and `CandlesWindowBundle` contracts.
- [x] Add legacy symbol to canonical `.P` ticker translation.
- [x] Preserve `to` versus `to_open_time_ms` resolution.
- [x] Add the `GetCandlesWindow` application use case.
- [x] Register the real market route and remove its preserved `501` placeholder.
- [x] Reuse the existing MDS port/client and complete-grid validation.
- [x] Map MDS unavailability to HTTP 503.
- [x] Add DTO, symbol, range and HTTP acceptance tests.
- [x] Document the intentional no-partial-response behavior.
- [x] Run repository verification and clean-install verification.
