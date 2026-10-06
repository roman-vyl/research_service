"""Delete the runs of one Experiment and clear their ``run_id`` in its table.

Best-effort and safe to repeat (``research-run-deletion-v1``): plan, then apply with
the plan token. Apply copies the table, removes each run folder whole (a missing
folder is not an error), rewrites the table atomically with only the selected
``run_id`` cells emptied, and appends a journal line. There is no transaction.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_service.adapters.experiments.filesystem import FilesystemExperiments
from research_service.adapters.experiments.locks import experiment_lock
from research_service.domain.errors import InvalidExperiment, InvalidRequest, PlanStale

JOURNAL_FILE = "runs_deleted.jsonl"
_RUN_ID_RE = re.compile(r"^run_[0-9a-f]{32}$")


class FilesystemRunDeletion:
    def __init__(self, experiments: FilesystemExperiments, artifacts_root: Path) -> None:
        self._experiments = experiments
        self._runs = artifacts_root

    # --- plan ------------------------------------------------------------------

    def plan(self, experiment_id: str, run_ids: list[str]) -> dict[str, Any]:
        if not run_ids:
            raise InvalidRequest("run_ids must not be empty")
        table, column = self._table(experiment_id)
        referenced = _run_ids_in(experiment_id, table, column)
        shared = self._ids_of_other_experiments(experiment_id)
        deletable: list[str] = []
        skipped: list[dict[str, str]] = []
        file_count = total_bytes = absent = 0
        for run_id in sorted(set(run_ids)):
            reason = self._skip_reason(run_id, referenced, shared)
            if reason is not None:
                skipped.append({"run_id": run_id, "reason": reason})
                continue
            deletable.append(run_id)
            folder = self._runs / run_id
            if not folder.exists():
                absent += 1
                continue
            files, size = _folder_size(folder)
            file_count += files
            total_bytes += size
        return {
            "run_count": len(deletable),
            "file_count": file_count,
            "bytes": total_bytes,
            "already_absent": absent,
            "skipped": skipped,
            "plan_token": _token(deletable, _sha256(table)),
        }

    def _skip_reason(self, run_id: str, referenced: set[str], shared: set[str]) -> str | None:
        if not _RUN_ID_RE.fullmatch(run_id):
            return "invalid_run_id"
        if run_id not in referenced:
            return "not_in_experiment"
        if run_id in shared:
            return "shared_with_other_experiment"
        if (self._runs / run_id).is_symlink():
            return "not_a_directory"
        return None

    # --- apply -----------------------------------------------------------------

    def delete(self, experiment_id: str, run_ids: list[str], plan_token: str) -> dict[str, Any]:
        with experiment_lock(experiment_id):
            return self._delete(experiment_id, run_ids, plan_token)

    def _delete(self, experiment_id: str, run_ids: list[str], plan_token: str) -> dict[str, Any]:
        plan = self.plan(experiment_id, run_ids)
        if plan["plan_token"] != plan_token:
            raise PlanStale(experiment_id)
        table, column = self._table(experiment_id)
        selected = {r for r in set(run_ids) if r not in {s["run_id"] for s in plan["skipped"]}}

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = table.with_name(f"{table.stem}.pre_delete_{stamp}{table.suffix}")
        shutil.copy2(table, backup)

        for run_id in sorted(selected):
            folder = self._runs / run_id
            if folder.exists():
                shutil.rmtree(folder)

        cleared = _rewrite_without(table, column, selected)

        with (table.parent / JOURNAL_FILE).open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "time_utc": stamp,
                        "run_ids": sorted(selected),
                        "run_count": plan["run_count"],
                        "file_count": plan["file_count"],
                        "bytes": plan["bytes"],
                        "already_absent": plan["already_absent"],
                        "backup": backup.name,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
        return {
            "deleted": plan["run_count"] - plan["already_absent"],
            "already_absent": plan["already_absent"],
            "cleared_rows": cleared,
            "file_count": plan["file_count"],
            "bytes": plan["bytes"],
            "skipped": plan["skipped"],
            "backup": backup.name,
        }

    # --- helpers ---------------------------------------------------------------

    def _table(self, experiment_id: str) -> tuple[Path, str]:
        table, schema = self._experiments.result_table(experiment_id)
        if not table.is_file():
            raise InvalidExperiment(experiment_id, f"result table not found: {table.name}")
        return table, schema.run_id_column

    def _ids_of_other_experiments(self, experiment_id: str) -> set[str]:
        out: set[str] = set()
        for other in self._experiments.registered_ids():
            if other == experiment_id:
                continue
            table, column = self._table(other)
            out |= _run_ids_in(other, table, column)
        return out


def _run_ids_in(experiment_id: str, table: Path, column: str) -> set[str]:
    with table.open(newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader, None) or []
        if column not in header:
            raise InvalidExperiment(experiment_id, f"table lacks declared column: {column}")
        pos = header.index(column)
        return {row[pos] for row in reader if len(row) > pos and row[pos] != ""}


def _rewrite_without(table: Path, column: str, selected: set[str]) -> int:
    with table.open("rb") as raw:
        terminator = "\r\n" if b"\r\n" in raw.readline() else "\n"
    tmp = table.with_name(f"{table.name}.tmp-{os.getpid()}")
    cleared = 0
    with table.open(newline="") as src, tmp.open("w", newline="") as dst:
        reader = csv.reader(src)
        writer = csv.writer(dst, lineterminator=terminator)
        header = next(reader)
        writer.writerow(header)
        pos = header.index(column)
        for row in reader:
            if len(row) > pos and row[pos] in selected:
                row[pos] = ""
                cleared += 1
            writer.writerow(row)
    os.replace(tmp, table)
    return cleared


def _folder_size(folder: Path) -> tuple[int, int]:
    files = size = 0
    for root, _dirs, names in os.walk(folder):
        for name in names:
            files += 1
            size += os.lstat(os.path.join(root, name)).st_size
    return files, size


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _token(deletable: list[str], table_sha256: str) -> str:
    payload = json.dumps({"run_ids": sorted(deletable), "table_sha256": table_sha256}, sort_keys=True)
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()
