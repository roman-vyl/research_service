# Initial physical copy manifest

## Research Service immutable source

Copied from `project_snapshot_20260711.zip`:

- `research/` excluding `research/results/` and `research/experiments/results/`;
- `research_api/`;
- `tests/`;
- root `README.md` and `pyproject.toml`.

The copy is immutable reference material under `legacy_source/bbb`. Production code must be created under `src/research_service` and must not import legacy modules.

See `legacy_source/bbb/copy_manifest.json` and `docs/08_backend_source_inventory.csv`.

## Research Workbench immutable source

The full `frontend/` directory was copied to the separate `research_workbench` scaffold. See its copy manifest and inventory.
