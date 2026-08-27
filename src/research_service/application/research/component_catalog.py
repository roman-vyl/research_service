"""Composer component catalog query with app-scoped cache."""

from __future__ import annotations

from research_service.api.contracts.catalog import ComponentCatalog
from research_service.domain.errors import InvalidRequest
from research_service.ports.strategy_engine import StrategyEnginePort


class GetComponentCatalog:
    def __init__(self, strategy_engine: StrategyEnginePort) -> None:
        self._strategy_engine = strategy_engine
        self._cache: dict[str, ComponentCatalog] = {}

    def execute(self, *, strategy_id: str = "ema_pullback") -> ComponentCatalog:
        if strategy_id != "ema_pullback":
            raise InvalidRequest(
                f"unsupported strategy_id {strategy_id!r}; supported: ema_pullback"
            )
        cached = self._cache.get(strategy_id)
        if cached is not None:
            return cached
        # Strategy Engine's own Composer Catalog API response still names its
        # selector field `family` today (cross-repo seam, not renamed here —
        # canonical-strategy-instance-v1, Decision 14). Research reads it
        # under Engine's existing name without exposing `family` to its own
        # callers.
        raw = self._strategy_engine.get_composer_catalog(strategy_id)
        catalog = ComponentCatalog.model_validate(raw)
        if catalog.family != strategy_id:
            raise InvalidRequest(
                "Strategy Engine composer catalog family does not match strategy_id"
            )
        self._cache[strategy_id] = catalog
        return catalog
