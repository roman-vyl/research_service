"""Read-only access to Experiment registry, manifest and result table.

`analysis/experiments.json` lists the Experiments; each manifest carries a
`result_schema`; the result table (for example ``runs.csv``) holds ready-made
metrics. Nothing here writes, validates run bundles, or walks the filesystem
for runs.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from research_service.domain.errors import ExperimentNotFound, InvalidExperiment, InvalidRequest
from research_service.domain.experiment_schema import GRID_ID, ResultSchema

REGISTRY_FILE = "experiments.json"
ROUND_DIGITS = 6
_CACHE_SIZE = 3


@dataclass(frozen=True, slots=True)
class _Table:
    rows: int
    numeric: dict[str, list[float | None]]
    text: dict[str, list[str | None]]


class FilesystemExperiments:
    def __init__(self, analysis_root: Path) -> None:
        self._root = analysis_root
        self._cache: dict[tuple[str, int, int], _Table] = {}

    # --- registry and manifest -------------------------------------------------

    def registry(self) -> dict[str, Any]:
        path = self._root / REGISTRY_FILE
        if not path.is_file():
            return {"registry_version": 1, "experiments": []}
        return _load_json(path)  # type: ignore[no-any-return]

    def _entry(self, experiment_id: str) -> dict[str, Any]:
        for entry in self.registry().get("experiments", []):
            if entry.get("experiment_id") == experiment_id:
                return dict(entry)
        raise ExperimentNotFound(experiment_id)

    def _manifest_path(self, experiment_id: str) -> Path:
        entry = self._entry(experiment_id)
        rel = entry.get("manifest")
        if not isinstance(rel, str):
            raise InvalidExperiment(experiment_id, "registry entry has no manifest path")
        path = (self._root / rel).resolve()
        if self._root.resolve() not in path.parents:
            raise InvalidExperiment(experiment_id, "manifest path leaves the analysis root")
        if not path.is_file():
            raise InvalidExperiment(experiment_id, f"manifest not found: {rel}")
        return path

    def manifest(self, experiment_id: str) -> dict[str, Any]:
        return _load_json(self._manifest_path(experiment_id), experiment_id)  # type: ignore[no-any-return]

    # --- results ---------------------------------------------------------------

    def results(
        self,
        experiment_id: str,
        *,
        filters: dict[str, str],
        columns: list[str] | None,
    ) -> dict[str, Any]:
        manifest_path = self._manifest_path(experiment_id)
        manifest = _load_json(manifest_path, experiment_id)
        try:
            schema = ResultSchema.model_validate(manifest.get("result_schema"))
        except ValidationError as exc:
            raise InvalidExperiment(experiment_id, f"result_schema: {exc.errors()[0]['msg']}") from exc
        table = self._table(experiment_id, manifest_path.parent / schema.table, schema)
        out = _Out(schema)
        wanted = out.resolve_columns(columns)
        idx = _select(table, schema, out, filters)
        data = [_column(table, out.source[c], idx) for c in wanted]
        result: dict[str, Any] = {"columns": wanted, "rows": len(idx), "data": data}
        if schema.provenance.value is not None:
            result["provenance"] = {"value": schema.provenance.value}
        return result

    def _table(self, experiment_id: str, path: Path, schema: ResultSchema) -> _Table:
        if not path.is_file():
            raise InvalidExperiment(experiment_id, f"result table not found: {path.name}")
        st = path.stat()
        key = (str(path), st.st_mtime_ns, st.st_size)
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        table = _read_table(experiment_id, path, schema)
        if len(self._cache) >= _CACHE_SIZE:
            self._cache.pop(next(iter(self._cache)))
        self._cache[key] = table
        return table


def _load_json(path: Path, experiment_id: str | None = None) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        if experiment_id is None:
            raise InvalidRequest(f"{path.name} is not readable: {exc}") from exc
        raise InvalidExperiment(experiment_id, f"{path.name} is not readable: {exc}") from exc


class _Out:
    """Maps semantic ids to physical columns and back."""

    def __init__(self, schema: ResultSchema) -> None:
        self.schema = schema
        self.source: dict[str, str] = {}      # output id -> physical column
        self.numeric: set[str] = set()        # output ids that are numeric
        self.order: list[str] = []
        self.dim_filter: dict[str, str] = {}  # single-dimension id -> column
        self.multi: dict[str, dict[str, str]] = {}  # multi dimension id -> grid -> column
        self.grid_column: str | None = None
        for dim in schema.dimensions:
            if dim.grids:
                self.multi[dim.id] = {g: c.column for g, c in dim.grids.items()}
                self.grid_column = dim.grid_column
                for grid, gcol in dim.grids.items():
                    self._add(f"{dim.id}.{grid}", gcol.column, True)
            else:
                assert dim.column
                self.dim_filter[dim.id] = dim.column
                self._add(dim.id, dim.column, True)
        if self.grid_column:
            self._add(GRID_ID, self.grid_column, False)
        if schema.arms:
            self._add("arm", schema.arms.column, False)
        for metric in schema.metrics:
            self._add(metric.metric_id, metric.column, True)
        self._add("run_id", schema.run_id_column, False)
        if schema.provenance.column:
            self._add("provenance", schema.provenance.column, False)
        for name, col in schema.row_columns.items():
            self._add(name, col, False)

    def _add(self, oid: str, column: str, numeric: bool) -> None:
        self.source[oid] = column
        self.order.append(oid)
        if numeric:
            self.numeric.add(oid)

    def resolve_columns(self, requested: list[str] | None) -> list[str]:
        if not requested:
            return list(self.order)
        for oid in requested:
            if oid not in self.source:
                raise InvalidRequest(f"unknown column id: {oid}", {"id": oid})
        return requested

    def physical(self) -> dict[str, bool]:
        return {self.source[o]: o in self.numeric for o in self.order}


def _read_table(experiment_id: str, path: Path, schema: ResultSchema) -> _Table:
    out = _Out(schema)
    need = out.physical()
    with path.open(newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader, None) or []
        missing = sorted(c for c in need if c not in header)
        if missing:
            raise InvalidExperiment(experiment_id, f"table lacks declared columns: {missing}")
        pos = {c: header.index(c) for c in need}
        numeric: dict[str, list[float | None]] = {c: [] for c, n in need.items() if n}
        text: dict[str, list[str | None]] = {c: [] for c, n in need.items() if not n}
        rows = 0
        for row in reader:
            rows += 1
            for c, lst in numeric.items():
                v = row[pos[c]]
                lst.append(float(v) if v != "" else None)
            for c, tl in text.items():
                v = row[pos[c]]
                tl.append(v if v != "" else None)
    return _Table(rows, numeric, text)


def _select(table: _Table, schema: ResultSchema, out: _Out, filters: dict[str, str]) -> list[int]:
    idx: list[int] | None = None
    grid_value = filters.get(GRID_ID)
    for fid, value in filters.items():
        if fid == GRID_ID:
            if out.grid_column is None:
                raise InvalidRequest("this experiment has no grid", {"id": fid})
            idx = _eq_text(table, out.grid_column, value, idx)
        elif fid == "arm":
            if schema.arms is None:
                raise InvalidRequest("this experiment has no arms", {"id": fid})
            idx = _eq_text(table, schema.arms.column, value, idx)
        elif fid in out.dim_filter:
            idx = _eq_num(table, out.dim_filter[fid], value, fid, idx)
        elif fid in out.multi:
            if grid_value is None:
                raise InvalidRequest(f"filter {fid} needs a grid", {"id": fid})
            col = out.multi[fid].get(grid_value)
            if col is None:
                raise InvalidRequest(f"unknown grid: {grid_value}", {"id": GRID_ID})
            idx = _eq_num(table, col, value, fid, idx)
        else:
            raise InvalidRequest(f"unknown filter id: {fid}", {"id": fid})
    return list(range(table.rows)) if idx is None else idx


def _eq_text(table: _Table, column: str, value: str, idx: list[int] | None) -> list[int]:
    col = table.text[column]
    rows = range(table.rows) if idx is None else idx
    return [i for i in rows if col[i] == value]


def _eq_num(table: _Table, column: str, value: str, fid: str, idx: list[int] | None) -> list[int]:
    try:
        target = float(value)
    except ValueError as exc:
        raise InvalidRequest(f"filter {fid} needs a number", {"id": fid}) from exc
    col = table.numeric[column]
    rows = range(table.rows) if idx is None else idx
    return [i for i in rows if col[i] is not None and math.isclose(col[i], target, abs_tol=1e-9)]  # type: ignore[arg-type]


def _column(table: _Table, physical: str, idx: list[int]) -> list[Any]:
    if physical in table.numeric:
        col = table.numeric[physical]
        out: list[Any] = []
        for i in idx:
            v = col[i]
            if v is None:
                out.append(None)
            elif v == int(v) and abs(v) < 1e15:
                out.append(int(v))
            else:
                out.append(round(v, ROUND_DIGITS))
        return out
    tcol = table.text[physical]
    return [tcol[i] for i in idx]
