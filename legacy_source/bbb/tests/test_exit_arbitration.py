"""Slice 4: ExitArbitrator bar-open-active conflict matrix."""

from __future__ import annotations

from research.strategies.ema_pullback.execution.exit_arbitration import ExitArbitrator
from research.strategies.ema_pullback.execution.trade_runtime import ExitCandidate


def _candidate(
    *,
    layer: str,
    candidate_type: str,
    rule_id: str = "r1",
    price: float = 100.0,
    bar: int = 5,
) -> ExitCandidate:
    return ExitCandidate(
        layer=layer,  # type: ignore[arg-type]
        rule_id=rule_id,
        component_id="comp",
        price=price,
        bar=bar,
        reason=f"{candidate_type}:{rule_id}",
        candidate_type=candidate_type,
    )


def test_initial_sl_wins_over_managed_stop_bar_open_active() -> None:
    arbitrator = ExitArbitrator()
    result = arbitrator.select_winner(
        [
            _candidate(layer="exit_management", candidate_type="managed_stop", price=99.0),
            _candidate(layer="exit_policy", candidate_type="stop_loss", price=98.0),
        ],
        bar_index=5,
    )
    assert result.winner is not None
    assert result.winner.layer == "exit_policy"
    assert result.winner.candidate_type == "stop_loss"
    assert len(result.losing_candidates) == 1


def test_managed_stop_wins_over_take_profit_bar_open_active() -> None:
    arbitrator = ExitArbitrator()
    result = arbitrator.select_winner(
        [
            _candidate(layer="exit_policy", candidate_type="take_profit", price=110.0),
            _candidate(layer="exit_management", candidate_type="managed_stop", price=101.0),
        ],
        bar_index=5,
    )
    assert result.winner is not None
    assert result.winner.layer == "exit_management"
    assert result.winner.candidate_type == "managed_stop"


def test_runtime_exit_loses_to_stop_and_tp_but_beats_signal() -> None:
    arbitrator = ExitArbitrator()
    vs_tp = arbitrator.select_winner(
        [
            _candidate(layer="exit_management", candidate_type="runtime_exit", price=105.0),
            _candidate(layer="exit_policy", candidate_type="take_profit", price=110.0),
        ],
        bar_index=5,
    )
    assert vs_tp.winner is not None
    assert vs_tp.winner.candidate_type == "take_profit"

    vs_signal = arbitrator.select_winner(
        [
            _candidate(layer="exit_management", candidate_type="runtime_exit", price=105.0),
            _candidate(layer="exit_policy", candidate_type="signal", price=105.0),
        ],
        bar_index=5,
    )
    assert vs_signal.winner is not None
    assert vs_signal.winner.candidate_type == "runtime_exit"


def test_losing_candidates_metadata_shape() -> None:
    arbitrator = ExitArbitrator()
    result = arbitrator.select_winner(
        [
            _candidate(layer="exit_policy", candidate_type="stop_loss"),
            _candidate(layer="exit_policy", candidate_type="signal", rule_id="sig"),
        ],
        bar_index=5,
    )
    assert result.winner is not None
    assert len(result.losing_candidates) == 1
    assert result.losing_candidates[0].candidate_type == "signal"


def test_ignores_candidates_on_other_bars() -> None:
    arbitrator = ExitArbitrator()
    result = arbitrator.select_winner(
        [_candidate(layer="exit_policy", candidate_type="stop_loss", bar=4)],
        bar_index=5,
    )
    assert result.winner is None
