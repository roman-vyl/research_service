"""Create-only export of a candidate's strategy spec to the Strategy Runtime catalog.

(``research-candidate-runtime-export-v1``.) Research writes one new deployment file with
``enabled: false`` and never changes, enables, disables or deletes an existing one. The
catalog is scanned with Strategy Runtime's own rules and identity formula so that a file
Runtime would reject or ignore is neither counted nor allowed to block an export.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import logging
import os
import re
import secrets
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_service.domain.errors import RuntimeExportError

LOG = logging.getLogger(__name__)

LOCK_FILE = ".runtime_export.lock"
LOCK_TIMEOUT_SECONDS = 10.0
_FORBIDDEN_FIELDS = ("strategy_instance_id", "strategy_version", "compatibility_profile")
_REQUIRED_STRINGS = ("ticker", "base_timeframe", "strategy_id")
_CANDIDATE_ID = re.compile(r"^cand_[0-9a-f]{24}$")
_SLUG_MAX = 40
_NAME_MAX_BYTES = 255


@dataclass(frozen=True, slots=True)
class CatalogFile:
    name: str
    identity: str
    enabled: bool


def runtime_identity(strategy_id: str, ticker: str, base_timeframe: str, raw_spec: dict[str, Any]) -> str:
    """Strategy Runtime's ``derive_strategy_instance_id`` (copied contract, pinned by a test)."""
    payload = {
        "strategy_id": strategy_id,
        "ticker": ticker,
        "base_timeframe": base_timeframe,
        "raw_spec": raw_spec,
    }
    canonical = json.dumps(
        payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return f"{strategy_id}:{hashlib.sha256(canonical).hexdigest()[:24]}"


def spec_fields(spec: Any) -> dict[str, Any] | None:
    """The four deployment fields of a stored strategy, or None if they are not all usable."""
    if not isinstance(spec, dict):
        return None
    for name in _REQUIRED_STRINGS:
        value = spec.get(name)
        if not isinstance(value, str) or not value.strip():
            return None
    if not isinstance(spec.get("raw_spec"), dict):
        return None
    return {k: spec[k] for k in (*_REQUIRED_STRINGS, "raw_spec")}


def spec_identity(spec: Any) -> str | None:
    fields = spec_fields(spec)
    if fields is None:
        return None
    try:
        return runtime_identity(fields["strategy_id"], fields["ticker"], fields["base_timeframe"], fields["raw_spec"])
    except (TypeError, ValueError):
        return None


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite number {value}")


def _accepted(document: Any) -> dict[str, Any] | None:
    """The document if Strategy Runtime would accept it as a deployment, else None."""
    if not isinstance(document, dict):
        return None
    if any(f in document for f in _FORBIDDEN_FIELDS):
        return None
    if not isinstance(document.get("enabled"), bool):
        return None
    return document if spec_fields(document) is not None else None


def scan_catalog(directory: Path) -> list[CatalogFile]:
    """Accepted deployment files of ``directory`` in name order (Runtime's selection rules)."""
    names = sorted(
        p.name
        for p in directory.iterdir()
        if p.is_file() and not p.name.startswith(".") and p.suffix == ".json"
    )
    found: list[CatalogFile] = []
    for name in names:
        try:
            document = json.loads((directory / name).read_text(encoding="utf-8"), parse_constant=_reject_constant)
        except (OSError, ValueError):
            continue
        accepted = _accepted(document)
        if accepted is None:
            continue
        identity = spec_identity(accepted)
        if identity is not None:
            found.append(CatalogFile(name, identity, accepted["enabled"]))
    return found


def file_name(ticker: str, candidate_id: str) -> str:
    if not _CANDIDATE_ID.match(candidate_id):
        raise RuntimeExportError("runtime_invalid_name", "stored candidate id has an unexpected shape", 500)
    slug = re.sub(r"[^a-z0-9]+", "_", ticker.lower()).strip("_")[:_SLUG_MAX].strip("_") or "spec"
    name = f"{slug}-{candidate_id}.json"
    if "/" in name or "\\" in name or name.startswith(".") or len(name.encode()) > _NAME_MAX_BYTES:
        raise RuntimeExportError("runtime_invalid_name", "file name is not safe", 500)
    return name


class RuntimeCatalogExport:
    def __init__(self, catalog: Path | None, lock_dir: Path) -> None:
        self._catalog = catalog
        self._lock_path = lock_dir / LOCK_FILE
        self._thread_lock = threading.Lock()

    @property
    def configured(self) -> bool:
        return self._catalog is not None

    # --- listing -----------------------------------------------------------------

    def snapshot(self) -> list[CatalogFile] | None:
        """Accepted files, or None when the catalog is unset or unreadable."""
        if self._catalog is None:
            return None
        try:
            return scan_catalog(self._catalog)
        except OSError:
            return None

    @staticmethod
    def status(files: list[CatalogFile] | None, spec: Any) -> dict[str, Any] | None:
        """``current.runtime``: what the directory holds, nothing about Runtime itself."""
        identity = spec_identity(spec)
        if files is None or identity is None:
            return None
        same = [f for f in files if f.identity == identity]
        if not same:
            return {"present": False}
        if len(same) > 1:
            return {"present": True, "duplicate": True, "files": [f.name for f in same]}
        return {"present": True, "file": same[0].name, "enabled": same[0].enabled}

    # --- export ------------------------------------------------------------------

    def export(self, record: dict[str, Any]) -> dict[str, Any]:
        directory = self._directory()
        snapshot = record.get("strategy_spec_snapshot")
        spec = snapshot.get("spec") if isinstance(snapshot, dict) else None
        fields = spec_fields(spec)
        if fields is None:
            raise RuntimeExportError(
                "no_strategy_spec", "the candidate has no strategy spec to export", 409,
                {"candidate_id": record["candidate_id"]},
            )
        identity = runtime_identity(fields["strategy_id"], fields["ticker"], fields["base_timeframe"], fields["raw_spec"])
        name = file_name(fields["ticker"], record["candidate_id"])
        document = {
            "enabled": False,
            **fields,
            "research_source": {
                "candidate_id": record["candidate_id"],
                "experiment_id": record["experiment_id"],
                "coords": record["coords"],
                "run_id": record.get("snapshot", {}).get("run_id"),
                "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        }
        payload = (json.dumps(document, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
        with self._exclusive():
            try:
                same = [f.name for f in scan_catalog(directory) if f.identity == identity]
            except OSError as exc:
                raise RuntimeExportError("runtime_catalog_unavailable", f"catalog cannot be read: {exc}", 503) from exc
            if same:
                raise RuntimeExportError(
                    "runtime_duplicate", "a file with this Runtime identity is already in the catalog", 409,
                    {"files": same, "strategy_instance_id": identity},
                )
            self._publish(directory, name, payload)
        return {"candidate_id": record["candidate_id"], "file": name, "strategy_instance_id": identity, "enabled": False}

    def _directory(self) -> Path:
        if self._catalog is None:
            raise RuntimeExportError("runtime_catalog_unconfigured", "RESEARCH_RUNTIME_SPECS_PATH is not set", 503)
        if not self._catalog.is_dir():
            raise RuntimeExportError("runtime_catalog_unavailable", "the Runtime catalog is not a readable directory", 503)
        return self._catalog

    @contextlib.contextmanager
    def _exclusive(self) -> Iterator[None]:
        deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
        if not self._thread_lock.acquire(timeout=LOCK_TIMEOUT_SECONDS):
            raise RuntimeExportError("runtime_export_busy", "another export is running", 503)
        fd = -1
        try:
            try:
                fd = os.open(self._lock_path, os.O_RDWR | os.O_CREAT, 0o644)
            except OSError as exc:
                raise RuntimeExportError("runtime_write_failed", f"export lock cannot be opened: {exc}", 500) from exc
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise RuntimeExportError("runtime_export_busy", "another export is running", 503) from None
                    time.sleep(0.05)
            yield
        finally:
            if fd >= 0:
                os.close(fd)  # closing releases the flock
            self._thread_lock.release()

    @staticmethod
    def _publish(directory: Path, name: str, payload: bytes) -> None:
        final = directory / name
        if final.resolve().parent != directory.resolve():
            raise RuntimeExportError("runtime_invalid_name", "file name leaves the catalog directory", 500)
        tmp = directory / f".{name}.tmp-{os.getpid()}-{secrets.token_hex(4)}"
        created = False
        try:
            try:
                fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
                created = True
                try:
                    os.fchmod(fd, 0o644)
                    view = memoryview(payload)
                    while view:
                        view = view[os.write(fd, view):]
                    os.fsync(fd)
                finally:
                    os.close(fd)
            except OSError as exc:
                raise RuntimeExportError("runtime_write_failed", f"export file cannot be written: {exc}", 500) from exc
            try:
                os.link(tmp, final)
            except FileExistsError as exc:
                raise RuntimeExportError(
                    "runtime_file_exists", "a file with this name already exists", 409, {"file": name}
                ) from exc
            except OSError as exc:
                raise RuntimeExportError("runtime_publish_failed", f"export file cannot be published: {exc}", 500) from exc
            with contextlib.suppress(OSError):
                dfd = os.open(directory, os.O_RDONLY)
                try:
                    os.fsync(dfd)
                finally:
                    os.close(dfd)
        finally:
            if created:
                try:
                    os.unlink(tmp)
                except FileNotFoundError:
                    pass
                except OSError as exc:
                    LOG.warning("runtime export: temporary file %s was not removed: %s", tmp.name, exc)
