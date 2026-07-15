"""Research API BFF — sync backtest endpoint."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.workbench_api

from fastapi.testclient import TestClient

from research_api.main import app
from research_api.services import config_service

from tests.test_research_api_config import _valid_draft


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_backtest_rejects_without_draft_or_path(client: TestClient) -> None:
    res = client.post("/api/research/backtests", json={})
    assert res.status_code == 422


def test_backtest_rejects_draft_and_config_path(client: TestClient) -> None:
    res = client.post(
        "/api/research/backtests",
        json={"draft": _valid_draft(), "config_path": "ema_pullback/foo.json"},
    )
    assert res.status_code == 422


def test_backtest_rejects_invalid_draft(client: TestClient) -> None:
    draft = _valid_draft()
    draft["experiment_id"] = ""

    res = client.post("/api/research/backtests", json={"draft": draft})
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is False
    assert body["run_id"] is None
    assert body["errors"]


def test_backtest_from_draft_runs_runner(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path
    configs_root = tmp_path / "research" / "experiments" / "configs"
    monkeypatch.setattr(config_service, "_REPO_ROOT", repo_root)
    monkeypatch.setattr(config_service, "_CONFIGS_ROOT", configs_root)

    captured: dict[str, Path] = {}

    def fake_run(config_source_file: str | Path, *, db_path: Path | None = None) -> str:
        captured["path"] = Path(config_source_file)
        return "2026-05-17T120000Z_ema_pullback_BTCUSDT_5m"

    monkeypatch.setattr(
        "research_api.services.backtest_service.run_strategy_specs_from_config",
        fake_run,
    )

    res = client.post("/api/research/backtests", json={"draft": _valid_draft()})
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["run_id"] == "2026-05-17T120000Z_ema_pullback_BTCUSDT_5m"
    assert body["config_path"] == "research/experiments/configs/ema_pullback/api_config_smoke.json"
    assert captured["path"].name == "api_config_smoke.json"


def test_backtest_from_config_path(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path
    configs_root = tmp_path / "research" / "experiments" / "configs"
    family_dir = configs_root / "ema_pullback"
    family_dir.mkdir(parents=True)
    config_file = family_dir / "saved.json"
    config_file.write_text('{"schema_version": 1}', encoding="utf-8")

    monkeypatch.setattr(config_service, "_REPO_ROOT", repo_root)
    monkeypatch.setattr(config_service, "_CONFIGS_ROOT", configs_root)

    rel = "ema_pullback/saved.json"

    def fake_validate(path: Path) -> None:
        assert path.name == "saved.json"

    def fake_run(config_source_file: str | Path, *, db_path: Path | None = None) -> str:
        assert Path(config_source_file) == config_file.resolve()
        return "2026-05-17T130000Z_ema_pullback_BTCUSDT_5m"

    monkeypatch.setattr(
        "research_api.services.backtest_service.load_strategy_config_file",
        fake_validate,
    )
    monkeypatch.setattr(
        "research_api.services.backtest_service.run_strategy_specs_from_config",
        fake_run,
    )

    res = client.post("/api/research/backtests", json={"config_path": rel})
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["run_id"].endswith("_5m")


def test_backtest_rejects_path_outside_configs(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(*_args, **_kwargs) -> str:
        raise AssertionError("runner must not be called")

    monkeypatch.setattr(
        "research_api.services.backtest_service.run_strategy_specs_from_config",
        fake_run,
    )

    res = client.post(
        "/api/research/backtests",
        json={"config_path": "research/results/latest.json"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is False
    assert "configs" in body["errors"][0]["message"].lower()
