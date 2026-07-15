"""Resolve Strategy Engine static exit policy into absolute entry protection."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Mapping, Sequence

from research_service.domain.contracts import StrategyEvaluationResult
from research_service.domain.errors import InvalidRequest
from research_service.domain.execution import EntryFill, InitialProtection


def _side_series(
    evaluation: StrategyEvaluationResult,
    *,
    field: str,
    side: str,
) -> Sequence[object]:
    raw = evaluation.exit_policy.get(field)
    if not isinstance(raw, Mapping):
        raise InvalidRequest(f"Strategy evaluation exit_policy.{field} must be an object")
    values = raw.get(side)
    if not isinstance(values, (list, tuple)):
        raise InvalidRequest(f"Strategy evaluation exit_policy.{field}.{side} must be a series")
    if len(values) != evaluation.bar_count:
        raise InvalidRequest(
            f"Strategy evaluation exit_policy.{field}.{side} length differs from market grid"
        )
    return values


def protection_ready_at(
    evaluation: StrategyEvaluationResult,
    *,
    side: str,
    bar_index: int,
) -> bool:
    """Return the legacy ``entries & stop_ready`` gate for one side/bar."""

    if side not in {"long", "short"}:
        raise InvalidRequest("side must be long or short")
    if bar_index < 0 or bar_index >= evaluation.bar_count:
        raise InvalidRequest("bar_index is outside the strategy evaluation")
    value = _side_series(evaluation, field="stop_ready", side=side)[bar_index]
    if not isinstance(value, bool):
        raise InvalidRequest("stop_ready values must be booleans")
    return value


def _ratio_at(
    evaluation: StrategyEvaluationResult,
    *,
    field: str,
    side: str,
    bar_index: int,
) -> Decimal | None:
    raw = _side_series(evaluation, field=field, side=side)[bar_index]
    if raw is None:
        return None
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError) as exc:
        raise InvalidRequest(f"{field}.{side} contains a non-decimal value") from exc
    if not value.is_finite() or value < 0:
        raise InvalidRequest(f"{field}.{side} ratios must be finite and non-negative")
    return value


def resolve_initial_protection(
    evaluation: StrategyEvaluationResult,
    entry_fill: EntryFill,
) -> InitialProtection:
    """Resolve entry-bar ratios into legacy-compatible absolute levels.

    BBB used VectorBT's default ``stop_entry_price=close`` and its managed loop
    also stored the signal-bar close as ``entry_price``. Therefore the bbb_v1
    protection anchor is ``entry_fill.reference_price`` rather than a
    slippage-adjusted fill price.
    """

    if entry_fill.instance_id != evaluation.instance_id:
        raise InvalidRequest("entry fill belongs to another strategy instance")
    if entry_fill.bar_index >= evaluation.bar_count:
        raise InvalidRequest("entry fill bar is outside the strategy evaluation")
    if not protection_ready_at(evaluation, side=entry_fill.side, bar_index=entry_fill.bar_index):
        raise InvalidRequest("initial protection is not ready on the entry bar")

    sl_ratio = _ratio_at(
        evaluation,
        field="stop_loss_ratio",
        side=entry_fill.side,
        bar_index=entry_fill.bar_index,
    )
    tp_ratio = _ratio_at(
        evaluation,
        field="take_profit_ratio",
        side=entry_fill.side,
        bar_index=entry_fill.bar_index,
    )
    anchor = entry_fill.reference_price
    one = Decimal("1")
    if entry_fill.side == "long":
        stop_price = anchor * (one - sl_ratio) if sl_ratio is not None else None
        take_price = anchor * (one + tp_ratio) if tp_ratio is not None else None
    else:
        stop_price = anchor * (one + sl_ratio) if sl_ratio is not None else None
        take_price = anchor * (one - tp_ratio) if tp_ratio is not None else None

    if stop_price is not None and stop_price <= 0:
        raise InvalidRequest("stop-loss ratio produces a non-positive price")
    if take_price is not None and take_price <= 0:
        raise InvalidRequest("take-profit ratio produces a non-positive price")

    return InitialProtection(
        side=entry_fill.side,
        source_bar_index=entry_fill.bar_index,
        source_time_ms=entry_fill.time_ms,
        anchor_price=anchor,
        stop_loss_ratio=sl_ratio,
        take_profit_ratio=tp_ratio,
        stop_loss_price=stop_price,
        take_profit_price=take_price,
    )
