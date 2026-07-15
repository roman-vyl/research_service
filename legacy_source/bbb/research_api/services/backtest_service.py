"""Sync backtest from saved config — delegates to research runner."""

from __future__ import annotations

from pathlib import Path

from research.experiments.config_loader import ConfigValidationError, load_strategy_config_file
from research.strategies.ema_pullback.execution.runner import run_strategy_specs_from_config
from research.strategies.ema_pullback.instance_loader import EmaPullbackInstanceValidationError

from research_api.contracts.backtests import BacktestResult
from research_api.contracts.config import StrategyConfigDraft, ValidationErrorItem
from research_api.services import config_service
from research_api.services.config_service import save_draft, validate_draft


def _error(message: str, *, path: str = "") -> BacktestResult:
    return BacktestResult(ok=False, errors=[ValidationErrorItem(path=path, message=message)])


def resolve_config_path(config_path: str) -> Path:
    """Resolve a repo-relative config path; must live under ``research/experiments/configs/``."""

    cleaned = config_path.strip().replace("\\", "/")
    if not cleaned:
        raise ValueError("config_path must be a non-empty string")

    if cleaned.startswith("research/"):
        absolute = (config_service._REPO_ROOT / cleaned).resolve()
    else:
        absolute = (config_service._CONFIGS_ROOT / cleaned).resolve()

    configs_root = config_service._CONFIGS_ROOT.resolve()
    if not absolute.is_relative_to(configs_root):
        raise ValueError("config_path must be under research/experiments/configs/")
    if not absolute.is_file():
        raise FileNotFoundError(f"config file not found: {config_path}")
    return absolute


def _validate_config_file(path: Path) -> BacktestResult | None:
    try:
        load_strategy_config_file(path)
        return None
    except (ConfigValidationError, EmaPullbackInstanceValidationError, ValueError, TypeError) as exc:
        return _error(str(exc))


def _run_config_file(path: Path) -> BacktestResult:
    preflight = _validate_config_file(path)
    if preflight is not None:
        return preflight

    try:
        run_id = run_strategy_specs_from_config(path)
    except Exception as exc:  # noqa: BLE001 — surface runner failures to Workbench
        return _error(str(exc))

    rel = path.relative_to(config_service._REPO_ROOT).as_posix()
    return BacktestResult(ok=True, run_id=run_id, config_path=rel)


def run_backtest_from_draft(draft: StrategyConfigDraft) -> BacktestResult:
    validation = validate_draft(draft)
    if not validation.ok:
        return BacktestResult(ok=False, errors=validation.errors)

    saved = save_draft(draft)
    if not saved.ok or saved.path is None:
        return BacktestResult(ok=False, errors=saved.errors)

    try:
        config_file = resolve_config_path(saved.path)
    except (ValueError, FileNotFoundError) as exc:
        return _error(str(exc))

    return _run_config_file(config_file)


def run_backtest(*, draft: StrategyConfigDraft | None, config_path: str | None) -> BacktestResult:
    if draft is not None:
        return run_backtest_from_draft(draft)

    assert config_path is not None
    try:
        config_file = resolve_config_path(config_path)
    except (ValueError, FileNotFoundError) as exc:
        return _error(str(exc))

    return _run_config_file(config_file)
