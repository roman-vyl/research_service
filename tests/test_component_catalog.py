from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from research_service.api.app import create_app
from research_service.runtime.settings import Settings
from research_service.runtime.wiring import Container


CATALOG = {
    "strategy_id": "ema_pullback",
    "schema_version": 1,
    "sections": [
        {"section_id": "direction", "label": "Direction", "role": "direction", "list_slot": False}
    ],
    "components": [
        {
            "component_id": "ema_anchor_stack_trend",
            "role": "direction",
            "allowed_roles": [],
            "label": "EMA anchor stack trend",
            "description": "Long when fast > anchor > slow; short mirrors.",
            "params_schema": {},
            "params_storage": "flat",
            "list_slot": False,
            "supports_context_consumption": False,
            "context_consumption_policies": [],
        }
    ],
    "context_providers": [],
    "context_consumption_roles": [],
}


class FakeStrategyEngine:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def health(self) -> bool:
        return True

    def get_composer_catalog(self, strategy_id: str):
        self.calls.append(strategy_id)
        return CATALOG


class HealthyMarket:
    def health(self) -> bool:
        return True


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def ensure_ready(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)


def make_client(tmp_path: Path, strategy: FakeStrategyEngine) -> TestClient:
    settings = Settings(artifacts_root=tmp_path, configs_root=tmp_path / "configs")
    return TestClient(
        create_app(
            settings,
            Container(settings, strategy, HealthyMarket(), ArtifactStore(tmp_path)),
        )
    )


def test_component_catalog_preserves_workbench_dto_and_uses_strategy_engine(tmp_path: Path) -> None:
    strategy = FakeStrategyEngine()
    response = make_client(tmp_path, strategy).get("/api/research/component-catalog")
    assert response.status_code == 200
    assert response.json() == CATALOG
    assert strategy.calls == ["ema_pullback"]


def test_component_catalog_is_cached_per_application(tmp_path: Path) -> None:
    strategy = FakeStrategyEngine()
    client = make_client(tmp_path, strategy)
    assert client.get("/api/research/component-catalog").status_code == 200
    assert client.get("/api/research/component-catalog").status_code == 200
    assert strategy.calls == ["ema_pullback"]


def test_component_catalog_rejects_unknown_strategy_id_without_upstream_call(tmp_path: Path) -> None:
    strategy = FakeStrategyEngine()
    response = make_client(tmp_path, strategy).get(
        "/api/research/component-catalog", params={"strategy_id": "unknown"}
    )
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_request"
    assert strategy.calls == []


class LegacyFamilyStrategyEngine:
    """Simulates a pre-cutover Engine response shape (`family` instead of
    `strategy_id`) to prove Research's strict catalog parser rejects it
    rather than silently accepting the old wire shape."""

    def health(self) -> bool:
        return True

    def get_composer_catalog(self, strategy_id: str):
        legacy = dict(CATALOG)
        del legacy["strategy_id"]
        legacy["family"] = "ema_pullback"
        return legacy


def test_component_catalog_rejects_legacy_family_wire_shape(tmp_path: Path) -> None:
    from pydantic import ValidationError

    from research_service.application.research.component_catalog import GetComponentCatalog

    use_case = GetComponentCatalog(LegacyFamilyStrategyEngine())
    with pytest.raises(ValidationError):
        use_case.execute()
