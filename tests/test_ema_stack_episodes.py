"""`research-market-ema-stack-episodes-v1`: thin proxy to Strategy Engine
`POST /v1/ema-stack-episodes/history`, through the app and the real HTTP
client on a mocked Engine transport."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
from fastapi.testclient import TestClient

from research_service.adapters.http.strategy_engine_client import HttpStrategyEngineClient
from research_service.api.app import create_app
from research_service.runtime.settings import Settings
from research_service.runtime.wiring import Container

ROUTE = "/api/market/ema-stack-episodes/history"

REQUEST: dict[str, Any] = {
    "market": {"ticker": "BTCUSDT.P", "base_timeframe": "5m"},
    "episode": {"fast_period": 200, "anchor_period": 500, "slow_period": 1000},
    "side": "long",
    "page": {"before_start_ms": 1_700_000_000_000, "limit": 2},
    "expected_market_data_hash": "h1",
}

ENGINE_PAGE: dict[str, Any] = {
    "history_id": "hid",
    "params": {
        "fast_period": 200,
        "anchor_period": 500,
        "slow_period": 1000,
        "window_bars": 24,
        "break_bars": 24,
    },
    "params_hash": "ph",
    "market_data_hash": "h1",
    "earliest_ms": 1_614_556_800_000,
    "as_of_ms": 1_791_500_000_000,
    "side": "long",
    "episodes": [
        {
            "start_ms": 1_699_000_000_000,
            "stack_break_ms": 1_699_500_000_000,
            "censored": False,
            "touches": 1,
            "false_breaks_count": 0,
            "zones": [{"number": 1, "start": 1_699_100_000_000, "low": "35012.5"}],
            "false_breaks": [],
            "waves": [{"origin": 1_699_000_300_000, "origin_price": "34001.1"}],
        }
    ],
    "next_before_start_ms": 1_699_000_000_000,
    "current": {
        "start_ms": 1_790_000_000_000,
        "stack_break_ms": None,
        "touch_number": 3,
        "phase": "in_zone",
    },
}


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def ensure_ready(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)


class NoMarketData:
    def health(self) -> bool:
        return True


def make_client(tmp_path: Path, handler: Callable[[httpx.Request], httpx.Response]) -> TestClient:
    engine = HttpStrategyEngineClient("http://strategy")
    engine._client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="http://strategy"
    )
    settings = Settings(artifacts_root=tmp_path, configs_root=tmp_path / "configs")
    container = Container(settings, engine, NoMarketData(), ArtifactStore(tmp_path))  # type: ignore[arg-type]
    return TestClient(create_app(settings, container))


def test_body_forwarded_and_response_returned_unchanged(tmp_path: Path) -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=ENGINE_PAGE)

    response = make_client(tmp_path, handler).post(ROUTE, json=REQUEST)

    assert response.status_code == 200
    assert response.json() == ENGINE_PAGE
    assert len(calls) == 1
    assert calls[0].method == "POST"
    assert calls[0].url.path == "/v1/ema-stack-episodes/history"
    assert json.loads(calls[0].content) == REQUEST


def test_parameters_are_not_validated_or_defaulted(tmp_path: Path) -> None:
    sent: list[Any] = []
    body = {**REQUEST, "episode": {"fast_period": 1000, "anchor_period": 500, "extra": 1}}

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, json=ENGINE_PAGE)

    make_client(tmp_path, handler).post(ROUTE, json=body)

    assert sent == [body]


def test_no_cache_of_its_own(tmp_path: Path) -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=ENGINE_PAGE)

    client = make_client(tmp_path, handler)
    client.post(ROUTE, json=REQUEST)
    client.post(ROUTE, json=REQUEST)

    assert len(calls) == 2


def _engine_error(status: int, error: str, details: dict[str, Any]) -> dict[str, Any]:
    return {"error": error, "message": error, "details": details, "request_id": "engine-req"}


def test_engine_errors_passed_through_with_status_and_body(tmp_path: Path) -> None:
    cases = [
        (
            409,
            _engine_error(
                409,
                "market_data_version_changed",
                {"expected_market_data_hash": "h1", "market_data_hash": "h2"},
            ),
        ),
        (422, _engine_error(422, "invalid_request", {"errors": [{"loc": ["episode"]}]})),
        (503, _engine_error(503, "market_stream_not_ready", {"state": "loading"})),
        (500, _engine_error(500, "internal_error", {})),
    ]
    for status, body in cases:
        client = make_client(tmp_path, lambda _r, s=status, b=body: httpx.Response(s, json=b))
        response = client.post(ROUTE, json=REQUEST)
        assert response.status_code == status
        assert response.json() == body


def test_non_json_engine_error_keeps_status(tmp_path: Path) -> None:
    client = make_client(tmp_path, lambda _r: httpx.Response(503, text="upstream down"))

    response = client.post(ROUTE, json=REQUEST)

    assert response.status_code == 503
    payload = response.json()
    assert payload["error"] == "upstream_service_error"
    assert payload["details"]["upstream_status"] == 503
    assert payload["details"]["body"] == "upstream down"


def test_engine_unreachable_is_503(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    response = make_client(tmp_path, handler).post(ROUTE, json=REQUEST)

    assert response.status_code == 503
    assert response.json()["error"] == "dependency_unavailable"
    assert response.json()["details"]["service"] == "strategy_engine"


def test_non_object_success_body_is_502(tmp_path: Path) -> None:
    client = make_client(tmp_path, lambda _r: httpx.Response(200, json=[1, 2]))

    response = client.post(ROUTE, json=REQUEST)

    assert response.status_code == 502
    assert response.json()["error"] == "upstream_service_error"
