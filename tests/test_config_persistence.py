from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from research_service.api.app import create_app
from research_service.adapters.artifacts.filesystem import FilesystemArtifactStore
from research_service.ports.strategy_engine import StrategyAuthoringValidationResult
from research_service.runtime.wiring import Container
from research_service.runtime.settings import Settings


class StubStrategyEngine:
    def validate_authoring_config(
        self, family: str, instances: list[dict[str, object]]
    ) -> StrategyAuthoringValidationResult:
        return StrategyAuthoringValidationResult(valid=True, errors=())

    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"unexpected strategy call: {name}")


def draft(experiment_id: str = "baseline") -> dict[str, object]:
    return {
        "config_version": 1,
        "experiment_id": experiment_id,
        "family": "ema_pullback",
        "execution": {"init_cash": 10000.0, "fees": 0.0004},
        "instances": [{"instance_id": "baseline", "strategy": {}}],
    }


def client(tmp_path: Path) -> TestClient:
    settings = Settings(
        configs_root=tmp_path / "configs",
        artifacts_root=tmp_path / "runs",
    )
    return TestClient(
        create_app(
            settings=settings,
            container=Container(
                settings=settings,
                strategy_engine=StubStrategyEngine(),  # type: ignore[arg-type]
                market_data=object(),  # type: ignore[arg-type]
                artifacts=FilesystemArtifactStore(tmp_path / "runs"),
            ),
        )
    )


def test_serialize_and_save_round_trip(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        serialized = api.post("/api/research/config/serialize?format=json", json=draft())
        assert serialized.status_code == 200
        assert serialized.json()["ok"] is True
        assert json.loads(serialized.json()["content"])["experiment_id"] == "baseline"

        saved = api.post("/api/research/config/save", json={"draft": draft()})
        assert saved.status_code == 200
        assert saved.json() == {
            "ok": True,
            "path": "ema_pullback/baseline.json",
            "errors": [],
        }
        state = api.get("/api/research/configs/state?family=ema_pullback")
        assert state.status_code == 200
        body = state.json()
        assert body["selected_experiment_id"] == "baseline"
        assert body["draft"]["experiment_id"] == "baseline"
        assert len(body["configs"]) == 1


def test_select_switches_draft(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        api.post("/api/research/config/save", json={"draft": draft("first")})
        api.post("/api/research/config/save", json={"draft": draft("second")})
        selected = api.put(
            "/api/research/configs/selected",
            json={"family": "ema_pullback", "experiment_id": "first"},
        )
        assert selected.status_code == 200
        assert selected.json()["selected_experiment_id"] == "first"


def test_bad_family_and_path_are_rejected(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        response = api.get("/api/research/configs/state?family=../ema_pullback")
        assert response.status_code == 400
        response = api.post(
            "/api/research/config/save",
            json={"draft": draft("../escape")},
        )
        assert response.status_code == 400


def test_invalid_saved_file_is_listed_but_not_loaded(tmp_path: Path) -> None:
    root = tmp_path / "configs"
    family = root / "ema_pullback"
    family.mkdir(parents=True)
    (family / "broken.json").write_text("{broken", encoding="utf-8")
    (root / ".workbench_selection.json").write_text(
        json.dumps({"ema_pullback": "broken"}), encoding="utf-8"
    )
    with client(tmp_path) as api:
        body = api.get("/api/research/configs/state?family=ema_pullback").json()
        assert body["selected_experiment_id"] == "broken"
        assert body["draft"] is None
        assert len(body["configs"]) == 1
