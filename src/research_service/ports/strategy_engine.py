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
        buffered. This method itself only builds the request -- the
        actual HTTP call, and Engine's shared `MarketFrame` acquisition/
        validation it triggers, do not happen until the caller starts
        consuming the returned iterator (first `next()`/loop iteration).
        A terminal acquisition failure therefore surfaces on that first
        iteration step, before any element is produced -- callers SHALL
        NOT materialize the full sequence before processing each
        element, and SHALL NOT assume the request has been sent, or
        succeeded, merely because this method returned."""
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
