"""Batch Experiment Management System — candidate summary extraction from strategy reports."""

from __future__ import annotations

from typing import Any, Mapping

from research.experiments.models import ExperimentCandidateResult

_QUALITY_FLAG_FIELDS: tuple[tuple[str, str], ...] = (
    ("high_mfe_high_capture", "high_mfe_high_capture_count"),
    ("high_mfe_low_capture", "high_mfe_low_capture_count"),
    ("signal_exit_winner", "signal_exit_winners"),
    ("signal_exit_giveback_failure", "signal_exit_giveback_failures"),
    ("stop_loss_after_low_mfe", "stop_loss_after_low_mfe"),
    ("stop_loss_after_bad_context", "stop_loss_after_bad_context"),
)

_PROFILE_SIDE_SUMMARY_PATHS: tuple[tuple[str, str, str], ...] = (
    ("long", "total", "long"),
    ("short", "total", "short"),
    ("total", "aligned", "aligned"),
    ("total", "countertrend", "countertrend"),
    ("total", "neutral", "neutral"),
    ("long", "aligned", "long_aligned"),
    ("long", "countertrend", "long_countertrend"),
    ("long", "neutral", "long_neutral"),
    ("short", "aligned", "short_aligned"),
    ("short", "countertrend", "short_countertrend"),
    ("short", "neutral", "short_neutral"),
)

_PROFILE_SIDE_SUMMARY_METRICS: tuple[tuple[str, str], ...] = (
    ("trades", "trades"),
    ("pnl", "pnl"),
    ("gross_pnl", "gross_pnl"),
    ("fees_paid", "fees_paid"),
    ("profit_factor", "profit_factor"),
    ("win_rate", "win_rate"),
)


def extract_candidate_summary(report_payload: Mapping[str, Any]) -> dict[str, Any]:
    """Extract summary metrics from a schema v5-like report (single-instance → variants[0])."""

    variants = report_payload.get("variants")
    if not isinstance(variants, list) or not variants:
        raise ValueError("report payload has no variants")

    variant = variants[0]
    if not isinstance(variant, dict):
        raise ValueError("report variant must be an object")

    metrics = variant.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("report variant has no metrics")

    total = metrics.get("total")
    if not isinstance(total, dict):
        raise ValueError("report variant metrics has no total block")

    out: dict[str, Any] = {
        "run_id": _optional_str(report_payload.get("run_id")),
        "config_id": _optional_str(variant.get("config_id")),
        "report_schema_version": _optional_int(report_payload.get("report_schema_version")),
        "total_trades": _optional_int(total.get("trades")),
        "pnl": _optional_float(total.get("pnl")),
        "return_pct": _optional_float(total.get("return_pct")),
        "profit_factor": _optional_float(total.get("profit_factor")),
        "win_rate": _optional_float(total.get("win_rate")),
        "sharpe": _optional_float(total.get("sharpe")),
        "max_drawdown": _optional_float(total.get("max_drawdown")),
        "gross_pnl": None,
        "fees_paid": None,
    }

    fee_diagnostics = metrics.get("fee_diagnostics")
    if isinstance(fee_diagnostics, dict):
        out["gross_pnl"] = _optional_float(fee_diagnostics.get("gross_pnl"))
        out["fees_paid"] = _optional_float(fee_diagnostics.get("total_fees_paid"))

    quality_breakdown = metrics.get("quality_flag_breakdown")
    if isinstance(quality_breakdown, dict):
        for flag_key, result_field in _QUALITY_FLAG_FIELDS:
            bucket = quality_breakdown.get(flag_key)
            if isinstance(bucket, dict):
                out[result_field] = _optional_int(bucket.get("trades"))
            else:
                out[result_field] = None
    else:
        for _, result_field in _QUALITY_FLAG_FIELDS:
            out[result_field] = None

    for _, _, prefix in _PROFILE_SIDE_SUMMARY_PATHS:
        for _, metric_suffix in _PROFILE_SIDE_SUMMARY_METRICS:
            out[f"{prefix}_{metric_suffix}"] = None

    profile_side_breakdown = metrics.get("profile_side_breakdown")
    if isinstance(profile_side_breakdown, dict):
        for side_key, profile_key, prefix in _PROFILE_SIDE_SUMMARY_PATHS:
            side_block = profile_side_breakdown.get(side_key)
            if not isinstance(side_block, dict):
                continue
            leaf = side_block.get(profile_key)
            if not isinstance(leaf, dict):
                continue
            for leaf_key, metric_suffix in _PROFILE_SIDE_SUMMARY_METRICS:
                value = leaf.get(leaf_key)
                field_name = f"{prefix}_{metric_suffix}"
                if metric_suffix == "trades":
                    out[field_name] = _optional_int(value)
                else:
                    out[field_name] = _optional_float(value)

    return out


def apply_summary_to_result(result: ExperimentCandidateResult, summary: Mapping[str, Any]) -> None:
    for key, value in summary.items():
        if hasattr(result, key):
            setattr(result, key, value)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _optional_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None
