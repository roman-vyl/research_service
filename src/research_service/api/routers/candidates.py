"""Candidate shortlist routes: list, star and unstar (``research-candidate-shortlist-v1``)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict

from research_service.domain.errors import RuntimeExportError
from research_service.runtime.services import services

router = APIRouter(prefix="/api/research/candidates", tags=["candidates"])


class StarRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experiment_id: str
    coords: dict[str, Any]


@router.get("")
def list_candidates(request: Request) -> dict[str, Any]:
    return services(request).candidates.list_all()


@router.put("")
def star_candidate(request: Request, body: StarRequest) -> dict[str, Any]:
    return services(request).candidates.star(body.experiment_id, body.coords)


@router.delete("/{candidate_id}")
def unstar_candidate(request: Request, candidate_id: str) -> dict[str, Any]:
    return services(request).candidates.unstar(candidate_id)


@router.post("/{candidate_id}/runtime-export", status_code=201)
async def export_to_runtime(request: Request, candidate_id: str) -> dict[str, Any]:
    """Create-only: no body, no query; the file is always written with ``enabled: false``."""
    if request.query_params or (await request.body()).strip():
        raise RuntimeExportError("export_takes_no_input", "runtime-export takes only the candidate id", 422)
    return await run_in_threadpool(services(request).candidates.runtime_export, candidate_id)
