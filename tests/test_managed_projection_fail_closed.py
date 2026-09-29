"""`historical-managed-projection-v1` blocker fix: managed historical
execution must never silently degrade to the eliminated per-trade
`/managed-replay` path (`execution/projection_loop.py::
_resolve_managed_timeline`).

Required semantics, proven here through the real
`RunSingleInstanceBacktest` seam (not just the loop function directly):

A. managed candidate + `HistoricalManagedProjection` present
   -> local projection path, zero managed-replay HTTP calls.
B. managed candidate + `HistoricalManagedProjection` absent
   -> explicit failure, zero managed-replay HTTP calls (never a
      silent fallback).
C. explicit parity/oracle opt-in (`allow_legacy_managed_replay_fallback=True`,
   set only at `RunSingleInstanceBacktest`/`MaterializeBacktestProjectionOutcome`
   construction time -- never a request-body field) -> the old
   per-trade path is available, exactly as before this change.
"""

from __future__ import annotations

import pytest

from research_service.application.backtests import (
    RunSingleInstanceBacktest,
    SingleInstanceBacktestRequest,
)
from research_service.domain.contracts import ExplicitRange, HistoricalManagedProjectionDTO
from research_service.domain.errors import UpstreamServiceError
from test_single_instance_backtest import (
    FakeMarketData,
    FakeStrategyEngine,
    market_frame,
    strategy_identity,
    strategy_projection,
)


def test_a_managed_candidate_with_projection_uses_local_path_zero_replay_calls() -> None:
    projection = strategy_projection().model_copy(
        update={
            "managed": HistoricalManagedProjectionDTO(conditions={}, distances={}, rules=())
        }
    )
    strategy = FakeStrategyEngine(projection)
    use_case = RunSingleInstanceBacktest(strategy, FakeMarketData(market_frame()))

    outcome = use_case.execute(
        SingleInstanceBacktestRequest(
            strategy=strategy_identity(),
            range=ExplicitRange(from_ms=0, to_ms=900_000),
            managed_policy_enabled=True,
        )
    )

    assert strategy.managed_requests == []
    assert outcome.execution.positions[0].exit_fill is not None


def test_b_managed_candidate_without_projection_fails_closed_zero_replay_calls() -> None:
    # strategy_projection() carries no `managed` (the default) -- a
    # real Strategy Engine would only omit it for a non-managed spec,
    # so this reproduces exactly the "unexpectedly missing" scenario
    # the blocker report describes.
    strategy = FakeStrategyEngine(strategy_projection())
    use_case = RunSingleInstanceBacktest(strategy, FakeMarketData(market_frame()))

    with pytest.raises(UpstreamServiceError) as exc_info:
        use_case.execute(
            SingleInstanceBacktestRequest(
                strategy=strategy_identity(),
                range=ExplicitRange(from_ms=0, to_ms=900_000),
                managed_policy_enabled=True,
            )
        )

    assert "HistoricalManagedProjection" in exc_info.value.message
    # The whole point: it must fail before ever reaching the eliminated
    # per-trade call, not after a wasted one.
    assert strategy.managed_requests == []


def test_c_explicit_opt_in_restores_the_legacy_per_trade_path() -> None:
    strategy = FakeStrategyEngine(strategy_projection())
    use_case = RunSingleInstanceBacktest(
        strategy, FakeMarketData(market_frame()), allow_legacy_managed_replay_fallback=True
    )

    outcome = use_case.execute(
        SingleInstanceBacktestRequest(
            strategy=strategy_identity(),
            range=ExplicitRange(from_ms=0, to_ms=900_000),
            managed_policy_enabled=True,
        )
    )

    # Explicit opt-in restores exactly the old behaviour: one
    # /managed-replay call for the one opened position.
    assert len(strategy.managed_requests) == 1
    assert outcome.execution.positions[0].exit_fill is not None


def test_c2_explicit_opt_in_overrides_a_present_projection_too() -> None:
    """The oracle opt-in is a genuine override, not just a missing-
    `managed` rescue: even when the projection DOES carry `managed`
    (the real 5.2 scenario -- a genuine managed candidate run through
    both paths to diff them), `allow_legacy_managed_replay_fallback=True`
    must still force the per-trade path, never silently prefer the
    local one."""

    projection = strategy_projection().model_copy(
        update={
            "managed": HistoricalManagedProjectionDTO(conditions={}, distances={}, rules=())
        }
    )
    strategy = FakeStrategyEngine(projection)
    use_case = RunSingleInstanceBacktest(
        strategy, FakeMarketData(market_frame()), allow_legacy_managed_replay_fallback=True
    )

    outcome = use_case.execute(
        SingleInstanceBacktestRequest(
            strategy=strategy_identity(),
            range=ExplicitRange(from_ms=0, to_ms=900_000),
            managed_policy_enabled=True,
        )
    )

    assert len(strategy.managed_requests) == 1
    assert outcome.execution.positions[0].exit_fill is not None


def test_non_managed_candidate_is_unaffected_either_way() -> None:
    """Fail-closed only applies once a caller signals managed intent
    (`managed_policy_enabled=True`). A non-managed run must stay silent
    and untouched -- no error, no replay call, regardless of the
    projection's `managed` field."""

    strategy = FakeStrategyEngine(strategy_projection())
    use_case = RunSingleInstanceBacktest(strategy, FakeMarketData(market_frame()))

    outcome = use_case.execute(
        SingleInstanceBacktestRequest(
            strategy=strategy_identity(),
            range=ExplicitRange(from_ms=0, to_ms=900_000),
            managed_policy_enabled=False,
        )
    )

    assert strategy.managed_requests == []
    assert outcome.execution.positions[0].exit_fill is not None
