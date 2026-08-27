import json
from decimal import Decimal

import httpx
import pytest

from research_service.adapters.http.strategy_engine_client import HttpStrategyEngineClient
from research_service.application.backtests.strategy_contract import (
    accept_strategy_execution_contract,
)
from research_service.domain.contracts import (
    Candle,
    ManagedReplayRequest,
    MarketFrame,
    MarketRange,
    StrategyEvaluationRequest,
)
from research_service.domain.errors import InvalidRequest


def range_response() -> dict[str, object]:
    return {
        "contract_version": "strategy_evaluation.v1",
        "strategy_id": "ema_pullback",
        "config_hash": "cfg-hash",
        "market": {
            "ticker": "BTCUSDT.P",
            "base_timeframe": "5m",
            "from_ms": 0,
            "to_ms": 600_000,
            "bar_count": 2,
            "market_data_hash": "market-hash",
        },
        "features": {
            "time_ms": [0, 300_000],
            "series": {},
            "validity": {},
            "plan_hash": "plan-hash",
            "market_data_hash": "market-hash",
            "mappings": {},
        },
        "contexts": {},
        "entries": {"long": [False, True], "short": [False, False]},
        "exit_policy": {
            "signal_exit": {"long": [False, False], "short": [False, False]},
            "stop_loss_ratio": {"long": ["0.01", "0.01"], "short": ["0.01", "0.01"]},
            "take_profit_ratio": {"long": ["0.03", "0.03"], "short": ["0.03", "0.03"]},
            "stop_ready": {"long": [True, True], "short": [True, True]},
        },
        "component_evidence": {},
        "validity": {"stage": "decisions_ready"},
        "state_artifact": None,
        "warnings": [],
    }


def managed_response() -> dict[str, object]:
    return {
        "contract_version": "managed_policy_replay.v1",
        "decision_timing": "end_of_bar_effective_next_bar",
        "trade_id": "trade-1",
        "side": "long",
        "entry_time_ms": 0,
        "events": [],
        "bars": [
            {
                "time_ms": 0,
                "bar_index": 0,
                "phase": "initial_risk",
                "bars_in_trade": 1,
                "mfe_pct": "0.01",
                "mae_pct": "0.005",
                "active_stop_price": None,
                "active_take_profile": "initial",
                "runtime_exit_rule_ids": [],
                "effective_from_time_ms": 300_000,
            },
            {
                "time_ms": 300_000,
                "bar_index": 1,
                "phase": "protected",
                "bars_in_trade": 2,
                "mfe_pct": "0.02",
                "mae_pct": "0.005",
                "active_stop_price": "100.5",
                "active_take_profile": "initial",
                "runtime_exit_rule_ids": [],
                "effective_from_time_ms": None,
            },
        ],
        "final_state": {"phase": "protected"},
    }


def test_real_strategy_engine_wire_contract_is_consumable() -> None:
    seen: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content.decode("utf-8")))
        if request.url.path == "/v1/strategy-evaluations/range":
            return httpx.Response(200, json=range_response())
        if request.url.path == "/v1/strategy-evaluations/managed-replay":
            return httpx.Response(200, json=managed_response())
        raise AssertionError(request.url.path)

    client = HttpStrategyEngineClient("http://strategy")
    client._client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="http://strategy"
    )
    market = MarketRange(ticker="BTCUSDT.P", timeframe="5m", from_ms=0, to_ms=600_000)
    evaluation = client.evaluate_range(
        StrategyEvaluationRequest(
            strategy_id="ema_pullback",
            instance_id="instance-1",
            strategy_spec={"trade_sides": ["long", "short"]},
            market=market,
        )
    )
    assert set(seen[0]["strategy"]) == {"strategy_id", "raw_spec"}
    assert seen[0]["strategy"]["raw_spec"] == {"trade_sides": ["long", "short"]}
    assert seen[0]["market"]["base_timeframe"] == "5m"
    assert evaluation.market_data_hash == "market-hash"
    assert evaluation.entries["long"] == (False, True)
    assert evaluation.instance_id == "instance-1"

    managed = client.evaluate_managed_replay(
        ManagedReplayRequest(
            strategy_id="ema_pullback",
            strategy_spec={},
            market=market,
            trade_id="trade-1",
            side="long",
            entry_time_ms=0,
            entry_price=Decimal("100"),
        )
    )
    assert set(seen[1]["strategy"]) == {"strategy_id", "raw_spec"}
    assert managed.bars[0].effective_from_time_ms == 300_000
    assert managed.bars[-1].effective_from_time_ms is None


def test_execution_contract_matches_mds_bar_identity() -> None:
    market = MarketRange(ticker="BTCUSDT.P", timeframe="5m", from_ms=0, to_ms=600_000)
    client = HttpStrategyEngineClient("http://strategy")
    client._client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=range_response())),
        base_url="http://strategy",
    )
    evaluation = client.evaluate_range(
        StrategyEvaluationRequest(
            strategy_id="ema_pullback",
            instance_id="instance-1",
            strategy_spec={},
            market=market,
        )
    )
    frame = MarketFrame(
        market=market,
        candles=(
            Candle(open_time_ms=0, open="100", high="101", low="99", close="100.5", volume="1"),
            Candle(
                open_time_ms=300_000, open="100.5", high="102", low="100", close="101", volume="2"
            ),
        ),
        market_data_hash="market-hash",
    )
    accepted = accept_strategy_execution_contract(evaluation, frame)
    assert accepted.bar_count == 2
    assert accepted.static_exit_fields == (
        "signal_exit",
        "stop_loss_ratio",
        "take_profit_ratio",
        "stop_ready",
    )

    wrong_frame = MarketFrame(
        market=MarketRange(ticker="ETHUSDT.P", timeframe="5m", from_ms=0, to_ms=600_000),
        candles=(
            Candle(open_time_ms=0, open="1", high="1", low="1", close="1", volume="1"),
            Candle(open_time_ms=300_000, open="1", high="1", low="1", close="1", volume="1"),
        ),
    )
    with pytest.raises(InvalidRequest):
        accept_strategy_execution_contract(evaluation, wrong_frame)
