"""Calculate rows of an Experiment with Engine and publish them after a metric parity gate.

``research-run-calculation-v1``: a row is addressed by its coordinates, its spec is
materialized from the manifest ``materialize`` block (template + bindings, Engine
validates), the job runs the specs through the Research batch path, compares each
run summary with the metrics already stored in the row, and only rows that agree
are written back to the table, atomically, with the new ``run_id``. A row that
does not agree is left as it was; its run stays on disk as a diagnostic.
"""

from __future__ import annotations

import copy
import csv
import hashlib
import json
import math
import os
import re
import shutil
import threading
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Protocol

from pydantic import ValidationError

from research_service.adapters.experiments.filesystem import FilesystemExperiments
from research_service.adapters.experiments.locks import experiment_lock
from research_service.application.experiments.contracts import (
    BatchCandidateRequest,
    BatchExperimentRequest,
    BatchExperimentResult,
    PersistedBatchArtifacts,
)
from research_service.domain.errors import (
    CalculationJobNotFound,
    CalculationRejected,
    InvalidExperiment,
    InvalidRequest,
    PlanStale,
    TooManyRows,
)
from research_service.domain.experiment_materialize import MaterializeBlock, pointer_set
from research_service.domain.experiment_schema import GRID_ID, ResultSchema
from research_service.domain.strategy_instance import DeployableStrategyInstance
from research_service.ports.strategy_engine import StrategySpecValidation

MAX_ROWS = 2000
BATCH_SIZE = 1000
JOURNAL_FILE = "runs_calculated.jsonl"
REL_TOL = 1e-6
ABS_TOL = 1e-9
_RUN_ID_RE = re.compile(r"^run_[0-9a-f]{32}$")
_ID_CHARS_RE = re.compile(r"[^A-Za-z0-9._-]")
_MARKET_HASH_ROW_COLUMN = "market_data_hash"


class _SpecValidator(Protocol):
    def validate_strategy(self, strategy_id: str, raw_spec: dict[str, Any]) -> StrategySpecValidation: ...


class _BatchRunner(Protocol):
    def execute(
        self, request: BatchExperimentRequest, *, expected_market_data_hash: str | None = None
    ) -> BatchExperimentResult: ...


class _BatchPersister(Protocol):
    def execute(self, request: BatchExperimentRequest, result: BatchExperimentResult) -> PersistedBatchArtifacts: ...


def _thread(target: Callable[[], None]) -> None:
    threading.Thread(target=target, name="research-calculation", daemon=True).start()


# --- plan data ----------------------------------------------------------------


@dataclass(slots=True)
class _Row:
    position: int                 # index in the request
    coords: dict[str, Any]
    row_index: int | None = None  # data row index in the table (0-based, header excluded)
    row_hash: str | None = None
    cells: dict[str, str] = field(default_factory=dict)
    spec: dict[str, Any] | None = None
    config_hash: str | None = None
    reason: str | None = None
    message: str | None = None


@dataclass(slots=True)
class _Plan:
    experiment_id: str
    table: Path
    schema: ResultSchema
    block: MaterializeBlock
    rows: list[_Row]
    token: str

    @property
    def calculable(self) -> list[_Row]:
        return [r for r in self.rows if r.reason is None]

    def payload(self) -> dict[str, Any]:
        out = []
        for r in self.rows:
            item: dict[str, Any] = {"position": r.position, "coords": r.coords}
            if r.reason is None:
                item.update(status="calculable", config_hash=r.config_hash)
            else:
                item.update(status="skipped", reason=r.reason)
                if r.message:
                    item["message"] = r.message
            out.append(item)
        return {"rows": out, "calculable_count": len(self.calculable), "plan_token": self.token}


# --- job data -----------------------------------------------------------------


@dataclass(slots=True)
class _JobRow:
    row: _Row
    outcome: str | None = None
    run_id: str | None = None
    parity: list[dict[str, Any]] | None = None
    message: str | None = None

    def payload(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "position": self.row.position,
            "coords": self.row.coords,
            "row_index": self.row.row_index,
            "config_hash": self.row.config_hash,
            "outcome": self.outcome or "pending",
        }
        if self.run_id:
            out["run_id"] = self.run_id
        if self.parity:
            out["parity"] = self.parity
        if self.message:
            out["message"] = self.message
        return out


