"""HTTP adapter for Strategy Engine."""

from __future__ import annotations

import json
from collections.abc import Iterator
from decimal import Decimal
from typing import Any, cast

import httpx

from pydantic import ValidationError

from research_service.domain.contracts import (
    HistoricalExecutionProjectionDTO,
    ManagedBarDecision,
    ManagedReplayRequest,
    ManagedReplayResult,
    MarketRange,
    StrategyDiagnosticEvaluationDTO,
    StrategyEvaluationBatchRequest,
    StrategyEvaluationBatchVariantOutcome,
    StrategyEvaluationRequest,
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

    def close(self) -> None:
        self._client.close()

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

    def evaluate_range_projection(
        self,
        request: StrategyEvaluationRequest,
    ) -> HistoricalExecutionProjectionDTO:
        """`compact-strategy-evaluation-boundary-v1` I7: production
        single-instance path. Calls `/strategy-evaluations/range` --
        Engine's I7 cutover made this route serve `.v2` only -- and
        decodes via the real `parse_historical_execution_projection`."""

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
                "raw_spec": request.strategy_spec,
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
        return parse_historical_execution_projection(body)

    def evaluate_range_diagnostics(
        self,
        request: StrategyEvaluationRequest,
    ) -> StrategyDiagnosticEvaluationDTO:
        """Calls Engine's separate dense diagnostic contract -- unaffected
        by I7's `/range` cutover -- to build a run's separately persisted
        diagnostic artifact (`research-diagnostics-projection-v1`)."""

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
                "raw_spec": request.strategy_spec,
            },
        }
        body = self._post_json(
            "/v1/strategy-evaluations/range/diagnostics",
            payload,
            "Strategy Engine diagnostic evaluation request failed",
        )
        market_raw = body.get("market")
        if not isinstance(market_raw, dict):
            raise UpstreamServiceError(
                service="strategy_engine",
                status_code=502,
                message="Strategy Engine diagnostic evaluation field market is invalid",
            )
        market = MarketRange(
            ticker=str(market_raw.get("ticker", "")),
            timeframe=str(market_raw.get("base_timeframe", "")),
            from_ms=_int(market_raw.get("from_ms", -1)),
            to_ms=_int(market_raw.get("to_ms", -1)),
        )
        try:
            return StrategyDiagnosticEvaluationDTO(
                contract_version=cast(Any, body.get("contract_version")),
                strategy_id=str(body.get("strategy_id", "")),
                config_hash=str(body.get("config_hash", "")),
                market=market,
                market_data_hash=str(market_raw.get("market_data_hash", "")),
                bar_count=_int(market_raw.get("bar_count", -1)),
                features=_object(body, "features"),
                contexts=_object(body, "contexts"),
                potential_entries=_object(body, "potential_entries"),
                component_evidence=_object(body, "component_evidence"),
                warnings=tuple(str(value) for value in _list(body.get("warnings", []))),
            )
        except ValidationError as exc:
            raise UpstreamServiceError(
                service="strategy_engine",
                status_code=502,
                message="Strategy Engine diagnostic evaluation response is invalid",
                details={"errors": exc.errors(include_url=False, include_context=False)},
            ) from exc

    def evaluate_range_batch(
        self,
        request: StrategyEvaluationBatchRequest,
    ) -> Iterator[StrategyEvaluationBatchVariantOutcome]:
        """I8 (`compact-strategy-evaluation-boundary-v1`): streamed `.v2`
        sequence, not a buffered `.v1` array. This is a generator
        function (`yield from` below) -- calling it builds nothing and
        sends no request; the HTTP request, and Engine's shared
        `MarketFrame` acquisition/validation it triggers, only happen
        once the caller starts consuming the returned iterator (first
        `next()`/loop iteration). A terminal acquisition failure
        therefore surfaces on that first iteration step, before any
        element is produced -- no candidate is ever settled in that
        case. Once the response starts, each line is decoded and
        yielded one at a time; callers SHALL process (materialize/
        persist/release) each outcome before this generator produces
        the next -- it never buffers the full response."""

        payload: dict[str, object] = {
            "market": {
                "ticker": request.market.ticker,
                "base_timeframe": request.market.timeframe,
                "from_ms": request.market.from_ms,
                "to_ms": request.market.to_ms,
            },
            "expected_market_data_hash": request.expected_market_data_hash,
            "variants": [
                {
                    "variant_id": variant.variant_id,
                    "strategy": {
                        "strategy_id": variant.strategy_id,
                        "raw_spec": variant.strategy_spec,
                    },
                }
                for variant in request.variants
            ],
        }
        expected_variant_ids = [variant.variant_id for variant in request.variants]
        try:
            with self._client.stream(
                "POST", "/v1/strategy-evaluations/range-batch", json=payload
            ) as response:
                if response.status_code != 200:
                    response.read()
                    raise UpstreamServiceError(
                        service="strategy_engine",
                        status_code=response.status_code,
                        message="Strategy Engine range-batch evaluation request failed",
                        details={"body": _safe_json(response)},
                    )
                yield from self._consume_batch_stream(response, expected_variant_ids)
        except httpx.HTTPError as exc:
            raise UpstreamServiceError(
                service="strategy_engine", status_code=503, message=str(exc)
            ) from exc

    def _consume_batch_stream(
        self, response: httpx.Response, expected_variant_ids: list[str]
    ) -> Iterator[StrategyEvaluationBatchVariantOutcome]:
        seen: set[str] = set()
        expected_by_position = list(expected_variant_ids)
        position = 0
        for line in response.iter_lines():
            if not line:
                continue
            try:
                item = json.loads(line)
            except ValueError as exc:
                raise UpstreamServiceError(
                    service="strategy_engine",
                    status_code=502,
                    message="Strategy Engine range-batch stream element is not valid JSON",
                ) from exc
            if not isinstance(item, dict):
                raise UpstreamServiceError(
                    service="strategy_engine",
                    status_code=502,
                    message="Strategy Engine range-batch stream element is not an object",
                )
            variant_id = item.get("variant_id")
            if not isinstance(variant_id, str) or not variant_id:
                raise UpstreamServiceError(
                    service="strategy_engine",
                    status_code=502,
                    message="Strategy Engine range-batch stream element has no variant_id",
                )
            if position >= len(expected_by_position):
                raise UpstreamServiceError(
                    service="strategy_engine",
                    status_code=502,
                    message="Strategy Engine range-batch stream has more elements than requested",
                    details={"variant_id": variant_id},
                )
            if variant_id != expected_by_position[position]:
                raise UpstreamServiceError(
                    service="strategy_engine",
                    status_code=502,
                    message="Strategy Engine range-batch stream element is out of request order",
                    details={
                        "expected_variant_id": expected_by_position[position],
                        "actual_variant_id": variant_id,
                    },
                )
            if variant_id in seen:
                raise UpstreamServiceError(
                    service="strategy_engine",
                    status_code=502,
                    message="Strategy Engine range-batch stream has a duplicate variant_id",
                    details={"variant_id": variant_id},
                )
            seen.add(variant_id)
            position += 1

            result_raw = item.get("result")
            error_raw = item.get("error")
            if (result_raw is None) == (error_raw is None):
                raise UpstreamServiceError(
                    service="strategy_engine",
                    status_code=502,
                    message=(
                        "Strategy Engine range-batch stream element must carry exactly "
                        "one of result/error"
                    ),
                    details={"variant_id": variant_id},
                )
            result = (
                parse_historical_execution_projection(cast("dict[str, object]", result_raw))
                if isinstance(result_raw, dict)
                else None
            )
            error = error_raw if isinstance(error_raw, dict) else None
            yield StrategyEvaluationBatchVariantOutcome(
                variant_id=variant_id,
                result=result,
                error=cast("dict[str, object] | None", error),
            )

        missing = expected_variant_ids[position:]
        if missing:
            raise UpstreamServiceError(
                service="strategy_engine",
                status_code=502,
                message="Strategy Engine range-batch stream is missing candidate outcome(s)",
                details={"missing_variant_ids": missing},
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
                "raw_spec": request.strategy_spec,
            },
            "trade_id": request.trade_id,
            "side": request.side,
            "entry_time_ms": request.entry_time_ms,
            "entry_price": float(request.entry_price),
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


