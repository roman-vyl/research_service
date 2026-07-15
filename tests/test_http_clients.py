import httpx
import pytest

from research_service.adapters.http.market_data_client import HttpMarketDataClient
from research_service.adapters.http.strategy_engine_client import HttpStrategyEngineClient
from research_service.domain.contracts import MarketRange, StrategyEvaluationRequest
from research_service.domain.errors import UpstreamServiceError


def test_market_data_client_parses_complete_decimal_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/candles"
        return httpx.Response(
            200,
            json={
                "ticker": "BTCUSDT.P",
                "timeframe": "1m",
                "from_ms": 0,
                "to_ms": 120000,
                "market_data_hash": "market-hash",
                "candles": [
                    {
                        "open_time_ms": 0,
                        "open": "1",
                        "high": "2",
                        "low": "1",
                        "close": "1.5",
                        "volume": "10",
                    },
                    {
                        "open_time_ms": 60000,
                        "open": "1.5",
                        "high": "2",
                        "low": "1",
                        "close": "1.7",
                        "volume": "11",
                    },
                ],
            },
        )

    client = HttpMarketDataClient("http://mds")
    client._client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://mds")
    frame = client.read_range(
        MarketRange(ticker="BTCUSDT.P", timeframe="1m", from_ms=0, to_ms=120_000)
    )
    assert str(frame.candles[0].close) == "1.5"


def test_strategy_engine_client_maps_result_and_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(
            200,
            json={
                "contract_version": "strategy_evaluation.v1",
                "strategy_id": "ema_pullback",
                "strategy_version": "v1",
                "instance_id": "x",
                "config_hash": "cfg",
                "market": {
                    "ticker": "BTCUSDT.P",
                    "base_timeframe": "5m",
                    "from_ms": 0,
                    "to_ms": 300000,
                    "bar_count": 1,
                    "market_data_hash": "md",
                },
                "features": {"time_ms": [0]},
                "contexts": {},
                "entries": {"long": [False]},
                "exit_policy": {
                    "signal_exit": {"long": [False], "short": [False]},
                    "stop_loss_ratio": {"long": [None], "short": [None]},
                    "take_profit_ratio": {"long": [None], "short": [None]},
                    "stop_ready": {"long": [False], "short": [False]},
                },
                "component_evidence": {},
                "validity": {},
                "state_artifact": None,
                "warnings": [],
            },
        )

    client = HttpStrategyEngineClient("http://strategy")
    client._client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="http://strategy"
    )
    result = client.evaluate_range(
        StrategyEvaluationRequest(
            strategy_id="ema_pullback",
            instance_id="x",
            strategy_spec={},
            market=MarketRange(
                ticker="BTCUSDT.P",
                timeframe="5m",
                from_ms=0,
                to_ms=300_000,
            ),
        )
    )
    assert result.config_hash == "cfg"
    assert result.market_data_hash == "md"
    assert client.health() is True

    def error_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "unavailable"})

    client._client = httpx.Client(
        transport=httpx.MockTransport(error_handler),
        base_url="http://strategy",
    )
    with pytest.raises(UpstreamServiceError):
        client.evaluate_range(
            StrategyEvaluationRequest(
                strategy_id="ema_pullback",
                instance_id="x",
                strategy_spec={},
                market=MarketRange(
                    ticker="BTCUSDT.P",
                    timeframe="5m",
                    from_ms=0,
                    to_ms=300_000,
                ),
            )
        )


def test_strategy_engine_client_reads_composer_catalog() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/strategies/ema_pullback/composer-catalog"
        return httpx.Response(
            200,
            json={
                "family": "ema_pullback",
                "schema_version": 1,
                "sections": [],
                "components": [],
                "context_providers": [],
                "context_consumption_roles": [],
            },
        )

    client = HttpStrategyEngineClient("http://strategy")
    client._client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="http://strategy"
    )
    body = client.get_composer_catalog("ema_pullback")
    assert body["family"] == "ema_pullback"
