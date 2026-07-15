"""Filesystem implementation for research artifacts."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Mapping
from uuid import uuid4

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class FilesystemArtifactStore:
    """Publish immutable run directories atomically on one filesystem."""

    def __init__(self, root: Path) -> None:
        self._root = root

    @property
    def root(self) -> Path:
        return self._root

    def ensure_ready(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        probe = self._root / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()

    def list_run_ids(self) -> tuple[str, ...]:
        self.ensure_ready()
        return tuple(
            sorted(
                path.name
                for path in self._root.iterdir()
                if path.is_dir()
                and path.name != "batches"
                and not path.name.startswith(".")
                and _SAFE_ID_RE.fullmatch(path.name)
                and (path / "manifest.json").is_file()
            )
        )

    def read_run_file(self, run_id: str, relative_name: str) -> bytes:
        if not _SAFE_ID_RE.fullmatch(run_id):
            raise FileNotFoundError(run_id)
        relative_path = Path(relative_name)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise FileNotFoundError(relative_name)
        target = self._root / run_id / relative_path
        if not target.is_file():
            raise FileNotFoundError(target)
        return target.read_bytes()

    def write_run_bundle(self, run_id: str, files: Mapping[str, bytes]) -> Path:
        self.ensure_ready()
        if not _SAFE_ID_RE.fullmatch(run_id):
            raise ValueError("run_id contains unsupported filesystem characters")
        if not files:
            raise ValueError("run bundle must contain at least one file")

        destination = self._root / run_id
        if destination.exists():
            raise FileExistsError(f"run artifacts already exist: {run_id}")

        temporary = self._root / f".{run_id}.tmp-{uuid4().hex}"
        temporary.mkdir(parents=False, exist_ok=False)
        try:
            for relative_name, payload in files.items():
                relative_path = Path(relative_name)
                if relative_path.is_absolute() or ".." in relative_path.parts:
                    raise ValueError(f"unsafe artifact path: {relative_name}")
                target = temporary / relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)

            # Publish only after every file is durable enough for the local
            # filesystem contract. Directory replacement is atomic when source
            # and destination share this parent filesystem.
            for path in temporary.rglob("*"):
                if path.is_file():
                    with path.open("rb") as handle:
                        os.fsync(handle.fileno())
            os.replace(temporary, destination)
            return destination
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise

    def write_batch_bundle(self, experiment_id: str, files: Mapping[str, bytes]) -> Path:
        self.ensure_ready()
        if not _SAFE_ID_RE.fullmatch(experiment_id):
            raise ValueError("experiment_id contains unsupported filesystem characters")
        if not files:
            raise ValueError("batch bundle must contain at least one file")

        batches_root = self._root / "batches"
        batches_root.mkdir(parents=True, exist_ok=True)
        destination = batches_root / experiment_id
        if destination.exists():
            raise FileExistsError(f"batch artifacts already exist: {experiment_id}")

        temporary = batches_root / f".{experiment_id}.tmp-{uuid4().hex}"
        temporary.mkdir(parents=False, exist_ok=False)
        try:
            for relative_name, payload in files.items():
                relative_path = Path(relative_name)
                if relative_path.is_absolute() or ".." in relative_path.parts:
                    raise ValueError(f"unsafe artifact path: {relative_name}")
                target = temporary / relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)
            for path in temporary.rglob("*"):
                if path.is_file():
                    with path.open("rb") as handle:
                        os.fsync(handle.fileno())
            os.replace(temporary, destination)
            return destination
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise
