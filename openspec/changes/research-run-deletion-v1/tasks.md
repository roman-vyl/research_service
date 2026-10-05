## 1. Research Service

- [x] 1.1 Confirm that `/data/analysis` (the Experiment folders) is writable by Research Service in the compose stack; if not, record the mount change needed. No new setting. Checked in `bbb_stack` (`docker-compose.yml`): `research-service` mounts `${BBB_DATA_ROOT}/research` at `/data` as a bind mount without `read_only`; `read_only: true` is set only on the container root filesystem; `docker-compose.deploy.yml` overrides only the image. So `/data/analysis` is writable by configuration. Host-side file permissions on the Mac are not visible from here and are covered by 2.2.
- [x] 1.2 Deletion adapter: deletable/skipped classification (id pattern, referenced by this table, not by another registered table), file and byte counts, plan token (run ids + table hash), table backup, folder removal (missing is fine), atomic rewrite with only `run_id` cells changed, journal line.
- [x] 1.3 `POST .../runs/delete-plan` and `POST .../runs/delete` with `plan_stale` (409) and stable errors; request and response shapes as in `design.md`.
- [x] 1.4 Tests on small fixture Experiments: counts and skipped reasons, shared run, stale token after table or selection change, other cells byte-identical, run list still valid, deleted run 404, already absent run, repeat after partial removal, backup and journal written, read routes and `/api/research/runs*` tests unchanged.
- [x] 1.5 Measure plan time for a table of 12 672 referenced runs. Measured on a synthetic tree of 12 672 runs × 7 files (88 704 files, 177 MB) in a temporary directory: plan 0.86 s; delete of the same selection 8.6 s. Not measured on the real local data (it is not in the cloud container); 2.1 reports the real plan time.

## 2. Verification on real data (Mac, only on explicit command)

- [ ] 2.1 Plan on one real Surface with a small selection; compare counts and bytes with `du`.
- [ ] 2.2 Delete the small selection; check that Surface values are unchanged, Open run is unavailable for those points, `GET /api/research/runs` and Workbench work, space is freed, backup and journal exist.

## 3. Out of Scope (recorded)

Frontend selection UI and confirmation dialogs (`research_frontend` change), Calculate
runs and `materialize`, trash, undo.