@dataclass(slots=True)
class _Job:
    job_id: str
    plan: _Plan
    rows: list[_JobRow]
    state: str = "running"
    cancel_requested: bool = False
    backup: str | None = None
    error: str | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)

    def payload(self) -> dict[str, Any]:
        with self.lock:
            counts: dict[str, int] = {}
            for r in self.rows:
                key = r.outcome or "pending"
                counts[key] = counts.get(key, 0) + 1
            out: dict[str, Any] = {
                "job_id": self.job_id,
                "experiment_id": self.plan.experiment_id,
                "state": self.state,
                "counts": counts,
                "rows": [r.payload() for r in self.rows],
            }
            if self.backup:
                out["backup"] = self.backup
            if self.error:
                out["error"] = self.error
            return out


class FilesystemRunCalculation:
    def __init__(
        self,
        experiments: FilesystemExperiments,
        artifacts_root: Path,
        engine: _SpecValidator,
        run_batch: _BatchRunner,
        persist_batch: _BatchPersister,
        spawn: Callable[[Callable[[], None]], None] = _thread,
    ) -> None:
        self._experiments = experiments
        self._runs = artifacts_root
        self._engine = engine
        self._run_batch = run_batch
        self._persist_batch = persist_batch
        self._spawn = spawn
        self._jobs: dict[str, _Job] = {}
        self._guard = threading.Lock()
        self._active: str | None = None

    # --- routes ----------------------------------------------------------------

    def plan(self, experiment_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        return self._plan(experiment_id, rows).payload()

    def calculate(self, experiment_id: str, rows: list[dict[str, Any]], plan_token: str) -> dict[str, Any]:
        plan = self._plan(experiment_id, rows)
        if plan.token != plan_token:
            raise PlanStale(experiment_id, "calculate")
        with self._guard:
            self._reject_if_running(experiment_id)
            job = _Job(
                job_id="calc_" + uuid.uuid4().hex,
                plan=plan,
                rows=[_JobRow(r) for r in plan.calculable],
            )
            self._jobs[job.job_id] = job
            self._active = job.job_id
        self._spawn(lambda: self._run(job))
        return {"job_id": job.job_id, "row_count": len(job.rows)}

    def status(self, experiment_id: str, job_id: str) -> dict[str, Any]:
        return self._job(experiment_id, job_id).payload()

    def cancel(self, experiment_id: str, job_id: str) -> dict[str, Any]:
        job = self._job(experiment_id, job_id)
        with job.lock:
            if job.state == "running":
                job.cancel_requested = True
        return job.payload()

    def _job(self, experiment_id: str, job_id: str) -> _Job:
        job = self._jobs.get(job_id)
        if job is None or job.plan.experiment_id != experiment_id:
            raise CalculationJobNotFound(job_id)
        return job

    def _reject_if_running(self, experiment_id: str) -> None:
        active = self._jobs.get(self._active) if self._active else None
        if active is not None and active.state == "running":
            raise CalculationRejected(
                experiment_id,
                "job_running",
                "another calculation job is running",
                {"job_id": active.job_id},
            )

    # --- plan --------------------------------------------------------------------

    def _plan(self, experiment_id: str, rows: list[dict[str, Any]]) -> _Plan:
        if not rows:
            raise InvalidRequest("rows must not be empty")
        if len(rows) > MAX_ROWS:
            raise TooManyRows(len(rows), MAX_ROWS)
        table, schema = self._experiments.result_table(experiment_id)
        if not table.is_file():
            raise InvalidExperiment(experiment_id, f"result table not found: {table.name}")
        block = self._block(experiment_id)
        header = _header(table)
        self._check_experiment(experiment_id, schema, block, header)
        with self._guard:
            self._reject_if_running(experiment_id)

        keys = _Keys(schema)
        planned = [_Row(position=i, coords=_coords(item, i)) for i, item in enumerate(rows)]
        wanted: dict[tuple[Any, ...], list[_Row]] = {}
        for row in planned:
            wanted.setdefault(keys.request_key(row.coords, row.position), []).append(row)

        matches: dict[tuple[Any, ...], int] = {}
        table_digest = hashlib.sha256()
        for index, cells, raw in _rows(table):
            table_digest.update(raw)
            key = keys.row_key(header, cells)
            if key is None or key not in wanted:
                continue
            matches[key] = matches.get(key, 0) + 1
            if matches[key] > 1:
                continue
            row_cells = dict(zip(header, cells))
            for row in wanted[key]:
                row.row_index = index
                row.row_hash = _row_hash(cells)
                row.cells = row_cells

        validations: dict[str, StrategySpecValidation] = {}
        for row in planned:
            key = keys.request_key(row.coords, row.position)
            if matches.get(key, 0) == 0:
                row.reason = "row_not_found"
            elif matches[key] > 1:
                row.reason = "ambiguous_row"
            elif self._has_run(row.cells.get(schema.run_id_column, "")):
                row.reason = "has_run"
            else:
                self._materialize(row, block, validations)

        token = _token(table_digest.hexdigest(), block, planned)
        return _Plan(experiment_id, table, schema, block, planned, token)

    def _block(self, experiment_id: str) -> MaterializeBlock:
        raw = self._experiments.manifest(experiment_id).get("materialize")
        if raw is None:
            raise CalculationRejected(
                experiment_id, "materialize_missing", "the Experiment manifest has no materialize block"
            )
        try:
            return MaterializeBlock.model_validate(raw)
        except ValidationError as exc:
            raise InvalidExperiment(experiment_id, f"materialize: {exc.errors()[0]['msg']}") from exc

    @staticmethod
    def _check_experiment(
        experiment_id: str, schema: ResultSchema, block: MaterializeBlock, header: list[str]
    ) -> None:
        needed = {b.column for b in block.bindings} | set(block.result_bindings) | {schema.run_id_column}
        missing = sorted(needed - set(header))
        if missing:
            raise InvalidExperiment(experiment_id, f"materialize: table lacks columns {missing}")
        unbound = sorted(m.column for m in schema.metrics if m.column not in block.result_bindings)
        if unbound:
            raise CalculationRejected(
                experiment_id,
                "unbound_metric",
                "every metric column needs a result binding",
                {"columns": unbound},
            )
        if schema.provenance.value is not None and schema.provenance.value != "engine":
            raise CalculationRejected(
                experiment_id,
                "provenance_not_per_row",
                "provenance is a constant other than engine; one row cannot become engine",
                {"provenance": schema.provenance.value},
            )

    def _has_run(self, run_id: str) -> bool:
        if not run_id:
            return False
        return bool(_RUN_ID_RE.fullmatch(run_id)) and (self._runs / run_id).is_dir()

    def _materialize(
        self, row: _Row, block: MaterializeBlock, cache: dict[str, StrategySpecValidation]
    ) -> None:
        spec = copy.deepcopy(block.strategy_template.model_dump(mode="json"))
        for binding in block.bindings:
            text = row.cells.get(binding.column, "")
            try:
                value = _parse(text, binding.type)
            except ValueError as exc:
                row.reason = "binding_value_invalid"
                row.message = f"{binding.column}: {exc}"
                return
            pointer_set(spec, binding.path, value)
        canonical = json.dumps(spec["raw_spec"], sort_keys=True, separators=(",", ":"))
        verdict = cache.get(canonical)
        if verdict is None:
            verdict = cache[canonical] = self._engine.validate_strategy(spec["strategy_id"], spec["raw_spec"])
        if verdict.config_hash is None:
            row.reason = "invalid_spec"
            row.message = verdict.error
            return
        row.spec = spec
        row.config_hash = verdict.config_hash

    # --- job ---------------------------------------------------------------------

    def _run(self, job: _Job) -> None:
        plan = job.plan
        try:
            market_column = plan.schema.row_columns.get(_MARKET_HASH_ROW_COLUMN)
            groups: dict[str | None, list[_JobRow]] = {}
            for jr in job.rows:
                key = (jr.row.cells.get(market_column) or None) if market_column else None
                groups.setdefault(key, []).append(jr)
            call = 0
            for market_hash, members in groups.items():
                for start in range(0, len(members), BATCH_SIZE):
                    chunk = members[start:start + BATCH_SIZE]
                    with job.lock:
                        cancelled = job.cancel_requested
                    if cancelled:
                        self._settle(job, chunk, "cancelled", None)
                        continue
                    call += 1
                    self._run_chunk(job, chunk, market_hash, call)
            with job.lock:
                job.state = "cancelled" if job.cancel_requested else "completed"
        except Exception as exc:  # noqa: BLE001 -- the job reports, never crashes the service
            pending = [jr for jr in job.rows if jr.outcome is None]
            with job.lock:
                job.error = getattr(exc, "message", None) or str(exc)
            self._settle(job, pending, "cancelled", job.error)
            with job.lock:
                job.state = "failed"
        finally:
            with self._guard:
                if self._active == job.job_id:
                    self._active = None

    def _run_chunk(self, job: _Job, chunk: list[_JobRow], market_hash: str | None, call: int) -> None:
        plan = job.plan
        policy = plan.block.research_policy
        request = BatchExperimentRequest(
            experiment_id=_batch_id(plan.experiment_id, job.job_id, call),
            strategy_id=plan.block.strategy_template.strategy_id,
            range_policy=policy.range_policy,
            range=policy.range,
            candidates=tuple(
                BatchCandidateRequest(
                    candidate_id=f"r{jr.row.row_index}",
                    strategy=DeployableStrategyInstance.model_validate(jr.row.spec),
                    execution=policy.execution,
                    accounting=policy.accounting,
                    managed_policy_enabled=policy.managed_policy_enabled,
                    metadata={"experiment_id": plan.experiment_id, "row_index": jr.row.row_index},
                )
                for jr in chunk
            ),
            description=f"Calculate {plan.experiment_id} ({job.job_id})",
        )
        try:
            result = self._run_batch.execute(request, expected_market_data_hash=market_hash)
        except Exception as exc:  # noqa: BLE001 -- a failed call fails its rows, not the job
            self._settle(job, chunk, "engine_failed", getattr(exc, "message", None) or str(exc))
            return
        try:
            self._persist_batch.execute(request, result)
        except Exception:  # noqa: BLE001,S110 -- the batch summary is a convenience copy
            pass

        by_candidate = {c.candidate_id: c for c in result.candidates}
        passed: list[tuple[_JobRow, dict[str, str]]] = []
        for jr in chunk:
            candidate = by_candidate.get(f"r{jr.row.row_index}")
            if candidate is None or candidate.status != "completed" or not candidate.run_id:
                message = candidate.error_message if candidate is not None else "no result for row"
                self._settle(job, [jr], "engine_failed", message)
                continue
            summary = candidate.model_dump(mode="python")
            values = {col: _lookup(summary, path) for col, path in plan.block.result_bindings.items()}
            diffs = _parity(plan.schema, jr.row.cells, values)
            if diffs:
                with job.lock:
                    jr.run_id = candidate.run_id
                    jr.parity = diffs
                self._settle(job, [jr], "parity_failed", None)
                continue
            with job.lock:
                jr.run_id = candidate.run_id
            passed.append((jr, {col: _cell(v) for col, v in values.items()}))
        if passed:
            self._publish(job, passed)

    def _publish(self, job: _Job, passed: list[tuple[_JobRow, dict[str, str]]]) -> None:
        plan = job.plan
        schema = plan.schema
        updates: dict[int, tuple[_JobRow, dict[str, str]]] = {}
        for jr, cells in passed:
            new = dict(cells)
            new[schema.run_id_column] = jr.run_id or ""
            if schema.provenance.column:
                new[schema.provenance.column] = "engine"
            assert jr.row.row_index is not None
            updates[jr.row.row_index] = (jr, new)
        with experiment_lock(plan.experiment_id):
            if job.backup is None:
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                backup = plan.table.with_name(f"{plan.table.stem}.pre_calculate_{stamp}{plan.table.suffix}")
                shutil.copy2(plan.table, backup)
                with job.lock:
                    job.backup = backup.name
            published, stale = _rewrite(plan.table, updates)
        self._settle(job, [updates[i][0] for i in sorted(published)], "published", None)
        self._settle(job, [updates[i][0] for i in sorted(stale)], "row_stale", "row changed since the plan")

    def _settle(self, job: _Job, rows: list[_JobRow], outcome: str, message: str | None) -> None:
        if not rows:
            return
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        lines = []
        with job.lock:
            for jr in rows:
                jr.outcome = outcome
                if message is not None:
                    jr.message = message
                lines.append(
                    json.dumps(
                        {
                            "time_utc": stamp,
                            "job_id": job.job_id,
                            "row_index": jr.row.row_index,
                            "coords": jr.row.coords,
                            "config_hash": jr.row.config_hash,
                            "outcome": outcome,
                            "run_id": jr.run_id,
                            "parity": jr.parity,
                            "message": jr.message,
                        },
                        sort_keys=True,
                        default=str,
                    )
                )
        with (job.plan.table.parent / JOURNAL_FILE).open("a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")


# --- coordinates -------------------------------------------------------------------


class _Keys:
    """Row identity from the dimensions of ``result_schema`` (same ids as the results filters)."""

    def __init__(self, schema: ResultSchema) -> None:
        self.single: list[tuple[str, str]] = []          # (dimension id, column)
        self.multi: list[tuple[str, dict[str, str]]] = []  # (dimension id, grid -> column)
        self.grid_column: str | None = None
        self.arm_column = schema.arms.column if schema.arms else None
        for dim in schema.dimensions:
            if dim.grids:
                self.multi.append((dim.id, {g: c.column for g, c in dim.grids.items()}))
                self.grid_column = dim.grid_column
            else:
                assert dim.column
                self.single.append((dim.id, dim.column))
        self.ids = [d for d, _ in self.single] + [d for d, _ in self.multi]
        if self.grid_column:
            self.ids.append(GRID_ID)
        if self.arm_column:
            self.ids.append("arm")

    def request_key(self, coords: dict[str, Any], position: int) -> tuple[Any, ...]:
        missing = [i for i in self.ids if i not in coords]
        extra = [k for k in coords if k not in self.ids]
        if missing or extra:
            raise InvalidRequest(
                f"rows[{position}].coords must name exactly the dimensions {self.ids}",
                {"missing": missing, "unknown": extra},
            )
        key: list[Any] = []
        for dim_id in [d for d, _ in self.single] + [d for d, _ in self.multi]:
            value = _num(coords[dim_id])
            if value is None:
                raise InvalidRequest(f"rows[{position}].coords.{dim_id} needs a number", {"id": dim_id})
            key.append(value)
        if self.grid_column:
            key.append(str(coords[GRID_ID]))
        if self.arm_column:
            key.append(str(coords["arm"]))
        return tuple(key)

    def row_key(self, header: list[str], cells: list[str]) -> tuple[Any, ...] | None:
        row = dict(zip(header, cells))
        key: list[Any] = [_num(row.get(col, "")) for _, col in self.single]
        grid = row.get(self.grid_column, "") if self.grid_column else None
        for _, grids in self.multi:
            col = grids.get(grid or "")
            if col is None:
                return None
            key.append(_num(row.get(col, "")))
        if None in key:
            return None
        if self.grid_column:
            key.append(grid)
        if self.arm_column:
            key.append(row.get(self.arm_column, ""))
        return tuple(key)


def _coords(item: dict[str, Any], position: int) -> dict[str, Any]:
    coords = item.get("coords") if isinstance(item, dict) else None
    if not isinstance(coords, dict):
        raise InvalidRequest(f"rows[{position}] needs a coords object")
    return coords


def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, 9) + 0.0


