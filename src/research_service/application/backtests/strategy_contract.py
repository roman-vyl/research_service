"""Acceptance checks for the Strategy Engine → Research Service execution seam."""

from __future__ import annotations

from dataclasses import dataclass

from research_service.domain.contracts import MarketFrame, StrategyEvaluationResult
from research_service.domain.errors import InvalidRequest


@dataclass(frozen=True, slots=True)
class StrategyExecutionContractAcceptance:
    bar_count: int
    sides: tuple[str, ...]
    market_data_hash: str
    static_exit_fields: tuple[str, ...]
    managed_replay_required: bool


def accept_strategy_execution_contract(
    evaluation: StrategyEvaluationResult,
    market_frame: MarketFrame,
) -> StrategyExecutionContractAcceptance:
    """Prove that a range response can drive the future execution simulator.

    This validates identity and per-bar decision alignment. It intentionally does
    not execute fills or trades.
    """

    if evaluation.market != market_frame.market:
        raise InvalidRequest("Strategy Engine and MDS market ranges differ")

    candle_times = tuple(candle.open_time_ms for candle in market_frame.candles)
    if evaluation.time_ms != candle_times:
        raise InvalidRequest("Strategy Engine and MDS bar identities differ")

    required_exit_fields = (
        "signal_exit",
        "stop_loss_ratio",
        "take_profit_ratio",
        "stop_ready",
    )
    missing = tuple(key for key in required_exit_fields if key not in evaluation.exit_policy)
    if missing:
        raise InvalidRequest(
            "Strategy Engine exit policy is incomplete",
            details={"missing_fields": list(missing)},
        )

    bar_count = len(candle_times)
    _validate_side_series(evaluation.exit_policy["signal_exit"], bar_count, "signal_exit")
    _validate_side_series(evaluation.exit_policy["stop_loss_ratio"], bar_count, "stop_loss_ratio")
    _validate_side_series(
        evaluation.exit_policy["take_profit_ratio"], bar_count, "take_profit_ratio"
    )
    _validate_side_series(evaluation.exit_policy["stop_ready"], bar_count, "stop_ready")

    if not evaluation.market_data_hash:
        raise InvalidRequest("Strategy Engine response lacks market_data_hash")

    if market_frame.market_data_hash is None:
        raise InvalidRequest("MDS response lacks market_data_hash")
    if evaluation.market_data_hash != market_frame.market_data_hash:
        raise InvalidRequest(
            "Strategy Engine and MDS market_data_hash differ",
            details={"code": "market_data_hash_mismatch"},
        )

    return StrategyExecutionContractAcceptance(
        bar_count=bar_count,
        sides=tuple(sorted(evaluation.entries)),
        market_data_hash=evaluation.market_data_hash,
        static_exit_fields=required_exit_fields,
        managed_replay_required=True,
    )


def _validate_side_series(value: object, bar_count: int, path: str) -> None:
    if not isinstance(value, dict):
        raise InvalidRequest(f"{path} must be an object")
    for side in ("long", "short"):
        series = value.get(side)
        if not isinstance(series, list) or len(series) != bar_count:
            raise InvalidRequest(f"{path}.{side} must contain one value per market bar")
