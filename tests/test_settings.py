from __future__ import annotations

import os
from pathlib import Path

import pytest

from research_service.runtime.settings import Settings


@pytest.fixture(autouse=True)
def _clear_research_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("RESEARCH_"):
            monkeypatch.delenv(key, raising=False)


def test_defaults_are_container_safe() -> None:
    settings = Settings()
    assert settings.host == "0.0.0.0"
    assert settings.port == 8080
    assert settings.strategy_engine_url == "http://strategy-engine:8080"
    assert settings.market_data_url == "http://market-data-service:8080"
    assert settings.artifacts_root == Path("/data/runs")
    assert settings.configs_root == Path("/data/configs")
    assert settings.cors_origins == (
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    )


def test_every_field_is_overridable_by_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RESEARCH_HOST", "127.0.0.1")
    monkeypatch.setenv("RESEARCH_PORT", "9090")
    monkeypatch.setenv("RESEARCH_STRATEGY_ENGINE_URL", "http://se.internal:8090")
    monkeypatch.setenv("RESEARCH_MARKET_DATA_URL", "http://mds.internal:8080")
    monkeypatch.setenv("RESEARCH_ARTIFACTS_ROOT", "/mnt/runs")
    monkeypatch.setenv("RESEARCH_CONFIGS_ROOT", "/mnt/configs")
    monkeypatch.setenv(
        "RESEARCH_CORS_ORIGINS", '["https://workbench.example.com"]'
    )

    settings = Settings()

    assert settings.host == "127.0.0.1"
    assert settings.port == 9090
    assert settings.strategy_engine_url == "http://se.internal:8090"
    assert settings.market_data_url == "http://mds.internal:8080"
    assert settings.artifacts_root == Path("/mnt/runs")
    assert settings.configs_root == Path("/mnt/configs")
    assert settings.cors_origins == ("https://workbench.example.com",)
