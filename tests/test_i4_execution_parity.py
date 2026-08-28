"""I4 -- Research: Execution Parity / locked exit profile + attribution
restoration (`compact-strategy-evaluation-boundary-v1`, Master Plan).

Execution-loop-level parity tests for `run_projection_execution_loop`
(`execution/projection_loop.py`) against a profile-sensitive adversarial
`HistoricalExecutionProjectionDTO`, built directly (not via HTTP/JSON --
I3 already covers wire decode) since I4's own scope is execution
semantics, not transport.

Covers: locked-profile capture and persistence across a 10+ bar drift,
initial-protection resolution (stop/take/both-null), attribution
restoration on stop/take/signal exits, multi-candidate declared-order
winner selection, long and short direction, a negative control proving
the profile-drift fixture actually distinguishes locked-profile from
current-profile lookup, existing same-bar arbitration priority
regression, and managed-policy architectural isolation.

Not covered here (out of I4 scope): production HTTP cutover,
`/range-batch`, persistence (I6), N=1 E2E (I5), fee/PnL/equity.
"""

from __future__ import annotations

from decimal import Decimal

from research_service.domain.contracts import (
    Candle,
    ExecutableEntryOpportunityDTO,
    ExitAttributionDTO,
    HistoricalExecutionProjectionDTO,
    HistoricalExecutionProjectionIndex,
    InitialProtectionLegDTO,
    ManagedBarDecision,
    ManagedReplayResult,
    MarketFrame,
    MarketRange,
    SignalExitCandidateDTO,
    SignalExitEventDTO,
    SignalExitProjectionDTO,
)
from research_service.domain.execution import ExecutionPolicy
from research_service.execution.projection_loop import run_projection_execution_loop
from research_service.execution.unified_exits import _CANDIDATE_PRIORITY

_MARKET_RANGE = MarketRange(ticker="BTCUSDT.P", timeframe="5m", from_ms=0, to_ms=300_000 * 15)
_POLICY = ExecutionPolicy()


def _candle(i: int, o: str, h: str, lo: str, c: str) -> Candle:
    return Candle(
        open_time_ms=i * 300_000,
        open=Decimal(o),
        high=Decimal(h),
        low=Decimal(lo),
        close=Decimal(c),
        volume=Decimal("10"),
    )


def _flat_candles(bar_count: int, price: str = "100") -> list[Candle]:
    return [_candle(i, price, price, price, price) for i in range(bar_count)]


def _attribution(kind: str, rule_id: str, component_id: str = "c") -> ExitAttributionDTO:
    return ExitAttributionDTO(rule_id=rule_id, component_id=component_id, exit_kind=kind)


def _leg(ratio: float, kind: str, rule_id: str) -> InitialProtectionLegDTO:
    return InitialProtectionLegDTO(ratio=ratio, attribution=_attribution(kind, rule_id))


def _empty_profile_events() -> dict[str, tuple[SignalExitEventDTO, ...]]:
    return {"aligned": (), "countertrend": (), "neutral": ()}


def _projection_index(
    *,
    bar_count: int,
    entry_opportunities: list[ExecutableEntryOpportunityDTO],
    long_signal_events: dict[str, tuple[SignalExitEventDTO, ...]] | None = None,
    short_signal_events: dict[str, tuple[SignalExitEventDTO, ...]] | None = None,
) -> HistoricalExecutionProjectionIndex:
    market = MarketRange(ticker="BTCUSDT.P", timeframe="5m", from_ms=0, to_ms=300_000 * bar_count)
    projection = HistoricalExecutionProjectionDTO(
        contract_version="strategy_evaluation_execution.v2",
        strategy_id="ema_pullback",
        config_hash="cfg",
        market=market,
        market_data_hash="hash",
        bar_count=bar_count,
        entry_opportunities=tuple(entry_opportunities),
        signal_exit_events=SignalExitProjectionDTO(
            long=long_signal_events or _empty_profile_events(),
            short=short_signal_events or _empty_profile_events(),
        ),
        warnings=(),
    )
    return HistoricalExecutionProjectionIndex.build(projection)


def _market_frame(candles: list[Candle]) -> MarketFrame:
    market = MarketRange(ticker="BTCUSDT.P", timeframe="5m", from_ms=0, to_ms=300_000 * len(candles))
    return MarketFrame(market=market, candles=tuple(candles), market_data_hash="hash")


# --- stop exit: attribution + price -----------------------------------