_HISTORICAL_EXECUTION_PROJECTION_CONTRACT_VERSION = "strategy_evaluation_execution.v2"


def parse_historical_execution_projection(body: dict[str, object]) -> HistoricalExecutionProjectionDTO:
    """Strict decode of Strategy Engine's `HistoricalExecutionProjection`
    wire shape (`strategy-research-execution-contract-v1`, I3 consumer
    foundation, `contract_version = "strategy_evaluation_execution.v2"`
    -- next version of the same envelope family
    `serialize_strategy_evaluation_execution` already ships as `.v1`).
    No `raw=body` retention -- see `HistoricalExecutionProjectionDTO`'s
    own docstring.

    The real wire envelope nests `bar_count`/`market_data_hash` inside
    `market{...}` alongside `base_timeframe` (Strategy Engine's own key
    name, not `timeframe`) -- this function translates that shape into
    `HistoricalExecutionProjectionDTO`'s flat fields and Research's own
    `MarketRange.timeframe`. A naive
    `HistoricalExecutionProjectionDTO.model_validate(body)` on the raw
    body would reject every real Engine response -- this function must
    not skip that translation step.

    Standalone rather than an `HttpStrategyEngineClient` method: Engine's
    `/range` route is not yet wired to this contract (route cutover is
    I7, `compact-strategy-evaluation-boundary-v1`'s master plan) -- there
    is no live endpoint to call yet. This function decodes whatever body
    a caller already has (a future route, or a test fixture), matching
    the pattern of this module's other pure `_parse_*`/`_object` helpers.
    """

    contract_version = body.get("contract_version")
    if contract_version != _HISTORICAL_EXECUTION_PROJECTION_CONTRACT_VERSION:
        raise UpstreamServiceError(
            service="strategy_engine",
            status_code=502,
            message="Strategy Engine historical execution projection has an unsupported "
            "contract_version",
            details={
                "expected": _HISTORICAL_EXECUTION_PROJECTION_CONTRACT_VERSION,
                "actual": contract_version,
            },
        )

    market_raw = body.get("market")
    if not isinstance(market_raw, dict):
        raise UpstreamServiceError(
            service="strategy_engine",
            status_code=502,
            message="Strategy Engine historical execution projection field market is invalid",
        )

    try:
        market = MarketRange(
            ticker=str(market_raw.get("ticker", "")),
            timeframe=str(market_raw.get("base_timeframe", "")),
            from_ms=_int(market_raw.get("from_ms", -1)),
            to_ms=_int(market_raw.get("to_ms", -1)),
        )
    except (ValidationError, TypeError, ValueError) as exc:
        raise UpstreamServiceError(
            service="strategy_engine",
            status_code=502,
            message="Strategy Engine historical execution projection market is invalid",
        ) from exc

    payload = {
        # Passed through, not discarded: the boundary check above already
        # rejected anything but the expected value, and
        # HistoricalExecutionProjectionDTO.contract_version (a `Literal`)
        # enforces it again on the DTO itself, matching the strict-DTO
        # form -- version identity is a property of the decoded object,
        # not just a parse-time gate.
        "contract_version": contract_version,
        "strategy_id": body.get("strategy_id"),
        "config_hash": body.get("config_hash"),
        "market": market,
        "market_data_hash": market_raw.get("market_data_hash"),
        "bar_count": market_raw.get("bar_count"),
        "entry_opportunities": body.get("entry_opportunities"),
        "signal_exit_events": body.get("signal_exit_events"),
        "warnings": body.get("warnings", []),
    }
    try:
        return HistoricalExecutionProjectionDTO.model_validate(payload)
    except ValidationError as exc:
        raise UpstreamServiceError(
            service="strategy_engine",
            status_code=502,
            message="Strategy Engine historical execution projection response is invalid",
            details={"errors": exc.errors(include_url=False, include_context=False)},
        ) from exc


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
