"""Per-Experiment write lock shared by every writer of a result table.

Run deletion and Calculate publish both rewrite the same table; one process
serves the API, so an in-process lock per Experiment is enough.
"""

from __future__ import annotations

import threading

_GUARD = threading.Lock()
_LOCKS: dict[str, threading.Lock] = {}


def experiment_lock(experiment_id: str) -> threading.Lock:
    with _GUARD:
        lock = _LOCKS.get(experiment_id)
        if lock is None:
            lock = _LOCKS[experiment_id] = threading.Lock()
        return lock