# --- table I/O ----------------------------------------------------------------------


def _header(table: Path) -> list[str]:
    with table.open(newline="") as fh:
        return next(csv.reader(fh), None) or []


def _rows(table: Path) -> Iterator[tuple[int, list[str], bytes]]:
    """Data rows with their index; the raw bytes of every line (header included) feed the table hash."""
    with table.open("rb") as raw:
        lines = _LineReader(raw)
        reader = csv.reader(lines)
        next(reader, None)
        index = 0
        for cells in reader:
            yield index, cells, lines.take()
            index += 1
        lines.take()


class _LineReader:
    """Decodes lines for ``csv.reader`` and keeps the bytes it handed out."""

    def __init__(self, raw: Any) -> None:
        self._raw = raw
        self._pending: list[bytes] = []

    def __iter__(self) -> _LineReader:
        return self

    def __next__(self) -> str:
        line = self._raw.readline()
        if not line:
            raise StopIteration
        self._pending.append(line)
        return str(line.decode("utf-8"))

    def take(self) -> bytes:
        out = b"".join(self._pending)
        self._pending = []
        return out


def _row_hash(cells: list[str]) -> str:
    return hashlib.sha256(json.dumps(cells, separators=(",", ":")).encode()).hexdigest()


def _rewrite(table: Path, updates: dict[int, tuple[_JobRow, dict[str, str]]]) -> tuple[set[int], set[int]]:
    with table.open("rb") as raw:
        terminator = "\r\n" if b"\r\n" in raw.readline() else "\n"
    tmp = table.with_name(f"{table.name}.tmp-{os.getpid()}")
    published: set[int] = set()
    stale: set[int] = set(updates)
    with table.open(newline="") as src, tmp.open("w", newline="") as dst:
        reader = csv.reader(src)
        writer = csv.writer(dst, lineterminator=terminator)
        header = next(reader)
        writer.writerow(header)
        pos = {c: i for i, c in enumerate(header)}
        for index, row in enumerate(reader):
            update = updates.get(index)
            if update is not None:
                jr, cells = update
                if _row_hash(row) == jr.row.row_hash:
                    for column, value in cells.items():
                        row[pos[column]] = value
                    published.add(index)
                    stale.discard(index)
            writer.writerow(row)
    os.replace(tmp, table)
    return published, stale


