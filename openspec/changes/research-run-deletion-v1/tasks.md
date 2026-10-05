## 1. Research Service

- [ ] 1.1 Confirm that `/data/analysis` (the Experiment folders) is writable by Research Service in the compose stack; if not, record the mount change needed. No new setting.
- [ ] 1.2 Deletion adapter: deletable/skipped classification (id pattern, referenced by this table, not by another registered table), file and byte counts, plan token (run ids + table hash), table backup, folder removal (missing is fine), atomic rewrite with only `run_id` cells changed, journal line.
- [ ] 1.3 `POST .../runs/delete-plan` and `POST .../runs/delete` with `plan_stale` (409) and stable errors; request and response shapes as in `design.md`.
- [ ] 1.4 Tests on small fixture Experiments: counts and skipped reasons, shared run, stale token after table or selection change, other cells byte-identical, run list still valid, deleted run 404, already absent run, repeat after partial removal, backup and journal written, read routes and `/api/research/runs*` tests unchanged.
- [ ] 1.5 Measure plan time for a table of 12 672 referenced runs on the local data (read-only plan, nothing deleted).

## 2. Verification on real data (Mac, only on explicit command)

- [ ] 2.1 Plan on one real Surface with a small selection; compare counts and bytes with `du`.
- [ ] 2.2 Delete the small selection; check that Surface values are unchanged, Open run is unavailable for those points, `GET /api/research/runs` and Workbench work, space is freed, backup and journal exist.

## 3. Out of Scope (recorded)

Frontend selection UI and confirmation dialogs (`research_frontend` change), Calculate
runs and `materialize`, trash, undo.
