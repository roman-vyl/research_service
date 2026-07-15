"""Batch Experiment Management System — preflight validation (no backtests)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from research.experiments.config_loader import ConfigValidationError, load_strategy_config_file
from research.experiments.models import (
    BatchValidationError,
    ExperimentBatchSpec,
    ValidatedBatchSpec,
    ValidatedCandidate,
    load_batch_spec,
    load_batch_spec_file,
)
from research.strategies.ema_pullback.spec import EmaPullbackStrategySpec

_SUPPORTED_FAMILIES = frozenset({"ema_pullback"})


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_batch_spec_with_candidate_configs(
    spec: ExperimentBatchSpec,
    *,
    batch_spec_path: str | Path,
    repo_root: Path | None = None,
) -> ValidatedBatchSpec:
    root = repo_root if repo_root is not None else _repo_root()
    batch_path = Path(batch_spec_path)
    if not batch_path.is_absolute():
        batch_path = (root / batch_path).resolve()
    if not batch_path.exists():
        raise BatchValidationError(f"batch spec file does not exist: {batch_path}")

    if spec.family not in _SUPPORTED_FAMILIES:
        raise BatchValidationError(
            f"unsupported family {spec.family!r}; supported: {sorted(_SUPPORTED_FAMILIES)}"
        )

    batch_spec_hash = file_sha256(batch_path)
    batch_symbol = spec.symbol.strip().upper()
    batch_timeframe = spec.timeframe.strip()

    validated_candidates: list[ValidatedCandidate] = []
    for candidate in spec.candidates:
        validated_candidates.append(
            _validate_candidate(candidate, batch_symbol=batch_symbol, batch_timeframe=batch_timeframe, repo_root=root)
        )

    return ValidatedBatchSpec(
        spec=spec,
        batch_spec_path=_relative_or_posix(batch_path, root),
        batch_spec_hash=batch_spec_hash,
        candidates=tuple(validated_candidates),
    )


def load_and_validate_batch_spec(path: str | Path, *, repo_root: Path | None = None) -> ValidatedBatchSpec:
    spec = load_batch_spec_file(path)
    return validate_batch_spec_with_candidate_configs(spec, batch_spec_path=path, repo_root=repo_root)


def _validate_candidate(
    candidate,
    *,
    batch_symbol: str,
    batch_timeframe: str,
    repo_root: Path,
) -> ValidatedCandidate:
    config_path = Path(candidate.strategy_config_path)
    if not config_path.is_absolute():
        config_path = (repo_root / config_path).resolve()
    if not config_path.exists():
        raise BatchValidationError(
            f"candidate {candidate.candidate_id!r}: strategy config file does not exist: {config_path}"
        )

    _assert_single_instance(config_path, candidate.candidate_id)

    try:
        loaded = load_strategy_config_file(config_path)
    except ConfigValidationError as exc:
        raise BatchValidationError(
            f"candidate {candidate.candidate_id!r}: failed to load strategy config {config_path}: {exc}"
        ) from exc

    if loaded.family != "ema_pullback":
        raise BatchValidationError(
            f"candidate {candidate.candidate_id!r}: unsupported family {loaded.family!r}"
        )

    if len(loaded.entries) != 1:
        raise BatchValidationError(
            f"candidate {candidate.candidate_id!r}: strategy config must contain exactly one instance; "
            f"found {len(loaded.entries)}"
        )

    spec_obj = loaded.specs[0]
    if not isinstance(spec_obj, EmaPullbackStrategySpec):
        raise BatchValidationError(
            f"candidate {candidate.candidate_id!r}: unsupported strategy spec type"
        )

    candidate_symbol = spec_obj.symbol.strip().upper()
    candidate_timeframe = spec_obj.base_timeframe.strip()
    if candidate_symbol != batch_symbol or candidate_timeframe != batch_timeframe:
        raise BatchValidationError(
            f"candidate {candidate.candidate_id!r}: market mismatch — "
            f"batch expects {batch_symbol}/{batch_timeframe}, "
            f"config has {candidate_symbol}/{candidate_timeframe}"
        )

    return ValidatedCandidate(
        spec=candidate,
        strategy_config_path=_relative_or_posix(config_path, repo_root),
        strategy_config_hash=file_sha256(config_path),
    )


def _assert_single_instance(config_path: Path, candidate_id: str) -> None:
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BatchValidationError(
            f"candidate {candidate_id!r}: failed to parse strategy config JSON {config_path}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise BatchValidationError(f"candidate {candidate_id!r}: strategy config root must be an object")

    if "instances" not in payload:
        raise BatchValidationError(
            f"candidate {candidate_id!r}: strategy config must contain exactly one instances item"
        )

    instances = payload["instances"]
    if not isinstance(instances, list):
        raise BatchValidationError(f"candidate {candidate_id!r}: instances must be a list")
    if len(instances) != 1:
        raise BatchValidationError(
            f"candidate {candidate_id!r}: strategy config must contain exactly one instance; "
            f"found {len(instances)}"
        )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _relative_or_posix(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()
