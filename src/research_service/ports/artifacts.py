"""Research artifact storage ports."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Protocol


class ArtifactStore(Protocol):
    @property
    def root(self) -> Path: ...

    def ensure_ready(self) -> None: ...


class RunArtifactStore(ArtifactStore, Protocol):
    """Atomic persistence boundary for one immutable research run bundle."""

    def write_run_bundle(
        self,
        run_id: str,
        files: Mapping[str, bytes],
    ) -> Path: ...

    def write_run_supplementary_file(
        self,
        run_id: str,
        relative_name: str,
        payload: bytes,
    ) -> Path:
        """Write one file into an already-published run directory, outside
        the atomic manifest-tracked bundle -- for artifacts generated after
        the run itself was persisted (e.g. the diagnostic artifact,
        `research-diagnostics-projection-v1`: "a separate, explicit
        operation from reading"). Does not touch or re-verify the existing
        manifest-tracked files."""
        ...


class BatchArtifactStore(ArtifactStore, Protocol):
    """Atomic persistence boundary for one immutable batch bundle."""

    def write_batch_bundle(
        self,
        experiment_id: str,
        files: Mapping[str, bytes],
    ) -> Path: ...


class RunArtifactReader(ArtifactStore, Protocol):
    """Read immutable run bundles published by the run artifact writer."""

    def list_run_ids(self) -> tuple[str, ...]: ...

    def read_run_file(self, run_id: str, relative_name: str) -> bytes: ...


class ResearchArtifactStore(RunArtifactStore, BatchArtifactStore, RunArtifactReader, Protocol):
    """Combined artifact capability used by the application container."""
