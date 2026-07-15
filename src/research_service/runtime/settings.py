"""Research Service runtime settings."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RESEARCH_", extra="ignore")

    host: str = "0.0.0.0"
    port: int = Field(default=8080, ge=1, le=65535)
    strategy_engine_url: str = "http://strategy-engine:8080"
    market_data_url: str = "http://market-data-service:8080"
    artifacts_root: Path = Path("var/runs")
    configs_root: Path = Path("var/configs")
    cors_origins: tuple[str, ...] = (
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    )
