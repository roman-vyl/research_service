"""Concrete dependency assembly."""

from __future__ import annotations

from dataclasses import dataclass

from research_service.adapters.artifacts.filesystem import FilesystemArtifactStore
from research_service.adapters.http.market_data_client import HttpMarketDataClient
from research_service.adapters.http.strategy_engine_client import HttpStrategyEngineClient
from research_service.ports.artifacts import ResearchArtifactStore
from research_service.ports.market_data import MarketDataPort
from research_service.ports.strategy_engine import StrategyEnginePort
from research_service.runtime.settings import Settings


@dataclass(frozen=True, slots=True)
class Container:
    settings: Settings
    strategy_engine: StrategyEnginePort
    market_data: MarketDataPort
    artifacts: ResearchArtifactStore


def build_container(settings: Settings) -> Container:
    artifacts = FilesystemArtifactStore(settings.artifacts_root)
    artifacts.ensure_ready()
    return Container(
        settings=settings,
        strategy_engine=HttpStrategyEngineClient(settings.strategy_engine_url),
        market_data=HttpMarketDataClient(settings.market_data_url),
        artifacts=artifacts,
    )
