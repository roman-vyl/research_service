# Research Run Artifacts v1 Specification

## Requirements

1. A completed backtest SHALL be persisted under `<artifacts_root>/<run_id>/`.
2. Publication SHALL be atomic at directory level.
3. A run ID SHALL be immutable after publication.
4. The manifest SHALL identify all non-manifest files by relative path, SHA-256 and byte size.
5. The bundle SHALL retain the exact request, Strategy Engine evaluation, execution events, realised trades, metrics and full result.
6. An open position SHALL remain represented in `result.json`; persistence SHALL NOT force an exit.
7. Production code SHALL NOT import or execute `legacy_source`.
