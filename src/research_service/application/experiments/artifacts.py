"""Persistence of immutable batch summaries."""

from __future__ import annotations

import hashlib
import json

from research_service.application.experiments.contracts import (
    BatchExperimentRequest,
    BatchExperimentResult,
    PersistedBatchArtifacts,
)
from research_service.ports.artifacts import BatchArtifactStore


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


class PersistBatchExperiment:
    def __init__(self, store: BatchArtifactStore) -> None:
        self._store = store

    def execute(
        self,
        request: BatchExperimentRequest,
        result: BatchExperimentResult,
    ) -> PersistedBatchArtifacts:
        if request.experiment_id != result.experiment_id:
            raise ValueError("request and result experiment_id differ")
        request_payload = _json_bytes(request.model_dump(mode="json"))
        result_payload = _json_bytes(result.model_dump(mode="json"))
        summary_hash = hashlib.sha256(result_payload).hexdigest()
        destination = self._store.write_batch_bundle(
            request.experiment_id,
            {
                "request.json": request_payload,
                "summary.json": result_payload,
                "manifest.json": _json_bytes(
                    {
                        "contract_version": "research_batch_artifacts.v1",
                        "experiment_id": request.experiment_id,
                        "summary_sha256": summary_hash,
                        "candidate_count": result.candidate_count,
                        "completed_count": result.completed_count,
                        "failed_count": result.failed_count,
                    }
                ),
            },
        )
        return PersistedBatchArtifacts(
            experiment_id=request.experiment_id,
            artifact_path=str(destination),
            summary_sha256=summary_hash,
        )
