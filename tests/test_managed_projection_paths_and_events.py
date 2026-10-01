"""`historical-managed-projection-cutover-v1` groups 2-3.

- Generic `paths` resolution through the shared `_phase_rule_met`
  (design D2): first true path wins, mixed market+trade, market-only and
  trade-only N-of-M, null threshold is false; incremental and eager
  consumers agree on a paths corpus.
- Stop attribution mirrors Strategy Engine's managed replay (design D3):
  a non-tightening winner never re-labels the active stop.
- Gating (design D4): no managed provider means no managed execution,
  even when the projection carries `managed`.
- Local managed events (design D5): observations of the consumer's own
  state transitions, persisted through the unchanged artifact path.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from research_service.application.backtests import (
    RunSingleInstanceBacktest,
    SingleInstanceBacktestRequest,
)
from research_service.domain.contracts import (
    Candle,
    ExplicitRange,
    HistoricalExecutionProjectionIndex,
    HistoricalManagedProjectionDTO,
    MarketFrame,
    MarketRange,
)
from research_service.domain.execution import PositionState
from research_service.execution.managed_policy import (
    ManagedRuleSet,
    advance_managed_trade_state,
    build_managed_policy_timeline_from_projection,
    initialize_managed_trade_state,
)
from research_service.execution.managed_policy_events import ManagedPolicyEvent
from research_service.execution.projection_loop import _open_managed_state
from test_managed_policy_from_projection import _position
from test_single_instance_backtest import (
    FakeMarketData,
    FakeStrategyEngine,
    market_frame,
    strategy_identity,
    strategy_projection,
)

_N = 8


def _frame(highs: list[float], closes: list[float] | None = None) -> MarketFrame:
    closes = closes or [100.0] * len(highs)
    candles = tuple(
        Candle(
            open_time_ms=i * 300_000,
            open=Decimal("100"),
            high=Decimal(str(high)),
            low=Decimal("100"),
            close=Decimal(str(close)),
            volume=Decimal("1"),
        )
        for i, (high, close) in enumerate(zip(highs, closes, strict=True))
    )
    return MarketFrame(
        market=MarketRange(ticker="BTCUSDT.P", timeframe="5m", from_ms=0, to_ms=len(highs) * 300_000),
        candles=candles,
    )


def _flag(true_at: set[int], n: int = _N) -> dict[str, list[bool]]:
    values = [i in true_at for i in range(n)]
    return {"long": values, "short": values}


def _phase_paths_rule(paths: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "kind": "phase_transition",
        "rule_id": "to_proven",
        "target_phase": "proven",
        "condition_id": None,
        "distance_id": None,
        "trade_metric": None,
        "paths": paths,
    }


def _path(path_id: str, **fields: Any) -> dict[str, Any]:
    return {"path_id": path_id, "condition_id": None, "thresholds": [], "at_least": None, **fields}


def _term(condition_id: str | None = None, distance_id: str | None = None, metric: str | None = None):
    return {"condition_id": condition_id, "distance_id": distance_id, "trade_metric": metric}


def _projection(
    rules: list[dict[str, Any]],
    conditions: dict[str, dict[str, list[bool]]] | None = None,
    distances: dict[str, list[float | None]] | None = None,
) -> HistoricalManagedProjectionDTO:
    return HistoricalManagedProjectionDTO.model_validate(
        {"conditions": conditions or {}, "distances": distances or {}, "rules": rules}
    )


def _run(
    projection: HistoricalManagedProjectionDTO,
    position: PositionState,
    frame: MarketFrame,
) -> tuple[list[Any], list[ManagedPolicyEvent]]:
    """Advance one position from its entry bar through the last bar,
    collecting per-bar states and events."""

    rule_set = ManagedRuleSet.from_projection(projection)
    state = initialize_managed_trade_state(position)
    states: list[Any] = []
    events: list[ManagedPolicyEvent] = []
    for bar_index in range(position.entry_fill.bar_index, len(frame.candles)):
        candle = frame.candles[bar_index]
        next_time_ms = (
            frame.candles[bar_index + 1].open_time_ms if bar_index + 1 < len(frame.candles) else None
        )
        state, effective = advance_managed_trade_state(
            state,
            projection,
            rule_set,
            trade_id=position.position_id,
            bar_index=bar_index,
            source_time_ms=candle.open_time_ms,
            high=float(candle.high),
            low=float(candle.low),
            next_time_ms=next_time_ms,
            close=float(candle.close),
            event_sink=events,
        )
        states.append((bar_index, state.phase, state.active_stop_price, state.active_stop_rule_id))
    return states, events


def _phase_events(events: list[ManagedPolicyEvent]) -> list[tuple[int, str | None]]:
    return [
        (event.bar_index, event.metadata.get("path_id"))
        for event in events
        if event.event_type == "phase_changed"
    ]


# -- D2: generic paths resolution ------------------------------------------


def test_first_true_path_wins() -> None:
    projection = _projection(
        [_phase_paths_rule([_path("fast", condition_id="a"), _path("htf", condition_id="b")])],
        conditions={"a": _flag({3}), "b": _flag({2, 3})},
    )
    _states, events = _run(projection, _position(entry_index=0), _frame([100.0] * _N))

    # b alone at bar 2 -> htf; on bar 3 both would be true, but the phase
    # already reached proven.
    assert _phase_events(events) == [(2, "htf")]

    projection_both = _projection(
        [_phase_paths_rule([_path("fast", condition_id="a"), _path("htf", condition_id="b")])],
        conditions={"a": _flag({3}), "b": _flag({3})},
    )
    _states, events = _run(projection_both, _position(entry_index=0), _frame([100.0] * _N))
    assert _phase_events(events) == [(3, "fast")]


def test_mixed_market_and_trade_waits_for_the_trade_threshold() -> None:
    # Market condition true from bar 1; MFE distance reaches 3.0 at bar 5.
    projection = _projection(
        [
            _phase_paths_rule(
                [
                    _path(
                        "mixed",
                        condition_id="adx",
                        thresholds=[{"distance_id": "three", "trade_metric": "mfe_distance"}],
                    )
                ]
            )
        ],
        conditions={"adx": _flag(set(range(1, _N)))},
        distances={"three": [3.0] * _N},
    )
    highs = [100.0, 101.0, 101.0, 102.0, 102.0, 103.0, 103.0, 103.0]
    _states, events = _run(projection, _position(entry_index=0), _frame(highs))

    assert _phase_events(events) == [(5, "mixed")]


def test_null_threshold_is_false() -> None:
    projection = _projection(
        [
            _phase_paths_rule(
                [_path("p", thresholds=[{"distance_id": "d", "trade_metric": "bars_since_entry"}])]
            )
        ],
        distances={"d": [None, None, None, 1.0, 1.0, 1.0, 1.0, 1.0]},
    )
    _states, events = _run(projection, _position(entry_index=0), _frame([100.0] * _N))

    assert _phase_events(events) == [(3, "p")]


def test_market_only_at_least() -> None:
    projection = _projection(
        [
            _phase_paths_rule(
                [
                    _path(
                        "vote",
                        at_least={"k": 2, "terms": [_term("a"), _term("b"), _term("c")]},
                    )
                ]
            )
        ],
        conditions={"a": _flag({1, 4}), "b": _flag({2, 4}), "c": _flag({3})},
    )
    _states, events = _run(projection, _position(entry_index=0), _frame([100.0] * _N))

    assert _phase_events(events) == [(4, "vote")]


def test_trade_only_at_least() -> None:
    # bars_since_entry >= 3 from bar 2; mfe_pct >= 0.02 from bar 4;
    # mfe_distance >= 5 never. k = 2 -> true from bar 4.
    projection = _projection(
        [
            _phase_paths_rule(
                [
                    _path(
                        "trade",
                        at_least={
                            "k": 2,
                            "terms": [
                                _term(distance_id="bars", metric="bars_since_entry"),
                                _term(distance_id="pct", metric="mfe_pct"),
                                _term(distance_id="far", metric="mfe_distance"),
                            ],
                        },
                    )
                ]
            )
        ],
        distances={"bars": [3.0] * _N, "pct": [0.02] * _N, "far": [5.0] * _N},
    )
    highs = [100.0, 100.0, 100.0, 101.0, 102.0, 102.0, 102.0, 102.0]
    _states, events = _run(projection, _position(entry_index=0), _frame(highs))

    assert _phase_events(events) == [(4, "trade")]


def test_mixed_at_least_counts_market_and_trade_terms() -> None:
    projection = _projection(
        [
            _phase_paths_rule(
                [
                    _path(
                        "mixed_vote",
                        at_least={
                            "k": 2,
                            "terms": [_term("adx"), _term(distance_id="bars", metric="bars_since_entry")],
                        },
                    )
                ]
            )
        ],
        conditions={"adx": _flag({1, 5})},
        distances={"bars": [4.0] * _N},
    )
    _states, events = _run(projection, _position(entry_index=0), _frame([100.0] * _N))

    # bars_since_entry >= 4 from bar 3; adx true at 1 and 5 -> both at 5.
    assert _phase_events(events) == [(5, "mixed_vote")]


@pytest.mark.parametrize(("side", "entry_index"), [("long", 0), ("long", 2), ("short", 1)])
def test_incremental_matches_eager_on_a_paths_corpus(side: str, entry_index: int) -> None:
    projection = _projection(
        [
            _phase_paths_rule(
                [
                    _path(
                        "fast",
                        condition_id="adx",
                        thresholds=[{"distance_id": "one", "trade_metric": "mfe_distance"}],
                    ),
                    _path("slow", at_least={"k": 1, "terms": [_term(distance_id="bars", metric="bars_since_entry")]}),
                ]
            ),
            {"kind": "stop_action", "rule_id": "be", "activation_phase": "proven", "distance_id": "zero"},
            {
                "kind": "take_action",
                "rule_id": "tp_off",
                "activation_phase": "proven",
                "resulting_profile": "disable_initial_tp",
            },
        ],
        conditions={"adx": _flag({3, 4, 5})},
        distances={"one": [1.0] * _N, "bars": [6.0] * _N, "zero": [0.0] * _N},
    )
    frame = _frame([100.0, 100.5, 101.0, 101.5, 102.0, 102.0, 102.0, 102.0])
    position = _position(entry_index=entry_index, side=side)

    eager = build_managed_policy_timeline_from_projection(projection, position, frame)
    rule_set = ManagedRuleSet.from_projection(projection)
    state = initialize_managed_trade_state(position)
    incremental = []
    for bar_index in range(entry_index, len(frame.candles)):
        candle = frame.candles[bar_index]
        next_time_ms = (
            frame.candles[bar_index + 1].open_time_ms if bar_index + 1 < len(frame.candles) else None
        )
        state, effective = advance_managed_trade_state(
            state,
            projection,
            rule_set,
            trade_id=position.position_id,
            bar_index=bar_index,
            source_time_ms=candle.open_time_ms,
            high=float(candle.high),
            low=float(candle.low),
            next_time_ms=next_time_ms,
        )
        if effective is not None:
            incremental.append(effective)

    assert incremental == list(eager.states)
    assert any(item.phase == "proven" for item in incremental)


# -- D3: stop attribution ---------------------------------------------------


def _two_stop_projection(a: list[float], b: list[float]) -> HistoricalManagedProjectionDTO:
    return _projection(
        [
            {"kind": "stop_action", "rule_id": "stop_a", "activation_phase": "initial_risk", "distance_id": "a"},
            {"kind": "stop_action", "rule_id": "stop_b", "activation_phase": "initial_risk", "distance_id": "b"},
        ],
        distances={"a": a, "b": b},
    )


def test_non_tightening_winner_does_not_relabel_the_active_stop() -> None:
    # bar 0: a wins at 101 -> active 101 (stop_a).
    # bar 1: a drops to 100.5, b = 101 wins but does not tighten -> stays stop_a.
    # bar 2: b = 102 tightens -> stop_b.
    projection = _two_stop_projection(
        a=[1.0, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
        b=[0.0, 1.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0],
    )
    frame = _frame([100.0] * _N)
    position = _position(entry_index=0)
    states, events = _run(projection, position, frame)

    assert [(bar, price, rule) for bar, _phase, price, rule in states[:3]] == [
        (0, 101.0, "stop_a"),
        (1, 101.0, "stop_a"),
        (2, 102.0, "stop_b"),
    ]
    stop_events = [
        (event.bar_index, event.rule_id, event.price)
        for event in events
        if event.event_type == "active_stop_updated"
    ]
    assert stop_events == [(0, "stop_a", Decimal("101.0")), (2, "stop_b", Decimal("102.0"))]

    eager = build_managed_policy_timeline_from_projection(projection, position, frame)
    assert [state.active_stop_rule_id for state in eager.states[:3]] == ["stop_a", "stop_a", "stop_b"]


def test_sub_epsilon_move_keeps_price_and_rule() -> None:
    projection = _two_stop_projection(
        a=[1.0] * _N,
        b=[0.0, 1.0 + 5e-9, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    )
    states, events = _run(projection, _position(entry_index=0), _frame([100.0] * _N))

    assert states[1][2:] == (101.0, "stop_a")
    assert sum(event.event_type == "active_stop_updated" for event in events) == 1


# -- D5: event observations -------------------------------------------------


def test_event_sequence_for_phase_stop_take_and_runtime() -> None:
    projection = _projection(
        [
            _phase_paths_rule([_path("htf", condition_id="adx")]),
            {"kind": "stop_action", "rule_id": "be", "activation_phase": "proven", "distance_id": "zero"},
            {
                "kind": "take_action",
                "rule_id": "tp_off",
                "activation_phase": "proven",
                "resulting_profile": "disable_initial_tp",
            },
            {
                "kind": "runtime_exit",
                "rule_id": "rsi_exit",
                "activation_phase": "proven",
                "condition_id": "rsi",
                "confirm_bars": 1,
                "exit_class": "runtime_close",
            },
        ],
        conditions={"adx": _flag({2}), "rsi": _flag({3})},
        distances={"zero": [0.0] * _N},
    )
    highs = [100.0, 101.0, 102.0, 102.0, 102.0, 102.0, 102.0, 102.0]
    closes = [100.0, 100.5, 101.5, 101.25, 101.0, 101.0, 101.0, 101.0]
    _states, events = _run(projection, _position(entry_index=0), _frame(highs, closes))

    observed = [
        (event.bar_index, event.event_type, event.rule_id, event.from_phase, event.to_phase, event.price, event.metadata)
        for event in events
    ]
    assert observed == [
        (2, "phase_changed", "to_proven", "initial_risk", "proven", Decimal("102.0"), {"path_id": "htf"}),
        (2, "active_stop_updated", "be", None, None, Decimal("100.0"), {"effective_from_bar": 3}),
        (
            2,
            "active_take_updated",
            "tp_off",
            None,
            None,
            None,
            {"take_profile": "disable_initial_tp", "effective_from_bar": 3},
        ),
        (
            3,
            "runtime_exit_triggered",
            "rsi_exit",
            None,
            None,
            Decimal("101.25"),
            {"exit_kind": "market_close", "effective_from_bar": 4},
        ),
    ]
    assert all(event.component_id is None for event in events)
    assert all(event.position_id == "trade-1" and event.side == "long" for event in events)
    assert [event.time_ms for event in events] == [600_000, 600_000, 600_000, 900_000]


def test_no_event_sink_builds_no_events_and_same_state() -> None:
    projection = _projection(
        [_phase_paths_rule([_path("p", condition_id="a")])],
        conditions={"a": _flag({1})},
    )
    position = _position(entry_index=0)
    frame = _frame([100.0] * _N)
    rule_set = ManagedRuleSet.from_projection(projection)
    with_sink = initialize_managed_trade_state(position)
    without_sink = initialize_managed_trade_state(position)
    sink: list[ManagedPolicyEvent] = []
    for bar_index in range(_N):
        candle = frame.candles[bar_index]
        kwargs = {
            "trade_id": "trade-1",
            "bar_index": bar_index,
            "source_time_ms": candle.open_time_ms,
            "high": 100.0,
            "low": 100.0,
            "next_time_ms": None,
        }
        with_sink, _ = advance_managed_trade_state(
            with_sink, projection, rule_set, close=100.0, event_sink=sink, **kwargs
        )
        without_sink, _ = advance_managed_trade_state(without_sink, projection, rule_set, **kwargs)
        assert with_sink == without_sink
    assert len(sink) == 1


def test_event_sink_requires_close() -> None:
    projection = _projection([])
    position = _position(entry_index=0)
    with pytest.raises(ValueError, match="close"):
        advance_managed_trade_state(
            initialize_managed_trade_state(position),
            projection,
            ManagedRuleSet.from_projection(projection),
            trade_id="trade-1",
            bar_index=0,
            source_time_ms=0,
            high=100.0,
            low=100.0,
            next_time_ms=None,
            event_sink=[],
        )


# -- D4 gating and end-to-end event persistence ------------------------------


def _always_proven_projection() -> HistoricalManagedProjectionDTO:
    return _projection(
        [
            {
                "kind": "phase_transition",
                "rule_id": "to_proven",
                "target_phase": "proven",
                "condition_id": "always",
                "distance_id": None,
                "trade_metric": None,
            }
        ],
        conditions={"always": _flag({0, 1, 2}, n=3)},
    )


def test_open_managed_state_without_provider_ignores_a_present_projection() -> None:
    projection = strategy_projection().model_copy(update={"managed": _always_proven_projection()})
    index = HistoricalExecutionProjectionIndex.build(projection)

    timeline, trade_state = _open_managed_state(
        _position(entry_index=0),
        projection_index=index,
        managed_replay_provider=None,
        allow_legacy_managed_replay_fallback=False,
    )

    assert (timeline, trade_state) == (None, None)


def _run_backtest(managed_policy_enabled: bool, managed: HistoricalManagedProjectionDTO | None):
    projection = strategy_projection()
    if managed is not None:
        projection = projection.model_copy(update={"managed": managed})
    strategy = FakeStrategyEngine(projection)
    outcome = RunSingleInstanceBacktest(strategy, FakeMarketData(market_frame())).execute(
        SingleInstanceBacktestRequest(
            strategy=strategy_identity(),
            range=ExplicitRange(from_ms=0, to_ms=900_000),
            managed_policy_enabled=managed_policy_enabled,
        )
    )
    return strategy, outcome


def test_managed_disabled_with_a_managed_projection_matches_a_non_managed_run() -> None:
    strategy, disabled = _run_backtest(False, _always_proven_projection())
    _strategy, plain = _run_backtest(False, None)

    assert strategy.managed_requests == []
    assert disabled.managed_policy_events == ()
    assert disabled.execution.positions == plain.execution.positions
    assert disabled.accounting.trades == plain.accounting.trades


def test_projection_path_persists_a_non_empty_event_trace() -> None:
    strategy, outcome = _run_backtest(True, _always_proven_projection())

    assert strategy.managed_requests == []
    assert [event.event_type for event in outcome.managed_policy_events] == ["phase_changed"]
    event = outcome.managed_policy_events[0]
    assert event.position_id == outcome.execution.positions[0].position.position_id
    assert (event.rule_id, event.from_phase, event.to_phase) == (
        "to_proven",
        "initial_risk",
        "proven",
    )
