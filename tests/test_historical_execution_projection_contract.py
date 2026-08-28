"""I3 -- Research: HistoricalExecutionProjection consumer foundation
(`compact-strategy-evaluation-boundary-v1`, Master Plan).

Covers: valid decode (both sides, all profiles, attributed legs,
nullable legs, multiple simultaneous signal candidates), alignment
validation (pass + four fail-closed mismatches), invalid bar_index
rejection, attribution-kind validation, independent leg nullability,
and the indexed lookup foundation (entry lookup, signal lookup, empty
lookup, candidate order preservation, locked-profile roundtrip).

Not covered here (out of I3 scope, per the master plan): execution
loop wiring, `PositionState`, fills, accounting -- those are I4/I5/I7.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from research_service.adapters.http.strategy_engine_client import (
    parse_historical_execution_projection,
)
from research_service.domain.contracts import (
    HistoricalExecutionProjectionIndex,
    MarketRange,
    validate_projection_alignment,
)
from research_service.domain.errors import UpstreamServiceError

_CONTRACT_VERSION = "strategy_evaluation_execution.v2"

# The real Strategy Engine wire envelope
# (`strategy_serialization.py::serialize_strategy_evaluation_execution`,
# same family as `.v1`): `bar_count`/`market_data_hash` nested INSIDE
# `market{...}`, key name `base_timeframe` (not `timeframe` -- that is
# Research's own `MarketRange` field name, mapped during parse).
_MARKET_WIRE = {
    "ticker": "BTCUSDT.P",
    "base_timeframe": "5m",
    "from_ms": 0,
    "to_ms": 900_000,  # 3 bars
    "bar_count": 3,
    "market_data_hash": "market-hash",
}

# `MarketRange(**_MARKET_RANGE_KWARGS)` -- Research's own domain type,
# used for alignment-check expectations, distinct from the wire shape.
_MARKET_RANGE_KWARGS = {"ticker": "BTCUSDT.P", "timeframe": "5m", "from_ms": 0, "to_ms": 900_000}


def _attribution(kind: str, *, rule_id: str = "r1", component_id: str = "c1") -> dict[str, object]:
    return {"rule_id": rule_id, "component_id": component_id, "exit_kind": kind}


def _leg(ratio: float, kind: str, **attribution_kwargs: str) -> dict[str, object]:
    return {"ratio": ratio, "attribution": _attribution(kind, **attribution_kwargs)}


def _event(bar_index: int, candidates: list[dict[str, object]]) -> dict[str, object]:
    return {"bar_index": bar_index, "candidates": candidates}


def _signal_candidate(*, rule_id: str = "s1", component_id: str = "sc1") -> dict[str, object]:
    return {"attribution": _attribution("signal", rule_id=rule_id, component_id=component_id)}


def _empty_profiles() -> dict[str, list[object]]:
    return {"aligned": [], "countertrend": [], "neutral": []}


def _full_valid_body() -> dict[str, object]:
    return {
        "contract_version": _CONTRACT_VERSION,
        "strategy_id": "ema_pullback",
        "config_hash": "cfg-hash",
        "market": dict(_MARKET_WIRE),
        "entry_opportunities": [
            {
                "bar_index": 0,
                "side": "long",
                "locked_exit_profile": "aligned",
                "initial_stop": _leg(10.0, "stop_loss", rule_id="sl_aligned"),
                "initial_take": _leg(20.0, "take_profit", rule_id="tp_aligned"),
            },
            {
                "bar_index": 1,
                "side": "short",
                "locked_exit_profile": "countertrend",
                "initial_stop": _leg(100.0, "stop_loss", rule_id="sl_always"),
                "initial_take": None,
            },
            {
                "bar_index": 2,
                "side": "long",
                "locked_exit_profile": "neutral",
                "initial_stop": None,
                "initial_take": None,
            },
        ],
        "signal_exit_events": {
            "long": {
                "aligned": [
                    _event(0, [_signal_candidate(rule_id="sig_always"), _signal_candidate(rule_id="sig_aligned")]),
                ],
                "countertrend": [],
                "neutral": [],
            },
            "short": {
                "aligned": [],
                "countertrend": [_event(1, [_signal_candidate(rule_id="sig_countertrend")])],
                "neutral": [],
            },
        },
        "warnings": (),
    }


# --- valid decode ------------------------------------------------------


def test_full_valid_projection_decodes() -> None:
    projection = parse_historical_execution_projection(_full_valid_body())
    assert projection.strategy_id == "ema_pullback"
    assert len(projection.entry_opportunities) == 3
    both_sides = {o.side for o in projection.entry_opportunities}
    assert both_sides == {"long", "short"}
    all_profiles = {o.locked_exit_profile for o in projection.entry_opportunities}
    assert all_profiles == {"aligned", "countertrend", "neutral"}


def test_multiple_simultaneous_signal_candidates_are_preserved_in_order() -> None:
    projection = parse_historical_execution_projection(_full_valid_body())
    events = projection.signal_exit_events.long["aligned"]
    assert len(events) == 1
    assert [c.attribution.rule_id for c in events[0].candidates] == ["sig_always", "sig_aligned"]


def test_independent_leg_nullability_stop_only_take_only_neither_both() -> None:
    projection = parse_historical_execution_projection(_full_valid_body())
    both = next(o for o in projection.entry_opportunities if o.bar_index == 0)
    stop_only = next(o for o in projection.entry_opportunities if o.bar_index == 1)
    neither = next(o for o in projection.entry_opportunities if o.bar_index == 2)
    assert both.initial_stop is not None and both.initial_take is not None
    assert stop_only.initial_stop is not None and stop_only.initial_take is None
    assert neither.initial_stop is None and neither.initial_take is None


# --- attribution-kind validation ----------------------------------------


def test_stop_leg_with_signal_kind_fails_closed() -> None:
    body = _full_valid_body()
    body["entry_opportunities"][0]["initial_stop"] = _leg(10.0, "signal")
    with pytest.raises((ValidationError, UpstreamServiceError)):
        parse_historical_execution_projection(body)


def test_take_leg_with_wrong_kind_fails_closed() -> None:
    body = _full_valid_body()
    body["entry_opportunities"][0]["initial_take"] = _leg(20.0, "stop_loss")
    with pytest.raises((ValidationError, UpstreamServiceError)):
        parse_historical_execution_projection(body)


def test_signal_candidate_with_non_signal_kind_fails_closed() -> None:
    body = _full_valid_body()
    body["signal_exit_events"]["long"]["aligned"] = [
        _event(0, [{"attribution": _attribution("stop_loss")}])
    ]
    with pytest.raises((ValidationError, UpstreamServiceError)):
        parse_historical_execution_projection(body)


def test_leg_missing_rule_id_fails_closed() -> None:
    body = _full_valid_body()
    leg = _leg(10.0, "stop_loss")
    leg["attribution"]["rule_id"] = ""  # type: ignore[index]
    body["entry_opportunities"][0]["initial_stop"] = leg
    with pytest.raises((ValidationError, UpstreamServiceError)):
        parse_historical_execution_projection(body)


def test_non_finite_ratio_fails_closed() -> None:
    body = _full_valid_body()
    body["entry_opportunities"][0]["initial_stop"] = _leg(float("nan"), "stop_loss")
    with pytest.raises((ValidationError, UpstreamServiceError)):
        parse_historical_execution_projection(body)


def test_unsupported_locked_exit_profile_fails_closed() -> None:
    body = _full_valid_body()
    body["entry_opportunities"][0]["locked_exit_profile"] = "bullish"
    with pytest.raises((ValidationError, UpstreamServiceError)):
        parse_historical_execution_projection(body)


def test_unsupported_side_fails_closed() -> None:
    body = _full_valid_body()
    body["entry_opportunities"][0]["side"] = "sideways"
    with pytest.raises((ValidationError, UpstreamServiceError)):
        parse_historical_execution_projection(body)


def test_signal_event_with_zero_candidates_fails_closed() -> None:
    body = _full_valid_body()
    body["signal_exit_events"]["long"]["aligned"] = [_event(0, [])]
    with pytest.raises((ValidationError, UpstreamServiceError)):
        parse_historical_execution_projection(body)


def test_malformed_profile_map_missing_key_fails_closed() -> None:
    body = _full_valid_body()
    del body["signal_exit_events"]["long"]["neutral"]  # type: ignore[union-attr]
    with pytest.raises((ValidationError, UpstreamServiceError)):
        parse_historical_execution_projection(body)


def test_malformed_profile_map_unknown_key_fails_closed() -> None:
    body = _full_valid_body()
    body["signal_exit_events"]["long"]["bullish"] = []  # type: ignore[index]
    with pytest.raises((ValidationError, UpstreamServiceError)):
        parse_historical_execution_projection(body)


# --- invalid bar_index ---------------------------------------------------


def test_entry_opportunity_bar_index_outside_range_fails_closed() -> None:
    body = _full_valid_body()
    body["entry_opportunities"][0]["bar_index"] = 3  # bar_count is 3, valid range [0, 3)
    with pytest.raises((ValidationError, UpstreamServiceError)):
        parse_historical_execution_projection(body)


def test_signal_event_bar_index_outside_range_fails_closed() -> None:
    body = _full_valid_body()
    body["signal_exit_events"]["long"]["aligned"] = [_event(99, [_signal_candidate()])]
    with pytest.raises((ValidationError, UpstreamServiceError)):
        parse_historical_execution_projection(body)


def test_duplicate_entry_opportunity_same_bar_and_side_fails_closed() -> None:
    body = _full_valid_body()
    duplicate = dict(body["entry_opportunities"][0])  # type: ignore[index]
    body["entry_opportunities"].append(duplicate)  # type: ignore[union-attr]
    with pytest.raises((ValidationError, UpstreamServiceError)):
        parse_historical_execution_projection(body)


def test_simultaneous_long_and_short_entry_on_same_bar_fails_closed() -> None:
    body = _full_valid_body()
    body["entry_opportunities"].append(  # type: ignore[union-attr]
        {
            "bar_index": 0,
            "side": "short",
            "locked_exit_profile": "countertrend",
            "initial_stop": _leg(100.0, "stop_loss", rule_id="sl_always"),
            "initial_take": None,
        }
    )
    with pytest.raises((ValidationError, UpstreamServiceError)):
        parse_historical_execution_projection(body)


def test_wrong_contract_version_fails_closed() -> None:
    body = _full_valid_body()
    body["contract_version"] = "strategy_evaluation_execution.v1"
    with pytest.raises(UpstreamServiceError):
        parse_historical_execution_projection(body)


def test_missing_contract_version_fails_closed() -> None:
    body = _full_valid_body()
    del body["contract_version"]
    with pytest.raises(UpstreamServiceError):
        parse_historical_execution_projection(body)


def test_real_wire_envelope_shape_decodes_bar_count_and_hash_from_nested_market() -> None:
    # bar_count/market_data_hash must come from market{...}, not top-level
    # -- this is the real strategy_serialization.py envelope shape.
    body = _full_valid_body()
    assert "bar_count" not in body
    assert "market_data_hash" not in body
    assert body["market"]["bar_count"] == 3  # type: ignore[index]
    assert body["market"]["market_data_hash"] == "market-hash"  # type: ignore[index]
    projection = parse_historical_execution_projection(body)
    assert projection.bar_count == 3
    assert projection.market_data_hash == "market-hash"
    assert projection.market.timeframe == "5m"  # translated from base_timeframe


def test_duplicate_signal_event_bar_index_within_one_profile_fails_closed() -> None:
    body = _full_valid_body()
    body["signal_exit_events"]["short"]["countertrend"] = [
        _event(1, [_signal_candidate()]),
        _event(1, [_signal_candidate(rule_id="s2")]),
    ]
    with pytest.raises((ValidationError, UpstreamServiceError)):
        parse_historical_execution_projection(body)


# --- alignment validation --------------------------------------------------


def test_alignment_passes_on_exact_identity_hash_range_bar_count() -> None:
    projection = parse_historical_execution_projection(_full_valid_body())
    validate_projection_alignment(
        projection,
        expected_market=MarketRange(**_MARKET_RANGE_KWARGS),
        expected_market_data_hash="market-hash",
        expected_bar_count=3,
    )  # must not raise


def test_alignment_fails_on_ticker_mismatch() -> None:
    projection = parse_historical_execution_projection(_full_valid_body())
    mismatched = dict(_MARKET_RANGE_KWARGS, ticker="ETHUSDT.P")
    with pytest.raises(UpstreamServiceError):
        validate_projection_alignment(
            projection,
            expected_market=MarketRange(**mismatched),
            expected_market_data_hash="market-hash",
            expected_bar_count=3,
        )


def test_alignment_fails_on_range_mismatch() -> None:
    projection = parse_historical_execution_projection(_full_valid_body())
    mismatched = dict(_MARKET_RANGE_KWARGS, from_ms=300_000, to_ms=1_200_000)
    with pytest.raises(UpstreamServiceError):
        validate_projection_alignment(
            projection,
            expected_market=MarketRange(**mismatched),
            expected_market_data_hash="market-hash",
            expected_bar_count=3,
        )


def test_alignment_fails_on_market_data_hash_mismatch() -> None:
    projection = parse_historical_execution_projection(_full_valid_body())
    with pytest.raises(UpstreamServiceError):
        validate_projection_alignment(
            projection,
            expected_market=MarketRange(**_MARKET_RANGE_KWARGS),
            expected_market_data_hash="different-hash",
            expected_bar_count=3,
        )


def test_alignment_fails_on_bar_count_mismatch() -> None:
    projection = parse_historical_execution_projection(_full_valid_body())
    with pytest.raises(UpstreamServiceError):
        validate_projection_alignment(
            projection,
            expected_market=MarketRange(**_MARKET_RANGE_KWARGS),
            expected_market_data_hash="market-hash",
            expected_bar_count=4,
        )


# --- indexed lookup foundation ----------------------------------------------


def test_index_entry_lookup_returns_correct_opportunity() -> None:
    projection = parse_historical_execution_projection(_full_valid_body())
    index = HistoricalExecutionProjectionIndex.build(projection)
    found = index.lookup_entry(0, "long")
    assert found is not None
    assert found.locked_exit_profile == "aligned"


def test_index_entry_lookup_returns_none_for_empty_bar() -> None:
    projection = parse_historical_execution_projection(_full_valid_body())
    index = HistoricalExecutionProjectionIndex.build(projection)
    assert index.lookup_entry(0, "short") is None
    assert index.lookup_entry(2, "short") is None


def test_index_signal_lookup_returns_correct_event_and_preserves_candidate_order() -> None:
    projection = parse_historical_execution_projection(_full_valid_body())
    index = HistoricalExecutionProjectionIndex.build(projection)
    event = index.lookup_signal_event("long", "aligned", 0)
    assert event is not None
    assert [c.attribution.rule_id for c in event.candidates] == ["sig_always", "sig_aligned"]


def test_index_signal_lookup_returns_none_for_empty_side_profile_bar() -> None:
    projection = parse_historical_execution_projection(_full_valid_body())
    index = HistoricalExecutionProjectionIndex.build(projection)
    assert index.lookup_signal_event("long", "countertrend", 0) is None
    assert index.lookup_signal_event("short", "aligned", 1) is None


def test_index_lookup_is_o1_not_a_linear_scan() -> None:
    # Build a projection with many events and confirm the index performs a
    # dict lookup (identity check on the underlying mapping), not a scan --
    # a scan would still pass functionally, so this asserts the mechanism
    # directly rather than timing it.
    body = _full_valid_body()
    body["market"] = dict(_MARKET_WIRE, bar_count=100, to_ms=30_000_000)
    body["signal_exit_events"]["long"]["neutral"] = [
        _event(i, [_signal_candidate(rule_id=f"s{i}")]) for i in range(50)
    ]
    projection = parse_historical_execution_projection(body)
    index = HistoricalExecutionProjectionIndex.build(projection)
    assert isinstance(index._signal_event_by_side_profile_bar, dict)  # noqa: SLF001
    event = index.lookup_signal_event("long", "neutral", 37)
    assert event is not None
    assert event.candidates[0].attribution.rule_id == "s37"


def test_locked_exit_profile_survives_decode_and_index_roundtrip_exactly() -> None:
    body = _full_valid_body()
    projection = parse_historical_execution_projection(body)
    index = HistoricalExecutionProjectionIndex.build(projection)
    for expected_profile, bar_index, side in (
        ("aligned", 0, "long"),
        ("countertrend", 1, "short"),
        ("neutral", 2, "long"),
    ):
        opportunity = index.lookup_entry(bar_index, side)
        assert opportunity is not None
        assert opportunity.locked_exit_profile == expected_profile
