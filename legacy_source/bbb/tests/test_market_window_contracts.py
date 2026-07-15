"""Market window bundle contracts (Phase 2 — no service/router)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from research_api.contracts.chart import (
    CHART_OVERLAY_EMA_KIND,
    CandlesWindowBundle,
    CandlesWindowCoverage,
    ChartBar,
    EmaWindowBundle,
    EmaWindowCoverage,
    IndicatorPoint,
)

pytestmark = pytest.mark.workbench_api


def _sample_bar(time_sec: int = 1_700_000_000) -> ChartBar:
    return ChartBar(time=time_sec, open=1.0, high=2.0, low=0.5, close=1.5, volume=10.0)


def _candles_coverage(**overrides: object) -> CandlesWindowCoverage:
    base = {
        "requested_from_ms": 1_000,
        "requested_to_ms": 2_000,
        "actual_from_ms": 1_000,
        "actual_to_ms": 2_000,
        "truncated": False,
    }
    base.update(overrides)
    return CandlesWindowCoverage(**base)  # type: ignore[arg-type]


def _ema_coverage(**overrides: object) -> EmaWindowCoverage:
    base = {
        "requested_from_ms": 1_000,
        "requested_to_ms": 2_000,
        "actual_from_ms": 1_000,
        "actual_to_ms": 2_000,
        "calculation_origin_ms": 500,
        "coverage_to_ms": 2_000,
        "cache_hit": False,
        "truncated": False,
    }
    base.update(overrides)
    return EmaWindowCoverage(**base)  # type: ignore[arg-type]


def test_candles_window_bundle_serializes_candles_only() -> None:
    bundle = CandlesWindowBundle(
        candles=[_sample_bar()],
        coverage=_candles_coverage(),
    )
    payload = bundle.model_dump(mode="json")
    assert "candles" in payload
    assert "coverage" in payload
    assert "ema_overlays" not in payload
    assert "points" not in payload
    assert payload["coverage"]["truncated"] is False


def test_candles_window_bundle_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        CandlesWindowBundle(
            candles=[],
            coverage=_candles_coverage(),
            ema_overlays=[],  # type: ignore[call-arg]
        )


def test_ema_window_bundle_serializes_points_only() -> None:
    bundle = EmaWindowBundle(
        points=[
            IndicatorPoint(time=1_700_000_000, value=100.0, kind=CHART_OVERLAY_EMA_KIND),
        ],
        coverage=_ema_coverage(cache_hit=True),
    )
    payload = bundle.model_dump(mode="json")
    assert "points" in payload
    assert "coverage" in payload
    assert "candles" not in payload
    assert payload["coverage"]["calculation_origin_ms"] == 500
    assert payload["coverage"]["coverage_to_ms"] == 2_000
    assert payload["coverage"]["cache_hit"] is True
    assert payload["points"][0]["kind"] == CHART_OVERLAY_EMA_KIND


def test_ema_window_bundle_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        EmaWindowBundle(
            points=[],
            coverage=_ema_coverage(),
            candles=[],  # type: ignore[call-arg]
        )


def test_ema_window_coverage_requires_canonical_fields() -> None:
    with pytest.raises(ValidationError):
        EmaWindowCoverage(
            requested_from_ms=1,
            requested_to_ms=2,
            actual_from_ms=1,
            actual_to_ms=2,
            truncated=False,
            # missing calculation_origin_ms, coverage_to_ms, cache_hit
        )


def test_ema_window_coverage_cache_hit_required() -> None:
    cov = _ema_coverage(cache_hit=False)
    assert cov.cache_hit is False
    payload = cov.model_dump(mode="json")
    assert "cache_hit" in payload
    assert "calculation_origin_ms" in payload
    assert "coverage_to_ms" in payload


def test_candles_and_ema_window_bundles_are_independent_shapes() -> None:
    candles = CandlesWindowBundle(candles=[], coverage=_candles_coverage())
    ema = EmaWindowBundle(points=[], coverage=_ema_coverage())
    candles_keys = set(candles.model_dump().keys())
    ema_keys = set(ema.model_dump().keys())
    assert candles_keys == {"candles", "coverage"}
    assert ema_keys == {"points", "coverage"}
    assert candles_keys.isdisjoint({"points"})
