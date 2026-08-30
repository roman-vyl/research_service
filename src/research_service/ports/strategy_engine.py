"""Strategy Engine consumer port."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Protocol

from research_service.domain.contracts import (
    HistoricalExecutionProjectionDTO,
    MarketRange,
    StrategyDiagnosticEvaluationDTO,
    StrategyEvaluationBatchRequest,
    StrategyEvaluationBatchVariantOutcome,
    StrategyEvaluationRequest,
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
    def evaluate_range_projection(
        self,
        request: StrategyEvaluationRequest,
    ) -> HistoricalExecutionProjectionDTO: ...

    def evaluate_range_diagnostics(
        self,
        request: StrategyEvaluationRequest,
    ) -> StrategyDiagnosticEvaluationDTO: ...

    def evaluate_range_batch(
        self,
        request: StrategyEvaluationBatchRequest,
    ) -> Iterator[StrategyEvaluationBatchVariantOutcome]:
        """I8 (`compact-strategy-evaluation-boundary-v1`): streamed, not
        buffered — the shared `MarketFrame` acquisition/validation SHALL
        complete before this returns; a terminal failure there raises
        directly. Iterating the returned generator drives one HTTP
        request whose body is consumed incrementally, one decoded variant
        outcome at a time — callers SHALL NOT materialize the full
        sequence before processing each element."""
        ...

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
