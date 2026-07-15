"""On-demand entry signal trace for a run variant (research pipeline, read-only)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from data_engine.contracts import TimeWindow, timeframe_ms, validate_timeframe
from data_engine.store.db import Db

from research.ema_smoke_helpers import candles_to_ohlcv_dataframe
from research.strategies.ema_pullback.execution.signal_trace import (
    SignalTraceBundleData,
    SideSignalTrace,
    build_signal_trace_from_spec,
    slice_signal_trace,
)
from research.strategies.ema_pullback.features.calculations import add_feature_columns_from_plan
from research.strategies.ema_pullback.features.plan import build_feature_plan_from_strategy_spec
from research.strategies.ema_pullback.spec_report import (
    StrategySpecReportParseError,
    strategy_spec_from_report_dict,
)
from research.strategies.ema_pullback.spec import (
    EmaBounceCounterSetupSpec,
    UntouchedAnchorSetupSpec,
)

from research_api.contracts.runs import RunReport, RunVariant
from research_api.contracts.signal_trace import (
    ComponentEvent,
    ContextConsumptionTraceRecord,
    HtfContextTrace,
    SignalTraceBundle,
    SignalTraceMeta,
    SideSignalTrace as SideSignalTraceContract,
)
from research_api.services.market_params import MarketParamError, normalize_symbol, parse_time_range_ms
from research_api.services.market_reader import (
    MarketDataNotFoundError,
    _open_db,
    resolve_exclusive_to_ms,
)
from research_api.services.results_reader import ResultsNotFoundError, load_run_report

MAX_SIGNAL_TRACE_BARS = 50_000


class UnsupportedSignalTraceFamilyError(ValueError):
    """Only ema_pullback runs are supported for signal trace in MVP."""


class SignalTraceVariantNotFoundError(ValueError):
    """Variant key not present in run report."""


def _variant_from_report(report: RunReport, variant_key: str) -> RunVariant:
    for variant in report.variants:
        if variant.variant == variant_key:
            return variant
    raise SignalTraceVariantNotFoundError(f"variant not found: {variant_key!r}")


def _warmup_bars_ms(spec: Any, timeframe: str) -> int:
    base_tf = validate_timeframe(timeframe)
    base_ms = timeframe_ms(base_tf)
    lookback = 1
    for rule in spec.setups:
        if isinstance(rule.params, EmaBounceCounterSetupSpec):
            lookback = max(lookback, int(rule.params.touch_lookback_bars))
        elif isinstance(rule.params, UntouchedAnchorSetupSpec):
            lookback = max(lookback, int(rule.params.lookback))
    slow_period = int(spec.anchor_stack.slow.period)
    anchor_warmup_ms = (max(lookback, slow_period) + 5) * base_ms

    warmup_ms = anchor_warmup_ms
    for _context_ref, provider in spec.contexts:
        context_tf = (
            base_tf
            if str(provider.timeframe).strip() == "base"
            else validate_timeframe(provider.timeframe)
        )
        context_ms = timeframe_ms(context_tf)
        context_warmup_ms = (int(provider.slow_period) + 5) * context_ms
        warmup_ms = max(warmup_ms, context_warmup_ms)
    return warmup_ms


def _load_ohlcv_frame(
    *,
    symbol: str,
    timeframe: str,
    from_ms: int,
    to_ms: int,
    db_path: Path | None,
):
    sym = normalize_symbol(symbol)
    tf = validate_timeframe(timeframe.strip())
    db = _open_db(db_path)
    window = TimeWindow(from_ms, to_ms)
    candles = db.range_get(sym, tf, window)
    if len(candles) < 2:
        raise MarketParamError("not enough candles for signal trace in requested range")
    return candles_to_ohlcv_dataframe(candles)


def _to_contract(data: SignalTraceBundleData) -> SignalTraceBundle:
    def side(s: SideSignalTrace) -> SideSignalTraceContract:
        return SideSignalTraceContract(
            direction_ok=s.direction_ok,
            blockers_ok=s.blockers_ok,
            setup_ok=s.setup_ok,
            trigger_ok=s.trigger_ok,
            risk_ok=s.risk_ok,
            signal_entry=s.signal_entry,
            stop_ready=s.stop_ready,
            portfolio_entry=s.portfolio_entry,
            internals=s.internals,
        )

    return SignalTraceBundle(
        times=data.times,
        meta=SignalTraceMeta(**data.meta),
        htf_context=HtfContextTrace(**data.htf_context),
        context_consumption_trace=[
            ContextConsumptionTraceRecord(**record) for record in data.context_consumption_trace
        ],
        component_events=[
            ComponentEvent(
                time=event.time,
                event_type=event.event_type,
                role=event.role,
                side=event.side,
                component_id=event.component_id,
                instance_id=event.instance_id,
                label=event.label,
                tooltip=event.tooltip,
                span_id=event.span_id,
                feature_family=event.feature_family,
                source_timeframe=event.source_timeframe,
                base_timeframe=event.base_timeframe,
                metadata=event.metadata,
            )
            for event in data.component_events
        ],
        long=side(data.long),
        short=side(data.short),
    )


def _cached_full_trace_key(
    run_id: str,
    variant_key: str,
    from_ms: int,
    to_ms: int,
    context_overlay_ref: str | None = None,
) -> str:
    ref_token = context_overlay_ref or ""
    return f"{run_id}:{variant_key}:{from_ms}:{to_ms}:{ref_token}"


# Simple module-level cache for full-window traces before slice
_TRACE_CACHE: dict[str, SignalTraceBundle] = {}


def fetch_signal_trace_bundle(
    *,
    run_id: str,
    variant_key: str,
    from_ms: int,
    to_ms: int | None = None,
    to_open_time_ms: int | None = None,
    context_overlay_ref: str | None = None,
    db_path: Path | None = None,
) -> SignalTraceBundle:
    """Compute entry pipeline trace for chart view window ``[from_ms, exclusive_end)``."""

    report = load_run_report(run_id=run_id)
    # TODO(perf): load_run_report re-reads strategy config; dedupe with backtest preflight path.
    if report.family != "ema_pullback":
        raise UnsupportedSignalTraceFamilyError(
            f"signal trace supports family ema_pullback only, got {report.family!r}"
        )

    variant = _variant_from_report(report, variant_key)
    try:
        spec = strategy_spec_from_report_dict(variant.strategy_spec)
    except StrategySpecReportParseError as exc:
        raise ValueError(str(exc)) from exc

    exclusive_end_ms = resolve_exclusive_to_ms(
        to_ms=to_ms,
        to_open_time_ms=to_open_time_ms,
        timeframe=report.timeframe,
    )
    start_ms, end_ms = parse_time_range_ms(from_ms=from_ms, to_ms=exclusive_end_ms)
    from_sec = start_ms // 1000
    to_sec = end_ms // 1000

    cache_key = _cached_full_trace_key(
        run_id, variant_key, start_ms, end_ms, context_overlay_ref
    )
    if cache_key in _TRACE_CACHE:
        return _TRACE_CACHE[cache_key]

    warmup_ms = _warmup_bars_ms(spec, report.timeframe)
    load_from = max(0, start_ms - warmup_ms)
    try:
        ohlcv = _load_ohlcv_frame(
            symbol=report.symbol,
            timeframe=report.timeframe,
            from_ms=load_from,
            to_ms=end_ms,
            db_path=db_path,
        )
    except MarketDataNotFoundError as exc:
        raise exc

    plan = build_feature_plan_from_strategy_spec(spec)
    enriched = add_feature_columns_from_plan(ohlcv, plan)
    if context_overlay_ref is not None and context_overlay_ref not in spec.contexts_by_ref():
        raise ValueError(
            f"context_overlay_ref {context_overlay_ref!r} is not defined in strategy.contexts"
        )
    full_trace = build_signal_trace_from_spec(
        enriched,
        spec,
        plan,
        context_overlay_ref=context_overlay_ref,
    )
    sliced = slice_signal_trace(
        full_trace,
        from_time_sec=from_sec,
        to_time_sec=to_sec,
        max_bars=MAX_SIGNAL_TRACE_BARS,
    )
    bundle = _to_contract(sliced)
    _TRACE_CACHE[cache_key] = bundle
    if len(_TRACE_CACHE) > 32:
        _TRACE_CACHE.pop(next(iter(_TRACE_CACHE)))
    return bundle
