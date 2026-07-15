"""Research-owned Workbench config persistence orchestration."""

from __future__ import annotations

from research_service.adapters.config import FilesystemConfigStore
from research_service.api.contracts.config import (
    ConfigStateResponse,
    SaveConfigResult,
    SelectConfigRequest,
    SerializeResult,
    StrategyConfigDraft,
)
from research_service.application.research.config_validation import ValidateStrategyConfig


class ManageResearchConfigs:
    def __init__(
        self,
        validation: ValidateStrategyConfig,
        store: FilesystemConfigStore,
    ) -> None:
        self._validation = validation
        self._store = store

    def serialize(self, draft: StrategyConfigDraft, fmt: str) -> SerializeResult:
        normalized = fmt.strip().lower()
        result = self._validation.execute(draft)
        if not result.ok:
            return SerializeResult(
                ok=False,
                format="yaml" if normalized == "yaml" else "json",
                errors=result.errors,
            )
        content = self._store.serialize(draft, normalized)
        return SerializeResult(ok=True, format=normalized, content=content)  # type: ignore[arg-type]

    def save(self, draft: StrategyConfigDraft) -> SaveConfigResult:
        result = self._validation.execute(draft)
        if not result.ok:
            return SaveConfigResult(ok=False, errors=result.errors)
        return SaveConfigResult(ok=True, path=self._store.save(draft))

    def state(self, family: str) -> ConfigStateResponse:
        family_key = self._store.validate_family(family)
        entries = self._store.list(family_key)
        selected = self._store.selected(family_key)
        selected_path: str | None = None
        draft = None
        if selected is not None:
            path = self._store.find(family_key, selected)
            if path is not None:
                selected_path = self._store.relative_path(path)
                draft = self._store.load(family_key, selected)
        return ConfigStateResponse(
            family=family_key,
            selected_experiment_id=selected,
            selected_path=selected_path,
            draft=draft,
            configs=list(entries),
        )

    def select(self, request: SelectConfigRequest) -> ConfigStateResponse:
        self._store.select(request.family, request.experiment_id)
        return self.state(request.family)
