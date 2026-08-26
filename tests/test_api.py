from pathlib import Path

from fastapi.testclient import TestClient

from research_service.api.app import create_app
from research_service.runtime.settings import Settings
from research_service.runtime.wiring import Container


class HealthyDependency:
    def health(self) -> bool:
        return True


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def ensure_ready(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)


def app(tmp_path: Path):
    settings = Settings(artifacts_root=tmp_path)
    dependency = HealthyDependency()
    return create_app(
        settings,
        Container(settings, dependency, dependency, ArtifactStore(tmp_path)),
    )


def test_health_readiness_and_openapi(tmp_path: Path) -> None:
    client = TestClient(app(tmp_path))
    assert client.get("/health").json() == {"status": "ok"}
    readiness = client.get("/readiness")
    assert readiness.status_code == 200
    assert readiness.json()["dependencies"] == {
        "strategy_engine": True,
        "market_data_service": True,
    }
    assert "/api/market/candles-window" in client.get("/openapi.json").json()["paths"]
    assert "/api/market/ema-window" in client.get("/openapi.json").json()["paths"]


def test_no_duplicate_method_path_route_registrations(tmp_path: Path) -> None:
    application = app(tmp_path)
    seen: set[tuple[str, str]] = set()
    duplicates: set[tuple[str, str]] = set()
    for route in application.routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        if methods is None or path is None:
            continue
        for method in methods:
            key = (method, path)
            if key in seen:
                duplicates.add(key)
            seen.add(key)
    assert duplicates == set()


class UnhealthyDependency:
    def health(self) -> bool:
        return False


def test_readiness_returns_503_when_dependency_is_down(tmp_path: Path) -> None:
    settings = Settings(artifacts_root=tmp_path)
    application = create_app(
        settings,
        Container(
            settings,
            UnhealthyDependency(),
            HealthyDependency(),
            ArtifactStore(tmp_path),
        ),
    )
    response = TestClient(application).get("/readiness")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
