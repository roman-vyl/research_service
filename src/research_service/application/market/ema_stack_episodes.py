"""EMA stack episode history for the Workbench (`research-market-ema-stack-episodes-v1`).

A thin proxy: Strategy Engine owns the episode, its parameters and its
cache; Research Service forwards the request and returns the answer.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from research_service.ports.strategy_engine import StrategyEnginePort


class GetEmaStackEpisodeHistory:
    def __init__(self, strategy_engine: StrategyEnginePort) -> None:
        self._strategy_engine = strategy_engine

    def execute(self, body: Mapping[str, Any]) -> dict[str, Any]:
        return self._strategy_engine.query_ema_stack_episode_history(body)


class GetStrategyFeaturePlan:
    """Engine's feature plan of a strategy, unchanged: the Workbench reads the
    effective episode parameters (`episode_params_by_ref`) from it."""

    def __init__(self, strategy_engine: StrategyEnginePort) -> None:
        self._strategy_engine = strategy_engine

    def execute(self, strategy_id: str, body: Mapping[str, Any]) -> dict[str, Any]:
        return self._strategy_engine.build_strategy_feature_plan(strategy_id, body)
