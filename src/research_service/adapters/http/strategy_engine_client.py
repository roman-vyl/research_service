"""HTTP adapter for Strategy Engine."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, cast

import httpx

from research_service.domain.contracts import (
    ManagedBarDecision,
    ManagedReplayRequest,
    ManagedReplayResult,
    MarketRange,
    StrategyEvaluationRequest,
    StrategyEvaluationResult,
)
from research_service.domain.errors import UpstreamServiceError
from research_service.ports.strategy_engine import (
    IndicatorSeriesResult,
    StrategyAuthoringValidationResult,
    StrategyValidationError,
)


class HttpStrategyEngineClient:
    def __init__(self, base_url: str, timeout_seconds: float = 60.0) -> None:
        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout_seconds)

    def health(self) -> bool:
        try:
            response = self._client.get("/health")
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def get_composer_catalog(self, strategy_id: str) -> dict[str, object]:
        try:
            response = self._client.get(f"/v1/strategies/{strategy_id}/composer-catalog")
        except httpx.HTTPError as exc:
            raise UpstreamServiceError(
                service="strategy_engine",
                status_code=503,
                message=str(exc),
            ) from exc
        if response.status_code != 200:
            raise UpstreamServiceError(
                service="strategy_engine",
                status_code=response.status_code,
                message="Strategy Engine composer catalog request failed",
                details={"body": _safe_json(response)},
            )
        body = response.json()
        if not isinstance(body, dict):
            raise UpstreamServiceError(
                service="strategy_engine",
                status_code=502,
                message="Strategy Engine composer catalog response is invalid",
            )
        return body

    def validate_authoring_config(
        self, strategy_id: str, instances: list[dict[str, object]]
    ) -> StrategyAuthoringValidationResult:
        try:
            response = self._client.post(
                f"/v1/strategies/{strategy_id}/authoring-config/validate",
                json={"instances": instances},
            )
        except httpx.HTTPError as exc:
            raise UpstreamServiceError(
                service="strategy_engine", status_code=503, message=str(exc)
            ) from exc
        if response.status_code != 200:
            raise UpstreamServiceError(
                service="strategy_engine",
                status_code=response.status_code,
                message="Strategy Engine config validation request failed",
                details={"body": _safe_json(response)},
            )
        body = response.json()
        errors = tuple(
            StrategyValidationError(
                path=str(item.get("path", "")),
                message=str(item.get("message", "")),
            )
            for item in body.get("errors", [])
        )
        return StrategyAuthoringValidationResult(
            valid=bool(body.get("valid", False)), errors=errors
        )

    def evaluate_range(
        self,
        request: StrategyEvaluationRequest,
    ) -> StrategyEvaluationResult:
        payload: dict[str, object] = {
            "market": {
                "ticker": request.market.ticker,
                "base_timeframe": request.market.timeframe,
                "from_ms": request.market.from_ms,
                "to_ms": request.market.to_ms,
            },
            "expected_market_data_hash": request.expected_market_data_hash,
            "strategy": {
                "strategy_id": request.strategy_id,
                "strategy_version": request.strategy_version,
                "instance_id": request.instance_id,
                "raw_spec": request.strategy_spec,
                "compatibility_profile": request.compatibility_profile,
            },
            "options": {
                "include_features": request.include_features,
                "include_contexts": request.include_contexts,
                "include_component_evidence": request.include_component_evidence,
                "include_state_artifact": False,
            },
        }
        body = self._post_json(
            "/v1/strategy-evaluations/range",
            payload,
            "Strategy Engine range evaluation request failed",
        )
        market = _object(body, "market")
        features = _object(body, "features")
        entries_raw = _object(body, "entries")
        entries = {
            str(side): tuple(bool(value) for value in values)
            for side, values in entries_raw.items()
            if isinstance(values, list)
        }
        parsed_market = MarketRange(
            ticker=str(market.get("ticker", "")),
            timeframe=str(market.get("base_timeframe", "")),
            from_ms=_int(market.get("from_ms", -1)),
            to_ms=_int(market.get("to_ms", -1)),
        )
        return StrategyEvaluationResult(
            contract_version=str(body.get("contract_version", "")),
            strategy_id=str(body.get("strategy_id", "")),
            strategy_version=str(body.get("strategy_version", "")),
            instance_id=str(body.get("instance_id", "")),
            config_hash=str(body.get("config_hash", "")),
            market=parsed_market,
            bar_count=_int(market.get("bar_count", -1)),
            market_data_hash=str(market.get("market_data_hash", "")),
            time_ms=tuple(_int(value) for value in _list(features.get("time_ms", []))),
            entries=entries,
            exit_policy=_object(body, "exit_policy"),
            component_evidence=_object(body, "component_evidence"),
            raw=body,
        )

    def evaluate_managed_replay(
        self,
        request: ManagedReplayRequest,
    ) -> ManagedReplayResult:
        payload = {
            "market": {
                "ticker": request.market.ticker,
                "base_timeframe": request.market.timeframe,
                "from_ms": request.market.from_ms,
                "to_ms": request.market.to_ms,
            },
            "strategy": {
                "strategy_id": request.strategy_id,
                "strategy_version": request.strategy_version,
                "instance_id": request.instance_id,
                "raw_spec": request.strategy_spec,
                "compatibility_profile": request.compatibility_profile,
            },
            "trade_id": request.trade_id,
            "side": request.side,
            "entry_time_ms": request.entry_time_ms,
            "entry_price": str(request.entry_price),
        }
        body = self._post_json(
            "/v1/strategy-evaluations/managed-replay",
            payload,
            "Strategy Engine managed replay request failed",
        )
        bars = tuple(
            ManagedBarDecision(
                time_ms=_int(item["time_ms"]),
                bar_index=_int(item["bar_index"]),
                phase=str(item["phase"]),
                bars_in_trade=_int(item["bars_in_trade"]),
                mfe_pct=Decimal(str(item["mfe_pct"])),
                mae_pct=Decimal(str(item["mae_pct"])),
                active_stop_price=(
                    None
                    if item.get("active_stop_price") is None
                    else Decimal(str(item["active_stop_price"]))
                ),
                active_take_profile=str(item["active_take_profile"]),
                runtime_exit_rule_ids=tuple(
                    str(value) for value in _list(item.get("runtime_exit_rule_ids", []))
                ),
                effective_from_time_ms=(
                    None
                    if item.get("effective_from_time_ms") is None
                    else _int(item["effective_from_time_ms"])
                ),
            )
            for item in cast("list[dict[str, object]]", body.get("bars", []))
        )
        return ManagedReplayResult(
            contract_version=str(body.get("contract_version", "")),
            decision_timing=str(body.get("decision_timing", "")),
            trade_id=str(body.get("trade_id", "")),
            side=str(body.get("side", "")),
            entry_time_ms=_int(body.get("entry_time_ms", -1)),
            bars=bars,
            events=tuple(dict(item) for item in _list(body.get("events", [])) if isinstance(item, dict)),
            final_state=_object(body, "final_state"),
            raw=body,
        )

    def evaluate_ema(
        self,
        market: MarketRange,
        *,
        period: int,
    ) -> IndicatorSeriesResult:
        output_id = f"chart_ema_{market.timeframe}_{period}"
        payload = {
            "market": {
                "ticker": market.ticker,
                "base_timeframe": market.timeframe,
                "from_ms": market.from_ms,
                "to_ms": market.to_ms,
            },
            "plan": {
                "plan_version": "1",
                "features": [
                    {
                        "output_id": output_id,
                        "kind": "ema",
                        "timeframe": "base",
                        "source": "close",
                        "parameters": {"period": period},
                        "dependencies": [],
                    }
                ],
            },
        }
        body = self._post_json(
            "/v1/indicator-evaluations/range",
            payload,
            "Strategy Engine indicator request failed",
        )
        raw_series = cast("dict[str, object]", body["series"])
        return IndicatorSeriesResult(
            time_ms=tuple(_int(value) for value in _list(body["time_ms"])),
            values=tuple(
                None if value is None else str(value) for value in _list(raw_series[output_id])
            ),
            plan_hash=str(body["plan_hash"]),
            market_data_hash=str(body["market_data_hash"]),
        )

    def _post_json(
        self,
        path: str,
        payload: dict[str, object],
        error_message: str,
    ) -> dict[str, object]:
        try:
            response = self._client.post(path, json=payload)
        except httpx.HTTPError as exc:
            raise UpstreamServiceError(
                service="strategy_engine", status_code=503, message=str(exc)
            ) from exc
        if response.status_code != 200:
            raise UpstreamServiceError(
                service="strategy_engine",
                status_code=response.status_code,
                message=error_message,
                details={"body": _safe_json(response)},
            )
        body = response.json()
        if not isinstance(body, dict):
            raise UpstreamServiceError(
                service="strategy_engine",
                status_code=502,
                message="Strategy Engine response is not an object",
            )
        return body


def _int(value: object) -> int:
    """Coerce a raw JSON scalar to int with the built-in's own semantics.

    ``cast`` here only satisfies the type checker: ``value`` came from a
    ``dict[str, object]`` produced by ``response.json()``, so mypy cannot
    prove it is int-convertible ahead of time, but ``int(...)`` itself still
    raises exactly as before on a malformed upstream value.
    """

    return int(cast(Any, value))


def _list(value: object) -> list[object]:
    """Coerce a raw JSON array to a typed list for iteration; see ``_int``."""

    return cast("list[object]", value)


def _object(body: dict[str, object], key: str) -> dict[str, object]:
    value = body.get(key)
    if not isinstance(value, dict):
        raise UpstreamServiceError(
            service="strategy_engine",
            status_code=502,
            message=f"Strategy Engine response field {key} is invalid",
        )
    return value


def _safe_json(response: httpx.Response) -> object:
    try:
        return response.json()
    except ValueError:
        return response.text
