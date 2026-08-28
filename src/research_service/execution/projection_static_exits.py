"""Projection-driven static/signal exit candidate collection (I4,
`compact-strategy-evaluation-boundary-v1`).

Parallel to `execution/static_exits.py`, additive. Reuses
`_distance_fill_price` (imported, not reimplemented) for the exact
stop/take OHLC-gap fill-price mechanics -- unchanged. What I4 replaces
is the *source of strategy facts*:

- stop/take: no per-bar series re-read after entry -- the position's
  already-stored `initial_protection` prices/attribution (resolved
  once, at fill) are checked against OHLC every bar, exactly as the
  legacy path already does.
- signal: looked up by `(position.side, position.locked_exit_profile,
  bar_index)` against the projection index -- the position's own
  locked profile, never the current bar's active profile. This is the
  I4 semantic fix; see `test_i4_execution_parity.py`'s negative-control
  test for the adversarial proof that this actually matters.

Arbitration priority (`stop_loss < managed_stop < take_profit < ... <
signal`) is untouched -- `execution/unified_exits.py`'s
`_CANDIDATE_PRIORITY`/`arbitrate_unified_exit_candidates` is reused
unchanged by the projection loop; this module only *collects*
candidates.
"""

from __future__ import annotations

from research_service.domain.contracts import Candle, HistoricalExecutionProjectionIndex
from research_service.domain.errors import InvalidRequest
from research_service.domain.execution import ExitCandidate, PositionState
from research_service.execution.static_exits import _distance_fill_price


def collect_projection_static_exit_candidates(
    index: HistoricalExecutionProjectionIndex,
    position: PositionState,
    candle: Candle,
    *,
    bar_index: int,
) -> tuple[ExitCandidate, ...]:
    """Collect SL, TP and locked-profile signal candidates for a
    position open at bar start -- the projection-driven counterpart to
    `execution/static_exits.py::collect_static_exit_candidates`."""

    if position.locked_exit_profile is None:
        raise InvalidRequest("position has no locked_exit_profile to look up signal exits by")
    if bar_index < 0 or bar_index >= index.projection.bar_count:
        raise InvalidRequest("bar_index is outside the historical execution projection")
    if bar_index <= position.entry_fill.bar_index:
        return ()

    protection = position.initial_protection
    candidates: list[ExitCandidate] = []

    if protection.stop_loss_price is not None:
        price = _distance_fill_price(
            position.side,
            candle,
            level=protection.stop_loss_price,
            is_loss=True,
        )
        if price is not None:
            attribution = protection.stop_loss_attribution
            candidates.append(
                ExitCandidate(
                    candidate_type="stop_loss",
                    layer="exit_policy",
                    bar_index=bar_index,
                    time_ms=candle.open_time_ms,
                    reference_level=protection.stop_loss_price,
                    fill_price=price,
                    reason="stop_loss",
                    rule_id=None if attribution is None else attribution.rule_id,
                    component_id=None if attribution is None else attribution.component_id,
                    exit_kind=None if attribution is None else attribution.exit_kind,
                )
            )

    if protection.take_profit_price is not None:
        price = _distance_fill_price(
            position.side,
            candle,
            level=protection.take_profit_price,
            is_loss=False,
        )
        if price is not None:
            attribution = protection.take_profit_attribution
            candidates.append(
                ExitCandidate(
                    candidate_type="take_profit",
                    layer="exit_policy",
                    bar_index=bar_index,
                    time_ms=candle.open_time_ms,
                    reference_level=protection.take_profit_price,
                    fill_price=price,
                    reason="take_profit",
                    rule_id=None if attribution is None else attribution.rule_id,
                    component_id=None if attribution is None else attribution.component_id,
                    exit_kind=None if attribution is None else attribution.exit_kind,
                )
            )

    event = index.lookup_signal_event(position.side, position.locked_exit_profile, bar_index)
    if event is not None:
        # Engine's candidates are already in canonical declared order
        # (always_on first, then the locked profile's own rules, in
        # their declared list order) -- the first candidate is the
        # old-BBB-compatible attribution winner. Research does not
        # re-sort, re-select, or invent its own priority among them.
        winner = event.candidates[0]
        candidates.append(
            ExitCandidate(
                candidate_type="signal",
                layer="exit_policy",
                bar_index=bar_index,
                time_ms=candle.open_time_ms,
                reference_level=candle.close,
                fill_price=candle.close,
                reason="signal",
                rule_id=winner.attribution.rule_id,
                component_id=winner.attribution.component_id,
                exit_kind=winner.attribution.exit_kind,
            )
        )

    return tuple(candidates)
