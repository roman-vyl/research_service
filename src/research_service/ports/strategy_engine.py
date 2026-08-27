"""Strategy Engine consumer port."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from research_service.domain.contracts import (
    MarketRange,
    StrategyEvaluationBatchRequest,
    StrategyEvaluationBatchVariantOutcome,
    StrategyEvaluationRequest,
    StrategyEvaluationResult,
    ManagedReplayRequest,
    ManagedReplayResult,
)


@dataclass(frozen=True, slots=True)
class IndicatorSeriesResult:
    time_ms: tuple[int, ...]
    values: tuple[str | None, ...]
    plan_hash: str
    market_data_hash: str


class StrategyEnginePort(Protocol):
    def evaluate_range(
        self,
        request: StrategyEvaluationRequest,
    ) -> StrategyEvaluationResult: ...

    def evaluate_range_batch(
        self,
        request: StrategyEvaluationBatchRequest,
    ) -> tuple[StrategyEvaluationBatchVariantOutcome, ...]: ...

    def evaluate_managed_replay(
        self,
        request: ManagedReplayRequest,
    ) -> ManagedReplayResult: ...

    def evaluate_ema(
        self,
        market: MarketRange,
        *,
        period: int,
    ) -> IndicatorSeriesResult: ...

    def get_composer_catalog(self, strategy_id: str) -> dict[str, Any]: ...

    def validate_authoring_config(
        self, strategy_id: str, instances: list[dict[str, Any]]
    ) -> StrategyAuthoringValidationResult: ...

    def health(self) -> bool: ...


@dataclass(frozen=True, slots=True)
class StrategyValidationError:
    path: str
    message: str


@dataclass(frozen=True, slots=True)
class StrategyAuthoringValidationResult:
    valid: bool
    errors: tuple[StrategyValidationError, ...]
