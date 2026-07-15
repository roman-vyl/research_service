"""Single-file external config loader for research experiments."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping


class ConfigValidationError(ValueError):
    """Raised when an external experiment config fails MVP validation."""


@dataclass(frozen=True)
class ConfigEntryMetadata:
    source_file: str
    entry_index: int
    family: str
    instance_id: str
    strategy_spec_config_id: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "source_file": self.source_file,
            "entry_index": self.entry_index,
            "family": self.family,
            "instance_id": self.instance_id,
            "strategy_spec_config_id": self.strategy_spec_config_id,
        }


@dataclass(frozen=True)
class LoadedExternalConfig:
    schema_version: int
    experiment_id: str
    family: str
    execution: "ExternalExecutionConfig"
    source_file: Path
    specs: tuple[Any, ...]
    entries: tuple[ConfigEntryMetadata, ...]

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "experiment_id": self.experiment_id,
            "family": self.family,
            "execution": self.execution.to_payload(),
            "source_file": self.source_file.as_posix(),
            "entries_count": len(self.entries),
            "entries": [entry.to_payload() for entry in self.entries],
        }


@dataclass(frozen=True)
class ExternalExecutionConfig:
    init_cash: float | None = None
    fees: float | None = None
    slippage: float | None = None

    def to_payload(self) -> dict[str, float]:
        payload: dict[str, float] = {}
        if self.init_cash is not None:
            payload["init_cash"] = self.init_cash
        if self.fees is not None:
            payload["fees"] = self.fees
        if self.slippage is not None:
            payload["slippage"] = self.slippage
        return payload


_ENVELOPE_KEYS = frozenset({"schema_version", "experiment_id", "family", "execution", "instances"})
_SUPPORTED_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class _LoadedFamilyInstance:
    spec: Any
    strategy_spec_config_id: str


def load_strategy_config_file(path: str | Path) -> LoadedExternalConfig:
    source_file = Path(path)
    payload = _read_config_file(source_file)
    return load_strategy_config(payload, source_file=source_file)


def load_strategy_config(
    payload: Mapping[str, Any],
    *,
    source_file: str | Path = "<memory>",
) -> LoadedExternalConfig:
    source_path = Path(source_file)
    root = _require_mapping("config payload", payload)
    schema_version = _parse_schema_version(root)
    experiment_id = _require_non_empty_str(root, "experiment_id")
    family = _require_non_empty_str(root, "family")
    execution = _parse_execution(root.get("execution", {}))

    instance_payloads = _normalize_instances(root)
    instance_ids = _validate_unique_instance_ids(instance_payloads)
    loaded_instances = tuple(_load_family_instance(family, item) for item in instance_payloads)
    specs = tuple(loaded.spec for loaded in loaded_instances)
    entries = tuple(
        ConfigEntryMetadata(
            source_file=source_path.as_posix(),
            entry_index=index,
            family=family,
            instance_id=instance_ids[index],
            strategy_spec_config_id=loaded.strategy_spec_config_id,
        )
        for index, loaded in enumerate(loaded_instances)
    )
    return LoadedExternalConfig(
        schema_version=schema_version,
        experiment_id=experiment_id,
        family=family,
        execution=execution,
        source_file=source_path,
        specs=specs,
        entries=entries,
    )


def _read_config_file(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        raise ConfigValidationError(f"config file does not exist: {path}")
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    try:
        if suffix in {".yaml", ".yml"}:
            try:
                import yaml  # type: ignore[import-untyped]
            except ImportError as exc:  # pragma: no cover - depends on optional local env
                raise ConfigValidationError("YAML config requires PyYAML to be installed") from exc
            loaded = yaml.safe_load(text)
        else:
            loaded = json.loads(text)
    except ConfigValidationError:
        raise
    except Exception as exc:
        raise ConfigValidationError(f"failed to parse config file {path}: {exc}") from exc
    return _require_mapping("config payload", loaded)


def _normalize_instances(root: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    if "run_name" in root:
        raise ConfigValidationError("experiment_id is required; run_name is not supported in MVP")
    if "instances" in root:
        unknown = sorted(set(root) - _ENVELOPE_KEYS)
        if unknown:
            raise ConfigValidationError(f"unknown envelope field(s): {', '.join(unknown)}")
        raw_instances = root["instances"]
        if not isinstance(raw_instances, list):
            raise ConfigValidationError("instances must be a list")
        if not raw_instances:
            raise ConfigValidationError("instances must contain at least one entry")
        return tuple(
            _require_mapping(f"instances[{index}]", item)
            for index, item in enumerate(raw_instances)
        )

    single = dict(root)
    for key in _ENVELOPE_KEYS - {"instances"}:
        single.pop(key, None)
    if not single:
        raise ConfigValidationError("single config object must contain instance fields")
    return (_require_mapping("single instance", single),)


def _validate_unique_instance_ids(
    instances: tuple[Mapping[str, Any], ...],
) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for index, item in enumerate(instances):
        if "external_config_id" in item:
            raise ConfigValidationError(
                f"instances[{index}] uses external_config_id; MVP requires instance_id"
            )
        instance_id = _require_non_empty_str(item, "instance_id", prefix=f"instances[{index}].")
        if instance_id in seen:
            raise ConfigValidationError(f"duplicate instance_id in config bundle: {instance_id!r}")
        seen.add(instance_id)
        out.append(instance_id)
    return tuple(out)


def _parse_execution(value: Any) -> ExternalExecutionConfig:
    payload = _require_mapping("execution", value)
    unknown = sorted(set(payload) - {"init_cash", "fees", "slippage"})
    if unknown:
        raise ConfigValidationError(f"unknown execution field(s): {', '.join(unknown)}")
    return ExternalExecutionConfig(
        init_cash=_optional_positive_number(payload, "init_cash"),
        fees=_optional_non_negative_number(payload, "fees"),
        slippage=_optional_non_negative_number(payload, "slippage"),
    )


def _parse_schema_version(payload: Mapping[str, Any]) -> int:
    value = _require_present(payload, "schema_version")
    if value != _SUPPORTED_SCHEMA_VERSION:
        raise ConfigValidationError(
            f"schema_version must be exactly {_SUPPORTED_SCHEMA_VERSION} for MVP"
        )
    return _SUPPORTED_SCHEMA_VERSION


def _load_family_instance(family: str, item: Mapping[str, Any]) -> _LoadedFamilyInstance:
    if family != "ema_pullback":
        raise ConfigValidationError(f"unsupported family {family!r}; supported families: ema_pullback")
    from research.strategies.ema_pullback.instance_loader import load_ema_pullback_config_entry

    loaded = load_ema_pullback_config_entry(item)
    return _LoadedFamilyInstance(
        spec=loaded.spec,
        strategy_spec_config_id=loaded.strategy_spec_config_id,
    )


def _require_mapping(name: str, value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ConfigValidationError(f"{name} must be an object")
    return value


def _require_present(payload: Mapping[str, Any], key: str) -> Any:
    if key not in payload:
        raise ConfigValidationError(f"{key} is required")
    return payload[key]


def _require_non_empty_str(
    payload: Mapping[str, Any],
    key: str,
    *,
    prefix: str = "",
) -> str:
    value = _require_present(payload, key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigValidationError(f"{prefix}{key} must be a non-empty string")
    return value.strip()


def _optional_positive_number(payload: Mapping[str, Any], key: str) -> float | None:
    if key not in payload:
        return None
    value = payload[key]
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        raise ConfigValidationError(f"execution.{key} must be a positive number")
    return float(value)


def _optional_non_negative_number(payload: Mapping[str, Any], key: str) -> float | None:
    if key not in payload:
        return None
    value = payload[key]
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        raise ConfigValidationError(f"execution.{key} must be a non-negative number")
    return float(value)

