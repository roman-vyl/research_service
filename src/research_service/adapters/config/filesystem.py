"""Atomic filesystem persistence for Research-owned Workbench config state."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import yaml

from research_service.domain.config import ConfigListEntry, StrategyConfigDraft
from research_service.domain.errors import InvalidRequest

_ALLOWED_STRATEGY_IDS = frozenset({"ema_pullback"})
_ALLOWED_SUFFIXES = frozenset({".json", ".yaml", ".yml"})
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class FilesystemConfigStore:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._selection_path = root / ".workbench_selection.json"

    def ensure_ready(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def validate_strategy_id(strategy_id: str) -> str:
        value = strategy_id.strip()
        if value not in _ALLOWED_STRATEGY_IDS:
            raise InvalidRequest(f"unsupported strategy_id {strategy_id!r}; supported: ema_pullback")
        return value

    @staticmethod
    def validate_experiment_id(experiment_id: str) -> str:
        value = experiment_id.strip()
        if not value or not _SAFE_NAME.fullmatch(value) or value in {".", ".."}:
            raise InvalidRequest("experiment_id contains unsafe path characters")
        return value

    def save(self, draft: StrategyConfigDraft) -> str:
        strategy_id = self.validate_strategy_id(draft.strategy_id)
        experiment_id = self.validate_experiment_id(draft.experiment_id)
        strategy_dir = self._root / strategy_id
        strategy_dir.mkdir(parents=True, exist_ok=True)
        target = strategy_dir / f"{experiment_id}.json"
        self._atomic_write_text(target, self.serialize(draft, "json"))
        self.select(strategy_id, experiment_id)
        return str(target.relative_to(self._root))

    def list(self, strategy_id: str) -> tuple[ConfigListEntry, ...]:
        strategy_key = self.validate_strategy_id(strategy_id)
        strategy_dir = self._root / strategy_key
        if not strategy_dir.exists():
            return ()
        entries: list[ConfigListEntry] = []
        for path in sorted(strategy_dir.iterdir(), key=lambda item: item.name):
            if not path.is_file() or path.suffix.lower() not in _ALLOWED_SUFFIXES:
                continue
            entries.append(
                ConfigListEntry(
                    experiment_id=path.stem,
                    path=str(path.relative_to(self._root)),
                    format="json" if path.suffix.lower() == ".json" else "yaml",
                )
            )
        return tuple(entries)

    def selected(self, strategy_id: str) -> str | None:
        strategy_key = self.validate_strategy_id(strategy_id)
        if not self._selection_path.exists():
            return None
        try:
            payload = json.loads(self._selection_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        value = payload.get(strategy_key) if isinstance(payload, dict) else None
        return value if isinstance(value, str) and value.strip() else None

    def select(self, strategy_id: str, experiment_id: str) -> None:
        strategy_key = self.validate_strategy_id(strategy_id)
        experiment_key = self.validate_experiment_id(experiment_id)
        if self.find(strategy_key, experiment_key) is None:
            raise InvalidRequest(
                f"no saved config for strategy_id={strategy_key!r} experiment_id={experiment_key!r}"
            )
        payload: dict[str, str] = {}
        if self._selection_path.exists():
            try:
                raw = json.loads(self._selection_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    payload = {
                        str(key): str(value)
                        for key, value in raw.items()
                        if isinstance(key, str) and isinstance(value, str)
                    }
            except (OSError, json.JSONDecodeError):
                payload = {}
        payload[strategy_key] = experiment_key
        self._atomic_write_text(
            self._selection_path,
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        )

    def find(self, strategy_id: str, experiment_id: str) -> Path | None:
        strategy_key = self.validate_strategy_id(strategy_id)
        experiment_key = self.validate_experiment_id(experiment_id)
        strategy_dir = self._root / strategy_key
        for suffix in (".json", ".yaml", ".yml"):
            candidate = strategy_dir / f"{experiment_key}{suffix}"
            if candidate.is_file():
                return candidate
        return None

    def relative_path(self, path: Path) -> str:
        return str(path.relative_to(self._root))

    def load(self, strategy_id: str, experiment_id: str) -> StrategyConfigDraft | None:
        path = self.find(strategy_id, experiment_id)
        if path is None:
            return None
        try:
            raw: Any
            text = path.read_text(encoding="utf-8")
            raw = json.loads(text) if path.suffix == ".json" else yaml.safe_load(text)
            if not isinstance(raw, dict):
                return None
            return StrategyConfigDraft.model_validate(
                {
                    "config_version": raw.get("schema_version", raw.get("config_version", 1)),
                    "experiment_id": raw.get("experiment_id"),
                    "strategy_id": raw.get("strategy_id"),
                    "execution": raw.get("execution", {}),
                    "instances": raw.get("instances", []),
                }
            )
        except (OSError, ValueError, yaml.YAMLError):
            return None

    @staticmethod
    def serialize(draft: StrategyConfigDraft, fmt: str) -> str:
        normalized = fmt.strip().lower()
        if normalized not in {"json", "yaml"}:
            raise InvalidRequest("format must be json or yaml")
        payload = {
            "schema_version": draft.config_version,
            "experiment_id": draft.experiment_id.strip(),
            "strategy_id": draft.strategy_id.strip(),
            "execution": {
                key: value
                for key, value in draft.execution.model_dump().items()
                if value is not None
            },
            "instances": [instance.model_dump(mode="json") for instance in draft.instances],
        }
        if normalized == "json":
            return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
        return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)

    @staticmethod
    def _atomic_write_text(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
        finally:
            temporary_path.unlink(missing_ok=True)