def test_stop_exit_uses_stored_attribution_and_correct_price() -> None:
    candles = _flat_candles(5)
    candles[1] = _candle(1, "95", "96", "85", "94")
    opportunity = ExecutableEntryOpportunityDTO(
        bar_index=0,
        side="long",
        locked_exit_profile="aligned",
        initial_stop=_leg(0.1, "stop_loss", "sl_aligned"),
        initial_take=_leg(0.2, "take_profit", "tp_aligned"),
    )
    index = _projection_index(bar_count=5, entry_opportunities=[opportunity])
    result = run_projection_execution_loop(
        "inst", index, _market_frame(candles), _POLICY
    )
    (closed,) = result.positions
    assert closed.position.locked_exit_profile == "aligned"
    assert closed.exit_fill is not None
    assert closed.exit_fill.candidate_type == "stop_loss"
    assert closed.exit_fill.bar_index == 1
    assert closed.exit_fill.fill_price == Decimal("90")
    assert closed.exit_fill.rule_id == "sl_aligned"
    assert closed.exit_fill.exit_kind == "stop_loss"
    assert closed.exit_fill.layer == "exit_policy"


# --- take exit: attribution + price, stop leg null ---------------------


def test_take_exit_uses_stored_attribution_with_null_stop_leg() -> None:
    candles = _flat_candles(5)
    candles[1] = _candle(1, "105", "115", "104", "112")
    opportunity = ExecutableEntryOpportunityDTO(
        bar_index=0,
        side="long",
        locked_exit_profile="aligned",
        initial_stop=None,
        initial_take=_leg(0.1, "take_profit", "tp_aligned"),
    )
    index = _projection_index(bar_count=5, entry_opportunities=[opportunity])
    result = run_projection_execution_loop(
        "inst", index, _market_frame(candles), _POLICY
    )
    (closed,) = result.positions
    assert closed.position.initial_protection.stop_loss_price is None
    assert closed.exit_fill is not None
    assert closed.exit_fill.candidate_type == "take_profit"
    assert closed.exit_fill.fill_price == Decimal("110")
    assert closed.exit_fill.rule_id == "tp_aligned"
    assert closed.exit_fill.exit_kind == "take_profit"


# --- managed-policy disable_initial_tp: corrective pass -----------------


def _disable_tp_replay(position_id: str, side: str, entry_time_ms: int) -> ManagedReplayResult:
    bar0_time = entry_time_ms
    bar1_time = entry_time_ms + 300_000
    bars = (
        ManagedBarDecision(
            time_ms=bar0_time,
            bar_index=0,
            phase="initial_risk",
            bars_in_trade=1,
            mfe_pct=Decimal("0"),
            mae_pct=Decimal("0"),
            active_stop_price=None,
            active_take_profile="disable_initial_tp",
            runtime_exit_rule_ids=(),
            effective_from_time_ms=bar1_time,
        ),
        ManagedBarDecision(
            time_ms=bar1_time,
            bar_index=1,
            phase="initial_risk",
            bars_in_trade=2,
            mfe_pct=Decimal("0"),
            mae_pct=Decimal("0"),
            active_stop_price=None,
            active_take_profile="disable_initial_tp",
            runtime_exit_rule_ids=(),
            effective_from_time_ms=None,
        ),
    )
    return ManagedReplayResult(
        contract_version="managed_policy_replay.v1",
        decision_timing="end_of_bar_effective_next_bar",
        trade_id=position_id,
        side=side,
        entry_time_ms=entry_time_ms,
        bars=bars,
        events=(),
        final_state={},
        raw={},
    )


def test_disable_initial_tp_suppresses_the_stored_take_profit_candidate() -> None:
    # Bug reproduced pre-fix: the projection collector never received
    # managed_state.active_take_profile, so the stored initial TP fired
    # even though managed policy had disabled it.
    candles = _flat_candles(3)
    candles[1] = _candle(1, "105", "115", "104", "112")  # would hit take_price=110
    opportunity = ExecutableEntryOpportunityDTO(
        bar_index=0,
        side="long",
        locked_exit_profile="aligned",
        initial_stop=None,
        initial_take=_leg(0.1, "take_profit", "tp_aligned"),
    )
    index = _projection_index(bar_count=3, entry_opportunities=[opportunity])
    market_frame = _market_frame(candles)

    def provider(position: object) -> ManagedReplayResult:
        return _disable_tp_replay(
            position.position_id,  # type: ignore[attr-defined]
            position.side,  # type: ignore[attr-defined]
            position.entry_fill.time_ms,  # type: ignore[attr-defined]
        )

    result = run_projection_execution_loop(
        "inst", index, market_frame, _POLICY, managed_replay_provider=provider
    )
    assert result.final_open_position is not None
    assert result.final_open_position.initial_protection.take_profit_price == Decimal("110")
    assert len(result.positions) == 1
    assert result.positions[0].status == "open"


