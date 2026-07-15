from pathlib import Path

import pytest
from pydantic import ValidationError

from data_engine.config import Settings


def test_settings_defaults() -> None:
    settings = Settings()
    assert isinstance(settings.db_path, Path)
    assert settings.db_path == Path("./market.sqlite")
    assert settings.log_level == "INFO"


def test_settings_invalid_log_level_raises() -> None:
    with pytest.raises(ValidationError):
        Settings(log_level="NOTALEVEL")


def test_settings_reads_env_overrides(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_file = tmp_path / "custom.sqlite"
    monkeypatch.setenv("DATA_ENGINE_DB_PATH", str(db_file))
    monkeypatch.setenv("DATA_ENGINE_LOG_LEVEL", "debug")

    settings = Settings()

    assert settings.db_path == db_file
    assert settings.log_level == "DEBUG"