# --- values and parity -------------------------------------------------------------------


def _parse(text: str, kind: str) -> Any:
    if text == "":
        raise ValueError("empty cell")
    if kind == "string":
        return text
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"{text!r} is not a number") from exc
    if not number.is_finite():
        raise ValueError(f"{text!r} is not finite")
    if kind == "integer":
        if number != number.to_integral_value():
            raise ValueError(f"{text!r} is not an integer")
        return int(number)
    return float(number)


def _lookup(summary: dict[str, Any], path: str) -> Any:
    node: Any = summary
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def _parity(schema: ResultSchema, cells: dict[str, str], actual: dict[str, Any]) -> list[dict[str, Any]]:
    """Metric parity only: every result-binding column against the stored cell (fixed tolerance)."""
    formats = {m.column: m.format for m in schema.metrics}
    diffs: list[dict[str, Any]] = []
    for column, value in actual.items():
        expected_text = cells.get(column, "")
        expected = _decimal(expected_text)
        got = _decimal(value)
        if expected_text == "" and value is None:
            continue
        if expected is None or got is None:
            ok = False
        elif formats.get(column) == "integer":
            ok = expected == got
        else:
            e, a = float(expected), float(got)
            ok = abs(a - e) <= max(REL_TOL * max(abs(a), abs(e)), ABS_TOL)
        if not ok:
            diffs.append({"column": column, "expected": expected_text, "actual": _cell(value)})
    return diffs


# --- identities ---------------------------------------------------------------------------


def _token(table_sha256: str, block: MaterializeBlock, rows: list[_Row]) -> str:
    calculable = sorted((r.row_index, r.config_hash) for r in rows if r.reason is None)
    payload = json.dumps(
        {
            "table_sha256": table_sha256,
            "materialize_sha256": hashlib.sha256(
                json.dumps(block.model_dump(mode="json"), sort_keys=True).encode()
            ).hexdigest(),
            "rows": calculable,
        },
        sort_keys=True,
    )
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


def _batch_id(experiment_id: str, job_id: str, call: int) -> str:
    base = _ID_CHARS_RE.sub("_", f"calc-{experiment_id}")
    suffix = f"-{job_id[-12:]}-{call}"
    return (base[: 128 - len(suffix)] + suffix).lstrip("._-") or f"calc{suffix}"