def test_initial_take_profit_still_fires_without_disable() -> None:
    # Positive control for the disable_initial_tp corrective pass: same
    # OHLC, no managed_replay_provider -- TP must still fire.
    candles = _flat_candles(3)
    candles[1] = _candle(1, "105", "115", "104", "112")
    opportunity = ExecutableEntryOpportunityDTO(
        bar_index=0,
        side="long",
        locked_exit_profile="aligned",
        initial_stop=None,
        initial_take=_leg(0.1, "take_profit", "tp_aligned"),
    )
    index = _projection_index(bar_count=3, entry_opportunities=[opportunity])
    market_frame = _market_frame(candles)

    result = run_projection_execution_loop("inst", index, market_frame, _POLICY)
    (closed,) = result.positions
    assert closed.exit_fill is not None
    assert closed.exit_fill.candidate_type == "take_profit"
    assert closed.exit_fill.fill_price == Decimal("110")


# --- both legs null: position may still open, no fabricated protection -


def test_both_legs_null_position_opens_without_fabricated_protection() -> None:
    candles = _flat_candles(3)
    opportunity = ExecutableEntryOpportunityDTO(
        bar_index=0,
        side="long",
        locked_exit_profile="neutral",
        initial_stop=None,
        initial_take=None,
    )
    index = _projection_index(bar_count=3, entry_opportunities=[opportunity])
    result = run_projection_execution_loop(
        "inst", index, _market_frame(candles), _POLICY
    )
    assert result.final_open_position is not None
    protection = result.final_open_position.initial_protection
    assert protection.stop_loss_price is None
    assert protection.take_profit_price is None
    assert protection.stop_loss_attribution is None
    assert protection.take_profit_attribution is None


# --- short side: stop-only, correct direction math ----------------------


def test_short_side_stop_only_direction_and_attribution() -> None:
    candles = _flat_candles(5)
    candles[1] = _candle(1, "105", "115", "104", "112")
    opportunity = ExecutableEntryOpportunityDTO(
        bar_index=0,
        side="short",
        locked_exit_profile="countertrend",
        initial_stop=_leg(0.1, "stop_loss", "sl_countertrend"),
        initial_take=None,
    )
    index = _projection_index(bar_count=5, entry_opportunities=[opportunity])
    result = run_projection_execution_loop(
        "inst", index, _market_frame(candles), _POLICY
    )
    (closed,) = result.positions
    assert closed.position.side == "short"
    assert closed.position.locked_exit_profile == "countertrend"
    assert closed.position.initial_protection.stop_loss_price == Decimal("110")
    assert closed.exit_fill is not None
    assert closed.exit_fill.candidate_type == "stop_loss"
    assert closed.exit_fill.rule_id == "sl_countertrend"


# --- primary adversarial scenario: profile drift, 10+ bars, multi-cand -


def _adversarial_index() -> HistoricalExecutionProjectionIndex:
    """Long entry at bar 0 under `aligned`. Countertrend's own signal
    stream fires early (bar 3) -- a current-profile-based lookup would
    wrongly exit there once the market's current profile drifts to
    countertrend. Aligned's own stream (the locked profile) fires much
    later (bar 12, 12 bars after entry) with TWO simultaneous
    candidates in canonical declared order -- the first must win."""

    opportunity = ExecutableEntryOpportunityDTO(
        bar_index=0,
        side="long",
        locked_exit_profile="aligned",
        initial_stop=None,
        initial_take=None,
    )
    long_events = {
        "aligned": (
            SignalExitEventDTO(
                bar_index=12,
                candidates=(
                    SignalExitCandidateDTO(attribution=_attribution("signal", "sig_always")),
                    SignalExitCandidateDTO(attribution=_attribution("signal", "sig_aligned")),
                ),
            ),
        ),
        "countertrend": (
            SignalExitEventDTO(
                bar_index=3,
                candidates=(SignalExitCandidateDTO(attribution=_attribution("signal", "sig_countertrend")),),
            ),
        ),
        "neutral": (),
    }
    return _projection_index(
        bar_count=15, entry_opportunities=[opportunity], long_signal_events=long_events
    )


