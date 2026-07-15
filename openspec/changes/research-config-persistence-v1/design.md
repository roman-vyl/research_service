# Design

## Ownership

Research Service owns the config envelope, deterministic serialization, atomic filesystem persistence,
listing, selection, and corrupt-file isolation. Strategy Engine owns strategy authoring validation.

## API

- `POST /api/research/config/validate`
- `POST /api/research/config/serialize?format=json|yaml`
- `POST /api/research/config/save`
- `GET /api/research/configs/state?family=...`
- `PUT /api/research/configs/selected`

## Persistence

Configs are stored under `RESEARCH_CONFIGS_ROOT/<family>/<experiment_id>.json`. Selection is stored
atomically in `.workbench_selection.json`. Writes use temporary files, `fsync`, and `os.replace`.
Invalid or corrupt saved files may be listed but are never loaded as executable drafts.
