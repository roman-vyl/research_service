"""Draft config validate / serialize / save — delegates to research config_loader."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from research.experiments.config_loader import (
    ConfigValidationError,
    _read_config_file,
    load_strategy_config,
)
from research.strategies.ema_pullback.instance_loader import EmaPullbackInstanceValidationError

from research_api.contracts.config import (
    ConfigListEntry,
    ConfigStateResponse,
    ExecutionDraft,
    SaveConfigResult,
    SerializeResult,
    StrategyConfigDraft,
    ValidationErrorItem,
    ValidationResult,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONFIGS_ROOT = _REPO_ROOT / "research" / "experiments" / "configs"
_SELECTION_FILE: Path | None = None
_CONFIG_EXTENSIONS = frozenset({".json", ".yaml", ".yml"})
_PATH_RE = re.compile(
    r"^(?P<prefix>(?:instances\[\d+\]|blockers\[\d+\]|exits\[\d+\]|"
    r"strategy|trade_management|exit_policy|exit_management|profiles|always_on|context|contexts|"
    r"context_consumption|market|execution|experiment_id|family|schema_version|"
    r"setup|setups\[\d+\]|trigger|direction|risk)[^\s]*)?"
)
SUPPORTED_CONFIG_FAMILIES = {"ema_pullback"}


def _selection_file_path() -> Path:
    if _SELECTION_FILE is not None:
        return _SELECTION_FILE
    return _CONFIGS_ROOT / ".workbench_selection.json"


def validate_config_family(family: str) -> str:
    family_key = family.strip()
    if not family_key:
        raise ValueError("family must be a non-empty string")
    if "/" in family_key or "\\" in family_key or ".." in family_key:
        supported = ", ".join(sorted(SUPPORTED_CONFIG_FAMILIES))
        raise ValueError(f"unsupported family {family!r}; supported: {supported}")
    if family_key not in SUPPORTED_CONFIG_FAMILIES:
        supported = ", ".join(sorted(SUPPORTED_CONFIG_FAMILIES))
        raise ValueError(f"unsupported family {family!r}; supported: {supported}")
    return family_key


def canonical_to_draft(payload: Mapping[str, Any]) -> StrategyConfigDraft:
    execution_raw = payload.get("execution")
    if not isinstance(execution_raw, dict):
        execution_raw = {}
    schema_version = payload.get("schema_version", 1)
    return StrategyConfigDraft(
        config_version=int(schema_version),
        experiment_id=str(payload["experiment_id"]),
        family=str(payload["family"]),
        execution=ExecutionDraft(
            init_cash=execution_raw.get("init_cash"),
            fees=execution_raw.get("fees"),
            slippage=execution_raw.get("slippage"),
        ),
        instances=list(payload["instances"]),
    )


def draft_to_canonical_payload(draft: StrategyConfigDraft) -> dict[str, Any]:
    execution: dict[str, Any] = {}
    if draft.execution.init_cash is not None:
        execution["init_cash"] = draft.execution.init_cash
    if draft.execution.fees is not None:
        execution["fees"] = draft.execution.fees
    if draft.execution.slippage is not None:
        execution["slippage"] = draft.execution.slippage

    return {
        "schema_version": draft.config_version,
        "experiment_id": draft.experiment_id.strip(),
        "family": draft.family.strip(),
        "execution": execution,
        "instances": draft.instances,
    }


def _parse_validation_message(message: str) -> ValidationErrorItem:
    match = _PATH_RE.match(message)
    if match and match.group("prefix"):
        prefix = match.group("prefix")
        rest = message[len(prefix) :].lstrip(" .:—-")
        return ValidationErrorItem(path=prefix, message=rest or message)
    return ValidationErrorItem(path="", message=message)


def validate_draft(draft: StrategyConfigDraft) -> ValidationResult:
    try:
        load_strategy_config(draft_to_canonical_payload(draft), source_file="<draft>")
        return ValidationResult(ok=True)
    except (ConfigValidationError, EmaPullbackInstanceValidationError, ValueError) as exc:
        return ValidationResult(ok=False, errors=[_parse_validation_message(str(exc))])


def _serialize_format(fmt: str) -> str:
    return "yaml" if fmt.lower() == "yaml" else "json"


def serialize_draft(draft: StrategyConfigDraft, *, fmt: str = "json") -> SerializeResult:
    out_fmt = _serialize_format(fmt)
    validation = validate_draft(draft)
    if not validation.ok:
        return SerializeResult(ok=False, format=out_fmt, content="", errors=validation.errors)

    payload = draft_to_canonical_payload(draft)
    if out_fmt == "yaml":
        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError:
            return SerializeResult(
                ok=False,
                format="yaml",
                content="",
                errors=[
                    ValidationErrorItem(
                        path="",
                        message="YAML preview requires PyYAML (pip install -e \".[research]\")",
                    )
                ],
            )
        content = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
        return SerializeResult(ok=True, format="yaml", content=content)

    content = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    return SerializeResult(ok=True, format="json", content=content)


def _safe_experiment_filename(experiment_id: str) -> str:
    cleaned = re.sub(r"[^\w.-]+", "_", experiment_id.strip())
    if not cleaned:
        raise ConfigValidationError("experiment_id must be a non-empty string")
    return cleaned


def _repo_relative_config_path(path: Path) -> str:
    resolved = path.resolve()
    repo_root = _REPO_ROOT.resolve()
    try:
        return resolved.relative_to(repo_root).as_posix()
    except ValueError:
        rel = resolved.relative_to(_CONFIGS_ROOT.resolve())
        return f"research/experiments/configs/{rel.as_posix()}"


def _list_config_files(family_dir: Path) -> list[Path]:
    if not family_dir.is_dir():
        return []
    files = [
        path
        for path in family_dir.iterdir()
        if path.is_file() and path.suffix.lower() in _CONFIG_EXTENSIONS
    ]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files


def _load_selection_store() -> dict[str, str]:
    selection_file = _selection_file_path()
    if not selection_file.is_file():
        return {}
    try:
        loaded = json.loads(selection_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(loaded, dict):
        return {}
    return {str(k): str(v) for k, v in loaded.items() if isinstance(k, str) and isinstance(v, str)}


def _save_selection_store(store: dict[str, str]) -> None:
    selection_file = _selection_file_path()
    _CONFIGS_ROOT.mkdir(parents=True, exist_ok=True)
    selection_file.write_text(
        json.dumps(store, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def get_selected_experiment_id(family: str) -> str | None:
    return _load_selection_store().get(family.strip())


def set_selected_experiment_id(family: str, experiment_id: str) -> None:
    store = _load_selection_store()
    store[family.strip()] = experiment_id.strip()
    _save_selection_store(store)


def find_config_file(family: str, experiment_id: str) -> Path | None:
    family_key = validate_config_family(family)
    family_dir = _CONFIGS_ROOT / family_key
    if not family_dir.is_dir():
        return None

    direct = family_dir / f"{_safe_experiment_filename(experiment_id)}.json"
    if direct.is_file():
        return direct

    target = experiment_id.strip()
    for path in _list_config_files(family_dir):
        try:
            payload = _read_config_file(path)
        except ConfigValidationError:
            continue
        if str(payload.get("experiment_id", "")).strip() == target:
            return path
    return None


def load_draft_from_file(path: Path) -> StrategyConfigDraft:
    payload = _read_config_file(path)
    load_strategy_config(payload, source_file=path)
    return canonical_to_draft(payload)


def list_config_entries(family: str) -> list[ConfigListEntry]:
    family_key = validate_config_family(family)
    family_dir = _CONFIGS_ROOT / family_key
    entries: list[ConfigListEntry] = []
    for path in _list_config_files(family_dir):
        try:
            payload = _read_config_file(path)
            experiment_id = str(payload.get("experiment_id", path.stem)).strip()
        except ConfigValidationError:
            experiment_id = path.stem
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()
        entries.append(
            ConfigListEntry(
                experiment_id=experiment_id,
                path=_repo_relative_config_path(path),
                updated_at=mtime,
            )
        )
    return entries


def resolve_selected_experiment_id(family: str, entries: list[ConfigListEntry]) -> str | None:
    if not entries:
        return None
    selected = get_selected_experiment_id(family)
    if selected and any(entry.experiment_id == selected for entry in entries):
        return selected
    return entries[0].experiment_id


def get_config_state(family: str) -> ConfigStateResponse:
    family_key = validate_config_family(family)
    entries = list_config_entries(family_key)
    selected_id = resolve_selected_experiment_id(family_key, entries)
    if selected_id is None:
        return ConfigStateResponse(family=family_key, configs=entries)

    selected_path: str | None = None
    draft: StrategyConfigDraft | None = None
    config_file = find_config_file(family_key, selected_id)
    if config_file is not None:
        selected_path = _repo_relative_config_path(config_file)
        try:
            draft = load_draft_from_file(config_file)
        except (ConfigValidationError, EmaPullbackInstanceValidationError, ValueError):
            draft = None

    return ConfigStateResponse(
        family=family_key,
        selected_experiment_id=selected_id,
        selected_path=selected_path,
        draft=draft,
        configs=entries,
    )


def select_config(family: str, experiment_id: str) -> ConfigStateResponse:
    family_key = validate_config_family(family)
    experiment_key = experiment_id.strip()
    config_file = find_config_file(family_key, experiment_key)
    if config_file is None:
        raise FileNotFoundError(
            f"no saved config for family={family_key!r} experiment_id={experiment_key!r}",
        )
    set_selected_experiment_id(family_key, experiment_key)
    return get_config_state(family_key)


def save_draft(draft: StrategyConfigDraft) -> SaveConfigResult:
    family = validate_config_family(draft.family)
    validation = validate_draft(draft)
    if not validation.ok:
        return SaveConfigResult(ok=False, errors=validation.errors)

    filename = f"{_safe_experiment_filename(draft.experiment_id)}.json"
    target_dir = _CONFIGS_ROOT / family
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / filename

    payload = draft_to_canonical_payload(draft)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    set_selected_experiment_id(family, draft.experiment_id.strip())
    rel = f"research/experiments/configs/{family}/{filename}"
    return SaveConfigResult(ok=True, path=rel)
