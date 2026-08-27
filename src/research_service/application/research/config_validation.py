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
        strategy_id = draft.strategy_id.strip()
        if strategy_id != "ema_pullback":
            errors.append(
                ValidationErrorItem(
                    path="strategy_id",
                    message="unsupported strategy_id; supported: ema_pullback",
                )
            )
        # An experiment/config explores one strategy type: every candidate
        # instance in it MUST be that same strategy_id. Mixing strategy
        # types inside one experiment is not a supported grouping.
        for index, instance in enumerate(draft.instances):
            if instance.strategy_id != draft.strategy_id:
                errors.append(
                    ValidationErrorItem(
                        path=f"instances[{index}].strategy_id",
                        message=(
                            f"must match draft.strategy_id ({draft.strategy_id!r}); "
                            f"got {instance.strategy_id!r}"
                        ),
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
        # Each `draft.instances` entry is already a validated
        # `DeployableStrategyInstance` by the time it reaches this method —
        # `extra="forbid"` on that type rejects `family`/`variant`/
        # `strategy_version`/`instance_id` and requires `strategy_id`
        # before this code runs at all (canonical-strategy-instance-v1,
        # "Canonical instance shape per draft entry"). `enabled` does not
        # affect this delegated Strategy Engine validation either way.
        upstream = self._strategy_engine.validate_authoring_config(
            strategy_id,
            [instance.model_dump(mode="json") for instance in draft.instances],
        )
        return ValidationResult(
            ok=upstream.valid,
            errors=[
                ValidationErrorItem(path=error.path, message=error.message)
                for error in upstream.errors
            ],
        )
