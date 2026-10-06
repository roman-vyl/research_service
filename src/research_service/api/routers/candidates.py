"""Candidate shortlist routes: list, star and unstar (``research-candidate-shortlist-v1``)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict

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
