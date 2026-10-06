"""The user's candidate shortlist (``research-candidate-shortlist-v1``).

A record in ``analysis/candidates.json`` means one Surface point is picked; no record
means it is not. The record keeps a snapshot of the picked row, a fingerprint of its
content and, when the row has a run, that run's strategy as a historical snapshot.
Listing compares the table's ``(mtime_ns, size)`` first and parses the table only when
it changed. Nothing here lists the artifacts root or writes an Experiment or a run.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_service.adapters.experiments.filesystem import (
    FilesystemExperiments,
    _column,
    _Out,
    _Table,
)
from research_service.domain.errors import (
    AmbiguousRow,
    InvalidCandidatesFile,
    InvalidCoords,
    ResearchServiceError,
    RowNotFound,
)
from research_service.domain.experiment_schema import GRID_ID, ResultSchema

CANDIDATES_FILE = "candidates.json"
JOURNAL_FILE = "candidates_journal.jsonl"
CONTRACT_VERSION = "research_candidates.v1"
_EXCLUDED_FROM_FINGERPRINT = ("run_id", "provenance")

Coords = dict[str, str | None]


class FilesystemCandidates:
    def __init__(self, experiments: FilesystemExperiments, artifacts_root: Path) -> None:
        self._experiments = experiments
        self._runs = artifacts_root
        self._path = experiments.root / CANDIDATES_FILE
        self._journal = experiments.root / JOURNAL_FILE
        self._lock = threading.Lock()

    # --- routes ----------------------------------------------------------------

    def list_all(self) -> dict[str, Any]:
        records = self._read()
        return {"candidates": [{**r, "current": self._current(r)} for r in records]}

    def star(self, experiment_id: str, coords: dict[str, Any]) -> dict[str, Any]:
        manifest, schema, table_path = self._experiments.loaded(experiment_id)
        out = _Out(schema)
        canonical = _canonical_coords(experiment_id, schema, coords)
        candidate_id = _candidate_id(experiment_id, canonical)
        with self._lock:
            records = self._read()
            for existing in records:
                if existing["candidate_id"] == candidate_id:
                    return existing
            key, table = self._experiments.keyed_table(experiment_id)
            rows = _matching_rows(schema, out, table, canonical)
            if not rows:
                raise RowNotFound(experiment_id, canonical)
            if len(rows) > 1:
                raise AmbiguousRow(experiment_id, canonical, len(rows))
            i = rows[0]
            fields = [oid for oid in out.order if oid not in _EXCLUDED_FROM_FINGERPRINT]
            values = _served(out, table, i)
            run_id = values.get("run_id")
            record = {
                "candidate_id": candidate_id,
                "experiment_id": experiment_id,
                "coords": canonical,
                "picked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "fingerprint_fields": fields,
                "fingerprint": _fingerprint(out, table, i, fields),
                "table_key": {"mtime_ns": key[1], "size": key[2]},
                "snapshot": {
                    "metrics": {m.metric_id: values.get(m.metric_id) for m in schema.metrics},
                    "provenance": _provenance(schema, values),
                    "run_id": run_id,
                    "row_columns": {name: values.get(name) for name in schema.row_columns},
                },
                "strategy_spec_snapshot": self._spec_snapshot(run_id),
            }
            self._write([*records, record], "star", record)
            return record

    def unstar(self, candidate_id: str) -> dict[str, Any]:
        with self._lock:
            records = self._read()
            kept = [r for r in records if r["candidate_id"] != candidate_id]
            if len(kept) == len(records):
                return {"removed": False}
            removed = next(r for r in records if r["candidate_id"] == candidate_id)
            self._write(kept, "unstar", removed)
            return {"removed": True}

    # --- current state ---------------------------------------------------------

    def _current(self, record: dict[str, Any]) -> dict[str, Any]:
        experiment_id = record["experiment_id"]
        missing: dict[str, Any] = {
            "row_state": "missing", "run_id": None, "provenance": None, "metrics": None, "meaning": None,
        }
        try:
            manifest, schema, table_path = self._experiments.loaded(experiment_id)
            meaning = _meaning(self._experiments.entry(experiment_id), manifest, schema, record["coords"])
            st = table_path.stat()
        except (ResearchServiceError, OSError):
            return missing
        snapshot = record["snapshot"]
        if st.st_mtime_ns == record["table_key"]["mtime_ns"] and st.st_size == record["table_key"]["size"]:
            return {
                "row_state": "same",
                "run_id": snapshot["run_id"],
                "provenance": snapshot["provenance"],
                "metrics": snapshot["metrics"],
                "meaning": meaning,
            }
        try:
            out = _Out(schema)
            _key, table = self._experiments.keyed_table(experiment_id)
            rows = _matching_rows(schema, out, table, record["coords"])
        except (ResearchServiceError, OSError):
            return {**missing, "meaning": meaning}
        if not rows:
            return {**missing, "meaning": meaning}
        if len(rows) > 1:
            return {**missing, "row_state": "ambiguous", "meaning": meaning}
        i = rows[0]
        fields = record["fingerprint_fields"]
        same = all(f in out.source for f in fields) and _fingerprint(out, table, i, fields) == record["fingerprint"]
        values = _served(out, table, i)
        return {
            "row_state": "same" if same else "changed",
            "run_id": values.get("run_id"),
            "provenance": _provenance(schema, values),
            "metrics": {m.metric_id: values.get(m.metric_id) for m in schema.metrics},
            "meaning": meaning,
        }

    # --- strategy snapshot -----------------------------------------------------

    def _spec_snapshot(self, run_id: Any) -> dict[str, Any] | None:
        if not isinstance(run_id, str) or not run_id:
            return None
        path = self._runs / run_id / "request.json"
        try:
            if path.parent.is_symlink() or not path.is_file():
                raise FileNotFoundError(path.name)
            request = json.loads(path.read_text())
            strategy = request["strategy"]
            if not isinstance(strategy, dict):
                raise ValueError("strategy is not an object")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            return {"source": None, "run_id": run_id, "reason": f"request.json unavailable: {exc}"}
        return {"source": "run_request", "run_id": run_id, "spec": strategy}

    # --- storage ---------------------------------------------------------------

    def _read(self) -> list[dict[str, Any]]:
        if not self._path.is_file():
            return []
        try:
            data = json.loads(self._path.read_text())
            records = data["candidates"]
            if not isinstance(records, list) or not all(isinstance(r, dict) for r in records):
                raise ValueError("candidates is not a list of records")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise InvalidCandidatesFile(str(exc)) from exc
        return records

    def _write(self, records: list[dict[str, Any]], action: str, record: dict[str, Any]) -> None:
        tmp = self._path.with_name(f"{self._path.name}.tmp-{os.getpid()}")
        payload = {"contract_version": CONTRACT_VERSION, "candidates": records}
        tmp.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n")
        os.replace(tmp, self._path)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._journal.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"time_utc": stamp, "action": action, "record": record}, sort_keys=True) + "\n")


# --- identity and row content -------------------------------------------------


def _coord_ids(schema: ResultSchema) -> tuple[list[str], set[str]]:
    """Required coordinate ids and the subset that is text."""
    ids = [d.id for d in schema.dimensions]
    text: set[str] = set()
    if any(d.grids for d in schema.dimensions):
        ids.append(GRID_ID)
        text.add(GRID_ID)
    if schema.arms:
        ids.append("arm")
        text.add("arm")
    return ids, text


def _number(value: float) -> str:
    out = format(value, ".12g")
    return "0" if out == "-0" else out


def _canonical_coords(experiment_id: str, schema: ResultSchema, coords: dict[str, Any]) -> Coords:
    ids, text = _coord_ids(schema)
    if set(coords) != set(ids):
        missing = sorted(set(ids) - set(coords))
        extra = sorted(set(coords) - set(ids))
        raise InvalidCoords(experiment_id, f"missing {missing}, unknown {extra}")
    out: Coords = {}
    for cid in ids:
        value = coords[cid]
        if value is None or value == "":
            out[cid] = None
        elif cid in text:
            if not isinstance(value, str):
                raise InvalidCoords(experiment_id, f"{cid} must be text")
            out[cid] = value
        else:
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise InvalidCoords(experiment_id, f"{cid} must be a number") from exc
            if isinstance(value, bool) or not math.isfinite(number):
                raise InvalidCoords(experiment_id, f"{cid} must be a finite number")
            out[cid] = _number(number)
    return out


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _candidate_id(experiment_id: str, coords: Coords) -> str:
    digest = hashlib.sha256(_canonical_json({"experiment_id": experiment_id, "coords": coords}))
    return "cand_" + digest.hexdigest()[:24]


def _matching_rows(schema: ResultSchema, out: _Out, table: _Table, coords: Coords) -> list[int]:
    """Rows whose coordinates equal ``coords`` (numbers within ``1e-9``, as the results route)."""
    rows: list[int] = list(range(table.rows))
    for cid, want in coords.items():
        if not rows:
            break
        if cid in (GRID_ID, "arm"):
            column = out.grid_column if cid == GRID_ID else (schema.arms.column if schema.arms else None)
            assert column is not None
            text = table.text[column]
            rows = [i for i in rows if text[i] == want]
            continue
        if cid in out.multi:
            assert out.grid_column is not None
            grids = table.text[out.grid_column]
            columns = {g: table.numeric[c] for g, c in out.multi[cid].items()}
            values = [columns[grids[i]][i] if grids[i] in columns else None for i in rows]  # type: ignore[index]
        else:
            col = table.numeric[out.dim_filter[cid]]
            values = [col[i] for i in rows]
        if want is None:
            rows = [i for i, v in zip(rows, values) if v is None]
        else:
            target = float(want)
            rows = [i for i, v in zip(rows, values) if v is not None and math.isclose(v, target, abs_tol=1e-9)]
    return rows


def _raw(out: _Out, table: _Table, i: int, oid: str) -> str | None:
    column = out.source[oid]
    if column in table.numeric:
        v = table.numeric[column][i]
        return None if v is None else _number(v)
    return table.text[column][i]


def _fingerprint(out: _Out, table: _Table, i: int, fields: list[str]) -> str:
    values = {f: _raw(out, table, i, f) for f in fields}
    return "sha256:" + hashlib.sha256(_canonical_json(values)).hexdigest()


def _served(out: _Out, table: _Table, i: int) -> dict[str, Any]:
    return {oid: _column(table, out.source[oid], [i])[0] for oid in out.order}


def _provenance(schema: ResultSchema, values: dict[str, Any]) -> Any:
    return schema.provenance.value if schema.provenance.value is not None else values.get("provenance")


def _meaning(
    entry: dict[str, Any], manifest: dict[str, Any], schema: ResultSchema, coords: Coords
) -> dict[str, Any]:
    varied = {
        p.get("column"): p for p in manifest.get("varied_params", []) or [] if isinstance(p, dict)
    }
    grid = coords.get(GRID_ID)
    items: list[dict[str, Any]] = []
    for dim in schema.dimensions:
        if dim.grids:
            gcol = dim.grids.get(grid) if grid is not None else None
            column, unit = (gcol.column, gcol.unit) if gcol else (None, None)
        else:
            column, unit = dim.column, dim.unit
        param = varied.get(column, {})
        items.append(
            {
                "id": dim.id,
                "label": dim.label or param.get("label") or dim.id,
                "value": coords.get(dim.id),
                "unit": unit,
                "component_id": param.get("component_id"),
                "component_param": param.get("component_param"),
            }
        )
    if GRID_ID in coords:
        items.append({"id": GRID_ID, "label": "Grid", "value": grid, "unit": None,
                      "component_id": None, "component_param": None})
    if "arm" in coords:
        items.append({"id": "arm", "label": "Arm", "value": coords["arm"], "unit": None,
                      "component_id": None, "component_param": None})
    return {
        "experiment_id": entry.get("experiment_id"),
        "title": entry.get("title"),
        "ticker": entry.get("ticker"),
        "anchor": entry.get("anchor"),
        "coords": items,
        "fixed_params": manifest.get("fixed_params"),
    }

