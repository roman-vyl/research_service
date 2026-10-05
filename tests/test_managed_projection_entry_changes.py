"""`research-entry-anchored-change-v1`.

- Decode (task 1.1): `path.entry_changes` and `term.entry_change`
  decode; a closed `op` enum, a finite `value` and a known `series_id`
  are required; a projection without the new fields decodes as before.
- Execution (task 2.1): an entry change holds on bar `i` iff
  `series[i] - series[e] <op> value` with both points non-null, `e`
  being the position's entry bar; inside `at_least` it counts as one
  term.
- Parity (task 2.2): the incremental advance equals the eager timeline
  bar for bar on a projection with entry changes.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from research_service.domain.contracts import HistoricalManagedProjectionDTO
from research_service.execution.managed_policy import (
    ManagedRuleSet,
    advance_managed_trade_state,
    build_managed_policy_timeline_from_projection,
    initialize_managed_trade_state,
)
from test_managed_policy_from_projection import _position
from test_managed_projection_paths_and_events import (
    _frame,
    _path,
    _phase_events,
    _phase_paths_rule,
    _projection,
    _run,
    _term,
)

_N = 16


def _change(op: str = ">=", value: float = 5.0, series_id: str = "adx") -> dict[str, Any]:
    return {"series_id": series_id, "op": op, "value": value}


def _flat_frame(n: int = _N):
    return _frame([100.0] * n)


def _first_fire(
    projection: HistoricalManagedProjectionDTO,
    *,
    entry_index: int,
    side: str = "long",
    n: int = _N,
) -> list[tuple[int, str | None]]:
    _states, events = _run(projection, _position(entry_index=entry_index, side=side), _flat_frame(n))
    return _phase_events(events)


def _require_projection(series: list[float | None], op: str = ">=", value: float = 5.0):
    return _projection(
        [_phase_paths_rule([_path("rise", entry_changes=[_change(op, value)])])],
        distances={"adx": series},
    )


# -- 1.1: decode ------------------------------------------------------------


def test_path_and_term_entry_changes_decode() -> None:
    projection = _projection(
        [
            _phase_paths_rule(
                [
                    _path(
                        "rise",
                        entry_changes=[_change()],
                        at_least={"k": 1, "terms": [{"entry_change": _change("<", -2.5)}]},
                    )
                ]
            )
        ],
        distances={"adx": [None] * _N},
    )

    rule = projection.rules[0]
    assert rule.kind == "phase_transition"
    assert rule.paths is not None
    path = rule.paths[0]
    assert [(item.series_id, item.op, item.value) for item in path.entry_changes] == [("adx", ">=", 5.0)]
    assert path.at_least is not None
    term = path.at_least.terms[0]
    assert term.entry_change is not None
    assert (term.entry_change.op, term.entry_change.value) == ("<", -2.5)
    assert term.condition_id is None and term.distance_id is None and term.trade_metric is None


def test_projection_without_entry_changes_decodes_unchanged() -> None:
    payload = {
        "conditions": {"adx": {"long": [True] * _N, "short": [False] * _N}},
        "distances": {"one": [1.0] * _N},
        "rules": [
            _phase_paths_rule(
                [
                    {
                        "path_id": "fast",
                        "condition_id": "adx",
                        "thresholds": [{"distance_id": "one", "trade_metric": "mfe_distance"}],
                        "at_least": {"k": 1, "terms": [_term(condition_id="adx")]},
                    }
                ]
            )
        ],
    }

    projection = HistoricalManagedProjectionDTO.model_validate(payload)

    rule = projection.rules[0]
    assert rule.kind == "phase_transition"
    assert rule.paths is not None
    path = rule.paths[0]
    assert path.entry_changes == ()
    assert path.at_least is not None
    assert path.at_least.terms[0].entry_change is None


@pytest.mark.parametrize("op", ["==", "!=", "ge", ""])
def test_unknown_op_rejected(op: str) -> None:
    with pytest.raises(ValidationError):
        _require_projection([1.0] * _N, op=op)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_value_rejected(value: float) -> None:
    with pytest.raises(ValidationError):
        _require_projection([1.0] * _N, value=value)


def test_unknown_entry_change_field_rejected() -> None:
    with pytest.raises(ValidationError):
        _projection(
            [_phase_paths_rule([_path("rise", entry_changes=[{**_change(), "anchor": 0}])])],
            distances={"adx": [1.0] * _N},
        )


def test_empty_series_id_rejected() -> None:
    with pytest.raises(ValidationError):
        _projection(
            [_phase_paths_rule([_path("rise", entry_changes=[_change(series_id="")])])],
            distances={"adx": [1.0] * _N},
        )


def test_dangling_path_series_id_rejected() -> None:
    with pytest.raises(ValidationError, match="distances=\\['missing'\\]"):
        _projection(
            [_phase_paths_rule([_path("rise", entry_changes=[_change(series_id="missing")])])],
            distances={"adx": [1.0] * _N},
        )


def test_dangling_term_series_id_rejected() -> None:
    with pytest.raises(ValidationError, match="distances=\\['missing'\\]"):
        _projection(
            [
                _phase_paths_rule(
                    [
                        _path(
                            "rise",
                            at_least={"k": 1, "terms": [{"entry_change": _change(series_id="missing")}]},
                        )
                    ]
                )
            ],
            distances={"adx": [1.0] * _N},
        )


@pytest.mark.parametrize(
    "term",
    [
        {"condition_id": "c", "entry_change": _change()},
        {"distance_id": "adx", "trade_metric": "mfe_pct", "entry_change": _change()},
        {"distance_id": "adx", "entry_change": _change()},
        {},
    ],
)
def test_term_must_set_exactly_one_variant(term: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        _projection(
            [_phase_paths_rule([_path("rise", at_least={"k": 1, "terms": [term]})])],
            conditions={"c": {"long": [True] * _N, "short": [True] * _N}},
            distances={"adx": [1.0] * _N},
        )


# -- 2.1: execution ---------------------------------------------------------


def _rise_series() -> list[float | None]:
    series: list[float | None] = [30.0] * _N
    series[10:14] = [21.0, 22.0, 25.9, 26.0]
    return series


@pytest.mark.parametrize("side", ["long", "short"])
def test_rise_from_entry_value(side: str) -> None:
    # Bars before the entry (30.0) are above the anchor but never seen.
    assert _first_fire(_require_projection(_rise_series()), entry_index=10, side=side) == [(13, "rise")]


@pytest.mark.parametrize(
    ("op", "value", "expected_bar"),
    [
        (">=", 5.0, 13),  # 26 - 21 = 5
        (">", 4.9, 13),  # 4.9 > 4.9 is False on bar 12, 5 > 4.9 on bar 13
        (">", 5.0, 14),  # 30 - 21 = 9
        ("<=", -1.0, 12),
        ("<", -1.0, 13),
    ],
)
def test_each_operator(op: str, value: float, expected_bar: int) -> None:
    series: list[float | None] = [20.0] * _N
    series[10:15] = [21.0, 23.0, 25.9, 26.0, 30.0]
    if op in {"<=", "<"}:
        series[10:15] = [21.0, 21.0, 20.0, 19.5, 30.0]
    assert _first_fire(_require_projection(series, op, value), entry_index=10) == [(expected_bar, "rise")]


def test_entry_bar_itself() -> None:
    series: list[float | None] = [21.0] * _N
    assert _first_fire(_require_projection(series, ">=", 0.0), entry_index=10) == [(10, "rise")]
    assert _first_fire(_require_projection(series, ">", 0.0), entry_index=10) == []


def test_null_anchor_never_holds() -> None:
    series = _rise_series()
    series[10] = None
    series[11:] = [100.0] * (_N - 11)
    assert _first_fire(_require_projection(series, ">=", -1_000.0), entry_index=10) == []


def test_null_current_value_is_false_on_that_bar() -> None:
    series = _rise_series()
    series[13] = None
    assert _first_fire(_require_projection(series), entry_index=10) == [(14, "rise")]


def test_anchor_follows_the_position_entry_bar() -> None:
    series: list[float | None] = [float(i) for i in range(_N)]
    projection = _require_projection(series, ">=", 3.0)
    assert _first_fire(projection, entry_index=2) == [(5, "rise")]
    assert _first_fire(projection, entry_index=9) == [(12, "rise")]


def test_entry_change_and_threshold_and_market_are_anded() -> None:
    projection = _projection(
        [
            _phase_paths_rule(
                [
                    _path(
                        "rise",
                        condition_id="di",
                        thresholds=[{"distance_id": "bars", "trade_metric": "bars_since_entry"}],
                        entry_changes=[_change()],
                    )
                ]
            )
        ],
        conditions={"di": {"long": [i >= 13 for i in range(_N)], "short": [False] * _N}},
        distances={"adx": [float(i) for i in range(_N)], "bars": [5.0] * _N},
    )
    # entry 8: rise holds from 13, DI from 13, bars_since_entry >= 5 from 12
    assert _first_fire(projection, entry_index=8) == [(13, "rise")]
    # the short side's DI never holds
    assert _first_fire(projection, entry_index=8, side="short") == []


@pytest.mark.parametrize("side", ["long", "short"])
def test_entry_change_inside_n_of_m(side: str) -> None:
    projection = _projection(
        [
            _phase_paths_rule(
                [
                    _path(
                        "rise",
                        at_least={
                            "k": 2,
                            "terms": [
                                {"entry_change": _change()},
                                _term(distance_id="never", metric="mfe_pct"),
                                _term(condition_id="di"),
                            ],
                        },
                    )
                ]
            )
        ],
        conditions={"di": {"long": [i >= 12 for i in range(_N)], "short": [i >= 12 for i in range(_N)]}},
        distances={"adx": _rise_series(), "never": [1.0] * _N},
    )
    # entry change from 13, DI from 12, mfe_pct never: exactly two hold on 13
    assert _first_fire(projection, entry_index=10, side=side) == [(13, "rise")]


def test_first_true_path_still_wins_with_entry_changes() -> None:
    projection = _projection(
        [
            _phase_paths_rule(
                [
                    _path("rise", entry_changes=[_change()]),
                    _path("di", condition_id="di"),
                ]
            )
        ],
        conditions={"di": {"long": [i >= 13 for i in range(_N)], "short": [False] * _N}},
        distances={"adx": _rise_series()},
    )
    assert _first_fire(projection, entry_index=10) == [(13, "rise")]


# -- 2.2: incremental == eager -----------------------------------------------


@pytest.mark.parametrize("side", ["long", "short"])
@pytest.mark.parametrize("entry_index", [0, 3, 10])
def test_incremental_matches_eager_with_entry_changes(side: str, entry_index: int) -> None:
    adx: list[float | None] = [20.0, 21.0, None, 22.0, 24.0, 27.0, 26.0, 21.0, 21.5, 23.0, 21.0, 22.0, 25.0, 26.5, 27.0, 31.0]
    projection = _projection(
        [
            _phase_paths_rule(
                [
                    _path("rise", condition_id="di", entry_changes=[_change(">=", 5.0)]),
                    _path(
                        "mixed",
                        at_least={
                            "k": 2,
                            "terms": [
                                {"entry_change": _change(">", 3.0)},
                                _term(distance_id="bars", metric="bars_since_entry"),
                                _term(condition_id="di"),
                            ],
                        },
                    ),
                ]
            ),
            {
                "kind": "phase_transition",
                "rule_id": "to_runner",
                "target_phase": "runner",
                "condition_id": None,
                "distance_id": None,
                "trade_metric": None,
                "paths": [_path("fall", entry_changes=[_change("<=", -4.0)])],
            },
            {"kind": "stop_action", "rule_id": "be", "activation_phase": "proven", "distance_id": "zero"},
        ],
        conditions={"di": {"long": [i % 3 != 0 for i in range(_N)], "short": [i % 2 == 0 for i in range(_N)]}},
        distances={"adx": adx, "bars": [4.0] * _N, "zero": [0.0] * _N},
    )
    frame = _frame([100.0 + 0.25 * i for i in range(_N)])
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
    assert any(item.phase != "initial_risk" for item in incremental)
