"""On-demand sparse chart display bundle (projected from signal trace, cache-on-demand)."""

from __future__ import annotations

from pathlib import Path

from research_api.contracts.chart_events import (
    CHART_EVENTS_BUNDLE_SCHEMA_VERSION,
    MAX_CHART_EVENTS_BARS,
    ChartEventsBundle,
    ChartEventsCoverage,
    ChartEventsHtfContext,
    cached_chart_events_key,
)
from research_api.contracts.signal_trace import SignalTraceBundle
from research_api.services.market_params import parse_time_range_ms
from research_api.services.market_reader import resolve_exclusive_to_ms
from research_api.services.results_reader import load_run_report
from research_api.services.signal_trace_service import fetch_signal_trace_bundle

_CHART_EVENTS_CACHE: dict[str, ChartEventsBundle] = {}
_MAX_CHART_EVENTS_CACHE_ENTRIES = 32


def _project_display_bundle(
    trace: SignalTraceBundle,
    *,
    requested_from_sec: int,
    requested_to_sec: int,
) -> ChartEventsBundle:
    """Map dense signal trace to sparse chart-events display payload."""

    times = trace.times
    if times:
        from_sec = times[0]
        to_sec = times[-1]
    else:
        from_sec = requested_from_sec
        to_sec = requested_to_sec

    bar_count = len(times)
    truncated = bar_count > 0 and (
        from_sec > requested_from_sec or to_sec < requested_to_sec
    )

    htf = trace.htf_context
    return ChartEventsBundle(
        times=list(times),
        component_events=list(trace.component_events),
        htf_context=ChartEventsHtfContext(
            fast=list(htf.fast),
            anchor=list(htf.anchor),
            slow=list(htf.slow),
            meta=dict(htf.meta),
        ),
        meta=trace.meta,
        coverage=ChartEventsCoverage(
            schema_version=CHART_EVENTS_BUNDLE_SCHEMA_VERSION,
            from_sec=from_sec,
            to_sec=to_sec,
            bar_count=bar_count,
            requested_from_sec=requested_from_sec,
            requested_to_sec=requested_to_sec,
            truncated=truncated,
            max_bars=MAX_CHART_EVENTS_BARS,
        ),
    )


def _requested_window_sec(
    *,
    from_ms: int,
    to_ms: int | None,
    to_open_time_ms: int | None,
    end_ms: int,
) -> tuple[int, int]:
    requested_from_sec = from_ms // 1000
    if to_open_time_ms is not None:
        requested_to_sec = to_open_time_ms // 1000
    elif to_ms is not None:
        requested_to_sec = max(requested_from_sec, (to_ms - 1) // 1000)
    else:
        requested_to_sec = end_ms // 1000
    return requested_from_sec, requested_to_sec


def _store_chart_events_cache(key: str, bundle: ChartEventsBundle) -> None:
    _CHART_EVENTS_CACHE[key] = bundle
    if len(_CHART_EVENTS_CACHE) > _MAX_CHART_EVENTS_CACHE_ENTRIES:
        _CHART_EVENTS_CACHE.pop(next(iter(_CHART_EVENTS_CACHE)))


def fetch_chart_events_bundle(
    *,
    run_id: str,
    variant_key: str,
    from_ms: int,
    to_ms: int | None = None,
    to_open_time_ms: int | None = None,
    context_overlay_ref: str | None = None,
    db_path: Path | None = None,
) -> ChartEventsBundle:
    """Return sparse chart display bundle for ``[from_ms, exclusive_end)``."""

    report = load_run_report(run_id=run_id)
    exclusive_end_ms = resolve_exclusive_to_ms(
        to_ms=to_ms,
        to_open_time_ms=to_open_time_ms,
        timeframe=report.timeframe,
    )
    start_ms, end_ms = parse_time_range_ms(from_ms=from_ms, to_ms=exclusive_end_ms)
    requested_from_sec, requested_to_sec = _requested_window_sec(
        from_ms=from_ms,
        to_ms=to_ms,
        to_open_time_ms=to_open_time_ms,
        end_ms=end_ms,
    )

    cache_key = cached_chart_events_key(
        run_id=run_id,
        variant_key=variant_key,
        from_ms=start_ms,
        exclusive_end_ms=end_ms,
        context_overlay_ref=context_overlay_ref,
    )
    cached = _CHART_EVENTS_CACHE.get(cache_key)
    if cached is not None:
        return cached

    trace = fetch_signal_trace_bundle(
        run_id=run_id,
        variant_key=variant_key,
        from_ms=from_ms,
        to_ms=to_ms,
        to_open_time_ms=to_open_time_ms,
        context_overlay_ref=context_overlay_ref,
        db_path=db_path,
    )
    bundle = _project_display_bundle(
        trace,
        requested_from_sec=requested_from_sec,
        requested_to_sec=requested_to_sec,
    )
    _store_chart_events_cache(cache_key, bundle)
    return bundle
