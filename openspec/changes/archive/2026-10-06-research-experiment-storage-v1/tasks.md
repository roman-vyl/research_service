## 1. Research Service

- [x] 1.1 `FilesystemExperiments`: expose the cached table, its key, schema and Experiment folder for one Experiment.
- [x] 1.2 Storage adapter: counts from the table; size by `lstat` over distinct referenced run folders (pattern check, no symlinks, missing counted) plus the Experiment folder; in-memory cache by table key; compute under a lock.
- [x] 1.3 Route `GET /api/research/experiments/{experiment_id}/storage?size=cached|compute`; 404 unknown Experiment, 422 invalid `size`.
- [x] 1.4 Tests on fixture Experiments: counts, cached before compute is `null` and reads no run folder, compute sizes, missing and invalid run ids, symlink not followed, cache hit, cache miss after a deletion, shared run counted in both, 404, 422, no write.

## 2. Verification on the stack (only on explicit command)

- [ ] 2.1 After deploy, `size=compute` for one Surface matches `du -s` of its run folders plus its folder within rounding; `size=cached` answers at once.