def test_locked_profile_survives_ten_plus_bar_drift_and_exits_on_its_own_stream() -> None:
    index = _adversarial_index()
    candles = _flat_candles(15)
    result = run_projection_execution_loop("inst", index, _market_frame(candles), _POLICY)
    (closed,) = result.positions
    assert closed.position.locked_exit_profile == "aligned"
    assert closed.exit_fill is not None
    # NOT bar 3 (countertrend's early-firing bar) -- proves the locked
    # profile was held, not the current/drifted one.
    assert closed.exit_fill.bar_index == 12
    assert closed.exit_fill.candidate_type == "signal"


def test_multi_candidate_signal_uses_first_declared_order_candidate() -> None:
    index = _adversarial_index()
    candles = _flat_candles(15)
    result = run_projection_execution_loop("inst", index, _market_frame(candles), _POLICY)
    (closed,) = result.positions
    assert closed.exit_fill is not None
    assert closed.exit_fill.rule_id == "sig_always"  # first candidate, not sig_aligned
    assert closed.exit_fill.exit_kind == "signal"
    assert closed.exit_fill.layer == "exit_policy"


def test_negative_control_current_profile_lookup_would_have_chosen_a_different_bar() -> None:
    """Proves the fixture is genuinely adversarial: a (deliberately
    wrong) current-profile-style lookup at the position's own side finds
    a DIFFERENT bar/rule than the actual locked-profile result -- if
    this assertion failed, the drift fixture would not be distinguishing
    the two lookup strategies and the earlier PASS tests would be
    meaningless."""

    index = _adversarial_index()
    wrong_current_profile = "countertrend"
    wrong_event = index.lookup_signal_event("long", wrong_current_profile, 3)
    assert wrong_event is not None
    wrong_bar, wrong_rule_id = 3, wrong_event.candidates[0].attribution.rule_id

    candles = _flat_candles(15)
    result = run_projection_execution_loop("inst", index, _market_frame(candles), _POLICY)
    (closed,) = result.positions
    assert closed.exit_fill is not None
    actual_bar, actual_rule_id = closed.exit_fill.bar_index, closed.exit_fill.rule_id

    assert (actual_bar, actual_rule_id) != (wrong_bar, wrong_rule_id)
    assert actual_bar == 12
    assert actual_rule_id == "sig_always"


# --- same-bar arbitration priority: unchanged ---------------------------


def test_same_bar_arbitration_priority_unchanged() -> None:
    assert _CANDIDATE_PRIORITY == {
        "stop_loss": 1,
        "managed_stop": 2,
        "take_profit": 3,
        "runtime_protective": 4,
        "runtime_take": 5,
        "runtime_close": 6,
        "runtime_exit": 6,
        "signal": 7,
    }


def test_stop_wins_over_signal_on_the_same_bar() -> None:
    # Both a stop hit and a locked-profile signal fire on bar 1 -- stop
    # (priority 1) must win over signal (priority 7), matching the
    # unchanged legacy arbitration order.
    candles = _flat_candles(5)
    candles[1] = _candle(1, "95", "96", "85", "94")
    opportunity = ExecutableEntryOpportunityDTO(
        bar_index=0,
        side="long",
        locked_exit_profile="aligned",
        initial_stop=_leg(0.1, "stop_loss", "sl_aligned"),
        initial_take=None,
    )
    long_events = {
        "aligned": (
            SignalExitEventDTO(
                bar_index=1,
                candidates=(SignalExitCandidateDTO(attribution=_attribution("signal", "sig_aligned")),),
            ),
        ),
        "countertrend": (),
        "neutral": (),
    }
    index = _projection_index(
        bar_count=5, entry_opportunities=[opportunity], long_signal_events=long_events
    )
    result = run_projection_execution_loop("inst", index, _market_frame(candles), _POLICY)
    (closed,) = result.positions
    assert closed.exit_fill is not None
    assert closed.exit_fill.candidate_type == "stop_loss"


# --- managed policy stays architecturally separate -----------------------


def test_managed_policy_module_does_not_read_projection_profile_streams() -> None:
    import inspect

    from research_service.execution import managed_policy

    source = inspect.getsource(managed_policy)
    assert "HistoricalExecutionProjection" not in source
    assert "locked_exit_profile" not in source
    assert "signal_exit_events" not in source
