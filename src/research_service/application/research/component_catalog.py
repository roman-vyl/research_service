"""Composer component catalog query with app-scoped cache."""

from __future__ import annotations

from research_service.api.contracts.catalog import ComponentCatalog
from research_service.domain.errors import InvalidRequest
from research_service.ports.strategy_engine import StrategyEnginePort


class GetComponentCatalog:
    def __init__(self, strategy_engine: StrategyEnginePort) -> None:
        self._strategy_engine = strategy_engine
        self._cache: dict[str, ComponentCatalog] = {}

    def execute(self, *, family: str = "ema_pullback") -> ComponentCatalog:
        if family != "ema_pullback":
            raise InvalidRequest(f"unsupported family {family!r}; supported: ema_pullback")
        cached = self._cache.get(family)
        if cached is not None:
            return cached
        raw = self._strategy_engine.get_composer_catalog(family)
        catalog = ComponentCatalog.model_validate(raw)
        if catalog.family != family:
            raise InvalidRequest("Strategy Engine composer catalog family does not match request")
        self._cache[family] = catalog
        return catalog
