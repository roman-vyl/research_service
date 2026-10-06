"""Experiment routes: registry, manifest, results, storage (read-only), run deletion and Calculate."""

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


class CalculateRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    coords: dict[str, Any]


class CalculatePlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rows: list[CalculateRow]


class CalculateRequest(CalculatePlanRequest):
    plan_token: str


@router.post("/{experiment_id}/runs/calculate-plan")
def plan_calculation(request: Request, experiment_id: str, body: CalculatePlanRequest) -> dict[str, Any]:
    return services(request).run_calculation.plan(experiment_id, [r.model_dump() for r in body.rows])


@router.post("/{experiment_id}/runs/calculate", status_code=202)
def calculate_runs(request: Request, experiment_id: str, body: CalculateRequest) -> dict[str, Any]:
    return services(request).run_calculation.calculate(
        experiment_id, [r.model_dump() for r in body.rows], body.plan_token
    )


@router.get("/{experiment_id}/calculations/{job_id}")
def get_calculation(request: Request, experiment_id: str, job_id: str) -> dict[str, Any]:
    return services(request).run_calculation.status(experiment_id, job_id)


@router.post("/{experiment_id}/calculations/{job_id}/cancel")
def cancel_calculation(request: Request, experiment_id: str, job_id: str) -> dict[str, Any]:
    return services(request).run_calculation.cancel(experiment_id, job_id)
