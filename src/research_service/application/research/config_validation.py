"""Validate a Workbench draft while delegating strategy semantics."""

from __future__ import annotations

from research_service.api.contracts.config import ValidationErrorItem, ValidationResult
from research_service.domain.config import StrategyConfigDraft
from research_service.ports.strategy_engine import StrategyEnginePort


class ValidateStrategyConfig:
    def __init__(self, strategy_engine: StrategyEnginePort) -> None:
        self._strategy_engine = strategy_engine

    def execute(self, draft: StrategyConfigDraft) -> ValidationResult:
        errors: list[ValidationErrorItem] = []
        if draft.config_version != 1:
            errors.append(ValidationErrorItem(path="config_version", message="must be 1"))
        if not draft.experiment_id.strip():
            errors.append(
                ValidationErrorItem(
                    path="experiment_id",
                    message="must be a non-empty string",
                )
            )
        family = draft.family.strip()
        if family != "ema_pullback":
            errors.append(
                ValidationErrorItem(
                    path="family",
                    message="unsupported family; supported: ema_pullback",
                )
            )
        execution = draft.execution
        if execution.init_cash is not None and execution.init_cash <= 0:
            errors.append(
                ValidationErrorItem(
                    path="execution.init_cash",
                    message="must be > 0",
                )
            )
        for name in ("fees", "slippage"):
            value = getattr(execution, name)
            if value is not None and value < 0:
                errors.append(
                    ValidationErrorItem(
                        path=f"execution.{name}",
                        message="must be >= 0",
                    )
                )
        if errors:
            return ValidationResult(ok=False, errors=errors)
        upstream = self._strategy_engine.validate_authoring_config(
            family,
            draft.instances,
        )
        return ValidationResult(
            ok=upstream.valid,
            errors=[
                ValidationErrorItem(path=error.path, message=error.message)
                for error in upstream.errors
            ],
        )
