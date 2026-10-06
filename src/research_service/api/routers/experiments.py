"""Experiment routes: registry, manifest, results, storage (read-only) and run deletion."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, ConfigDict

from research_service.runtime.services import services

router = APIRouter(prefix="/api/research/experiments", tags=["experiments"])


@router.get("")
def list_experiments(request: Request) -> dict[str, Any]:
    return services(request).experiments.registry()


@router.get("/{experiment_id}")
def get_experiment(request: Request, experiment_id: str) -> dict[str, Any]:
    return services(request).experiments.manifest(experiment_id)


@router.get("/{experiment_id}/results")
def get_results(request: Request, experiment_id: str) -> dict[str, Any]:
    params = request.query_params
    columns_raw = params.get("columns")
    columns = [c for c in columns_raw.split(",") if c] if columns_raw else None
    filters = {k: v for k, v in params.items() if k != "columns"}
    return services(request).experiments.results(experiment_id, filters=filters, columns=columns)


@router.get("/{experiment_id}/storage")
def get_storage(
    request: Request,
    experiment_id: str,
    size: Literal["cached", "compute"] = Query("cached"),
) -> dict[str, Any]:
    return services(request).experiment_storage.storage(experiment_id, size)


class DeletePlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_ids: list[str]


class DeleteRunsRequest(DeletePlanRequest):
    plan_token: str


@router.post("/{experiment_id}/runs/delete-plan")
def plan_run_deletion(request: Request, experiment_id: str, body: DeletePlanRequest) -> dict[str, Any]:
    return services(request).run_deletion.plan(experiment_id, body.run_ids)


@router.post("/{experiment_id}/runs/delete")
def delete_runs(request: Request, experiment_id: str, body: DeleteRunsRequest) -> dict[str, Any]:
    return services(request).run_deletion.delete(experiment_id, body.run_ids, body.plan_token)
