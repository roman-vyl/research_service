"""Counts and disk size of one Experiment (``research-experiment-storage-v1``).

Counts come from the result table held by the results cache. The size stats files of
the distinct referenced run folders and of the Experiment folder only: it never lists
the artifacts root, opens a run file or follows a symbolic link. Sizes are cached in
memory by the table key; nothing is written.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from research_service.adapters.experiments.filesystem import FilesystemExperiments
from research_service.adapters.experiments.run_deletion import _RUN_ID_RE, _folder_size

_CACHE_SIZE = 64

SizeMode = Literal["cached", "compute"]


class FilesystemExperimentStorage:
    def __init__(self, experiments: FilesystemExperiments, artifacts_root: Path) -> None:
        self._experiments = experiments
        self._runs = artifacts_root
        self._sizes: dict[tuple[str, int, int], dict[str, Any]] = {}
        self._lock = threading.Lock()

    def storage(self, experiment_id: str, size: SizeMode) -> dict[str, Any]:
        key, _schema, folder, run_ids = self._experiments.table_snapshot(experiment_id)
        present = [r for r in run_ids if r is not None]
        distinct = set(present)
        found = self._sizes.get(key)
        if found is None and size == "compute":
            with self._lock:
                found = self._sizes.get(key)
                if found is None:
                    found = self._compute(distinct, folder)
                    if len(self._sizes) >= _CACHE_SIZE:
                        self._sizes.pop(next(iter(self._sizes)))
                    self._sizes[key] = found
        return {
            "experiment_id": experiment_id,
            "rows": len(run_ids),
            "engine_runs": len(present),
            "distinct_run_ids": len(distinct),
            "size": dict(found) if found is not None else None,
        }

    def _compute(self, run_ids: set[str], experiment_folder: Path) -> dict[str, Any]:
        run_bytes = missing = 0
        for run_id in sorted(run_ids):
            folder = self._runs / run_id
            if not _RUN_ID_RE.fullmatch(run_id) or folder.is_symlink() or not folder.is_dir():
                missing += 1
                continue
            run_bytes += _folder_size(folder)[1]
        folder_bytes = _folder_size(experiment_folder)[1]
        return {
            "bytes": run_bytes + folder_bytes,
            "run_bytes": run_bytes,
            "experiment_folder_bytes": folder_bytes,
            "missing_runs": missing,
            "computed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
