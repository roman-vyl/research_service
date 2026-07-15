"""CLI: monkeypatch ema_pullback + BFF path and print pipeline timing tables.

Usage (repo root)::

    set EMA_PIPELINE_DEBUG=1
    python research/diagnostics/run_pipeline_debug.py

See research/diagnostics/README.md and debug/run-pipeline-debug.bat (log under debug/reports/).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("EMA_PIPELINE_DEBUG", "1")

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.diagnostics.pipeline_trace import dbg_mark, dbg_root, dbg_span


def _wrap(name: str, fn):
    def wrapped(*args, **kwargs):
        with dbg_span(name):
            return fn(*args, **kwargs)

    wrapped.__name__ = getattr(fn, "__name__", name)
    return wrapped


def _patch_all() -> None:
    import research.experiments.config_loader as cl
    import research.strategies.ema_pullback.context.evaluation as ev
    import research.strategies.ema_pullback.context.pipeline as ctx_pipe
    import research.strategies.ema_pullback.execution.backtest as bt
    import research.strategies.ema_pullback.execution.exits as ex
    import research.strategies.ema_pullback.execution.runner as runner_mod
    import research.strategies.ema_pullback.execution.signal_trace as st
    import research.strategies.ema_pullback.execution.signals as sig
    import research.strategies.ema_pullback.features.calculations as calc
    import research.strategies.ema_pullback.features.plan as fp
    import research.strategies.ema_pullback.spec_report as sr
    import research_api.services.backtest_service as bsvc
    import research_api.services.results_reader as rr
    import research_api.services.signal_trace_service as sts

    cl.load_strategy_config_file = _wrap(
        "config.load_strategy_config_file", cl.load_strategy_config_file
    )
    cl._read_config_file = _wrap("config.read_file", cl._read_config_file)
    orig_load = cl.load_strategy_config

    def load_cfg(payload, *, source_file="<memory>"):
        with dbg_span("config.load_strategy_config"):
            return orig_load(payload, source_file=source_file)

    cl.load_strategy_config = load_cfg

    orig_family = cl._load_family_instance

    def load_inst(family, item):
        dbg_mark("config.load_family_instance")
        return orig_family(family, item)

    cl._load_family_instance = load_inst

    runner_mod.load_candles_once = _wrap("runner.load_candles_once", runner_mod.load_candles_once)
    runner_mod.run_strategy_spec = _wrap("backtest.run_strategy_spec", runner_mod.run_strategy_spec)

    fp.build_feature_plan_from_strategy_spec = _wrap(
        "backtest.feature_plan", fp.build_feature_plan_from_strategy_spec
    )
    calc.add_feature_columns_from_plan = _wrap("backtest.add_features", calc.add_feature_columns_from_plan)
    ctx_pipe.build_context_bundle_for_spec = _wrap(
        "backtest.context_bundle", ctx_pipe.build_context_bundle_for_spec
    )
    sig.build_signals_from_spec = _wrap("backtest.signals", sig.build_signals_from_spec)
    ex.build_exit_outputs_from_spec = _wrap("backtest.exits", ex.build_exit_outputs_from_spec)
    bt.build_feature_plan_from_strategy_spec = _wrap(
        "backtest.feature_plan", bt.build_feature_plan_from_strategy_spec
    )
    bt.add_feature_columns_from_plan = _wrap("backtest.add_features", bt.add_feature_columns_from_plan)
    bt.build_context_bundle_for_spec = _wrap(
        "backtest.context_bundle", bt.build_context_bundle_for_spec
    )
    bt.build_signals_from_spec = _wrap("backtest.signals", bt.build_signals_from_spec)
    bt.build_exit_outputs_from_spec = _wrap("backtest.exits", bt.build_exit_outputs_from_spec)
    ev.evaluate_context_consumption = _wrap("context.evaluate", ev.evaluate_context_consumption)

    st.build_signal_trace_from_spec = _wrap(
        "signal_trace.build_full", st.build_signal_trace_from_spec
    )
    st.slice_signal_trace = _wrap("signal_trace.slice", st.slice_signal_trace)

    # Consumer namespace: signal_trace_service binds imports at load time.
    sts.build_signal_trace_from_spec = st.build_signal_trace_from_spec
    sts.slice_signal_trace = st.slice_signal_trace
    sts.build_feature_plan_from_strategy_spec = _wrap(
        "signal_trace.feature_plan", sts.build_feature_plan_from_strategy_spec
    )
    sts.add_feature_columns_from_plan = _wrap(
        "signal_trace.add_features", sts.add_feature_columns_from_plan
    )
    rr.load_run_report = _wrap("signal_trace.load_report", rr.load_run_report)
    sts.load_run_report = rr.load_run_report
    sr.strategy_spec_from_report_dict = _wrap(
        "signal_trace.parse_spec", sr.strategy_spec_from_report_dict
    )
    sts.strategy_spec_from_report_dict = sr.strategy_spec_from_report_dict

    orig_load_ohlcv = sts._load_ohlcv_frame

    def load_ohlcv(**kwargs):
        with dbg_span("signal_trace.load_candles"):
            return orig_load_ohlcv(**kwargs)

    sts._load_ohlcv_frame = load_ohlcv

    orig_to_contract = sts._to_contract

    def to_contract(data):
        with dbg_span("signal_trace.to_contract"):
            return orig_to_contract(data)

    sts._to_contract = to_contract

    orig_fetch = sts.fetch_signal_trace_bundle

    def fetch_trace(**kwargs):
        from research_api.services.market_params import parse_time_range_ms
        from research_api.services.market_reader import resolve_exclusive_to_ms
        from research_api.services.results_reader import load_run_report

        with dbg_root("bff.signal_trace"):
            report = load_run_report(run_id=kwargs["run_id"])
            exclusive_end_ms = resolve_exclusive_to_ms(
                to_ms=kwargs.get("to_ms"),
                to_open_time_ms=kwargs.get("to_open_time_ms"),
                timeframe=report.timeframe,
            )
            start_ms, end_ms = parse_time_range_ms(
                from_ms=kwargs["from_ms"], to_ms=exclusive_end_ms
            )
            cache_key = sts._cached_full_trace_key(
                kwargs["run_id"],
                kwargs["variant_key"],
                start_ms,
                end_ms,
            )
            if cache_key in sts._TRACE_CACHE:
                dbg_mark("signal_trace.cache_hit")
                with dbg_span("signal_trace.fetch_cached"):
                    return sts._TRACE_CACHE[cache_key]
            dbg_mark("signal_trace.cache_miss")
            with dbg_span("signal_trace.fetch_total"):
                return orig_fetch(**kwargs)

    sts.fetch_signal_trace_bundle = fetch_trace

    orig_validate = bsvc._validate_config_file

    def validate(path):
        with dbg_span("bff.backtest.preflight_validate"):
            return orig_validate(path)

    bsvc._validate_config_file = validate
    runner_mod.run_strategy_specs_from_config = _wrap(
        "bff.backtest.run", runner_mod.run_strategy_specs_from_config
    )


def _sample_config(path: Path) -> None:
    payload = {
        "schema_version": 1,
        "experiment_id": "pipeline_debug_run",
        "family": "ema_pullback",
        "execution": {"init_cash": 10000.0, "fees": 0.0006, "slippage": 0.0001},
        "instances": [
            {
                "instance_id": "baseline",
                "variant": "ema_pullback_fast100_anchor200_slow1000",
                "market": {"symbol": "BTCUSDT", "base_timeframe": "1h"},
                "strategy": {
                    "trade_sides": ["long"],
                    "anchor_stack": {
                        "source": "close",
                        "timeframe": "base",
                        "fast": 100,
                        "anchor": 200,
                        "slow": 1000,
                    },
                    "direction": {"component_id": "ema_anchor_stack_trend"},
                    "setups": [
                        {
                            "instance_id": "setup",
                            "component_id": "untouched_anchor_setup",
                            "lookback": 50,
                            "active_bars": 3,
                        }
                    ],
                    "trigger": {"component_id": "reclaim_anchor"},
                    "blockers": [{"instance_id": "no_blockers", "component_id": "no_blockers"}],
                    "risk": {"component_id": "no_risk_filter"},
                    "contexts": {},
                    "trade_management": {
                        "exit_policy": {
                            "always_on": {
                                "exits": [
                                    {
                                        "instance_id": "atr_stop_loss",
                                        "component_id": "atr_stop_loss",
                                        "distance": {
                                            "timeframe": "base",
                                            "period": 14,
                                            "multiplier": 1.5,
                                        },
                                    },
                                    {
                                        "instance_id": "atr_take_profit",
                                        "component_id": "atr_take_profit",
                                        "distance": {
                                            "timeframe": "base",
                                            "period": 14,
                                            "multiplier": 4.0,
                                        },
                                    },
                                ]
                            },
                            "profiles": {
                                "aligned": {"exits": []},
                                "countertrend": {"exits": []},
                                "neutral": {"exits": []},
                            },
                        }
                    },
                },
            }
        ],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    _patch_all()
    from research_api.services import backtest_service as bsvc

    with tempfile.TemporaryDirectory() as td:
        cfg = Path(td) / "debug.json"
        _sample_config(cfg)
        with dbg_root("bff.backtest"):
            pre = bsvc._validate_config_file(cfg)
            if pre is not None:
                print("preflight failed:", pre, file=sys.stderr)
                raise SystemExit(1)
            with dbg_span("bff.backtest.run"):
                run_id = bsvc.run_strategy_specs_from_config(cfg)

    print(f"run_id={run_id}", file=sys.stderr)

    try:
        from research_api.services.results_reader import load_run_report
        import research_api.services.signal_trace_service as sts
        from research_api.services.signal_trace_service import fetch_signal_trace_bundle

        report = load_run_report(run_id=run_id)
        variant = report.variants[0].variant
        from_ms = report.data_range.from_open_time_ms
        to_open_time_ms = report.data_range.to_open_time_ms
        sts._TRACE_CACHE.clear()
        fetch_signal_trace_bundle(
            run_id=run_id,
            variant_key=variant,
            from_ms=from_ms,
            to_open_time_ms=to_open_time_ms,
        )
        fetch_signal_trace_bundle(
            run_id=run_id,
            variant_key=variant,
            from_ms=from_ms,
            to_open_time_ms=to_open_time_ms,
        )
    except Exception as exc:
        print(f"signal_trace skipped: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
